#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Resolve static and shared library artefacts under a GitLab package ``lib/``.

See ``design/plans/package-use-libs-defaults.md``.
"""

from __future__ import annotations

import os

import SCons.Errors

from cuppa.colourise import as_info, as_notice
from cuppa.log import logger


LINK_PREFER_STATIC = "prefer_static"
LINK_PREFER_SHARED = "prefer_shared"
LINK_STATIC = "static"
LINK_SHARED = "shared"
VALID_LINK_MODES = (
        LINK_PREFER_STATIC,
        LINK_PREFER_SHARED,
        LINK_STATIC,
        LINK_SHARED,
)

_LINK_CONTRIB_KEY = "_cuppa_package_link_contrib"


def env_lib_naming( env ):
    """Return ``(lib_prefix, lib_suffix, shlib_prefix, shlib_suffix)`` from ``env``.

    SCons often stores ``SHLIBPREFIX`` as ``$LIBPREFIX`` until substituted; always
    expand via ``env.subst`` when available.
    """
    def _get( key, default ):
        if key not in env:
            return default
        subst = getattr( env, "subst", None )
        if callable( subst ):
            return subst( "${}".format( key ) )
        value = env[key]
        return default if value is None else str( value )

    lib_prefix = _get( "LIBPREFIX", "lib" )
    lib_suffix = _get( "LIBSUFFIX", ".a" )
    shlib_prefix = _get( "SHLIBPREFIX", lib_prefix )
    shlib_suffix = _get( "SHLIBSUFFIX", ".so" )
    return lib_prefix, lib_suffix, shlib_prefix, shlib_suffix


def normalise_link_mode( link ):
    """Return a valid link mode, defaulting to prefer_static."""
    if link is None or link == "":
        return LINK_PREFER_STATIC
    mode = str( link )
    if mode not in VALID_LINK_MODES:
        raise SCons.Errors.StopError(
                "Unknown package link mode [{}]; expected one of {}".format(
                        mode, ", ".join( VALID_LINK_MODES )
                )
        )
    return mode


def _stem_variants( name ):
    """Return name forms useful when matching package slug to a lib stem."""
    if not name:
        return set()
    text = str( name )
    return { text, text.replace( "-", "_" ), text.replace( "_", "-" ) }


def list_static_lib_stems( lib_dir, lib_prefix, lib_suffix, library_prefix="" ):
    """Return sorted static library leaf names found under ``lib_dir``."""
    if not lib_dir or not os.path.isdir( lib_dir ):
        return []
    names = []
    library_prefix = library_prefix or ""
    lib_prefix = lib_prefix or ""
    lib_suffix = lib_suffix or ""
    for fname in sorted( os.listdir( lib_dir ) ):
        if lib_prefix and not fname.startswith( lib_prefix ):
            continue
        if lib_suffix and not fname.endswith( lib_suffix ):
            continue
        stem = fname[len( lib_prefix ):] if lib_prefix else fname
        if lib_suffix:
            stem = stem[: -len( lib_suffix )]
        if library_prefix and stem.startswith( library_prefix ):
            stem = stem[len( library_prefix ):]
        if stem:
            names.append( stem )
    return names


def _shared_stem_from_filename( fname, shlib_prefix, shlib_suffix, library_prefix="" ):
    """Extract a link stem from a shared library filename, or ``None``."""
    shlib_prefix = shlib_prefix or ""
    shlib_suffix = shlib_suffix or ""
    library_prefix = library_prefix or ""
    if shlib_prefix and not fname.startswith( shlib_prefix ):
        return None
    body = fname[len( shlib_prefix ):] if shlib_prefix else fname
    if shlib_suffix:
        if body == shlib_suffix.lstrip( "." ):  # defensive; unlikely
            return None
        # libfmt.so / libfmt.so.12.2.0 / libfmt.dylib
        if body.endswith( shlib_suffix ):
            stem = body[: -len( shlib_suffix )]
        elif shlib_suffix in body:
            # versioned: libfmt.so.12.2.0 → fmt
            index = body.find( shlib_suffix )
            if index <= 0:
                return None
            # require suffix at a boundary: name + ".so" + rest
            if body[index: index + len( shlib_suffix )] != shlib_suffix:
                return None
            if len( body ) > index + len( shlib_suffix ):
                if body[index + len( shlib_suffix )] not in ( ".", "-" ):
                    return None
            stem = body[:index]
        else:
            return None
    else:
        stem = body
    if library_prefix and stem.startswith( library_prefix ):
        stem = stem[len( library_prefix ):]
    return stem or None


def list_shared_lib_stems( lib_dir, shlib_prefix, shlib_suffix, library_prefix="" ):
    """Return sorted unique shared library leaf names under ``lib_dir``."""
    if not lib_dir or not os.path.isdir( lib_dir ):
        return []
    found = set()
    for fname in os.listdir( lib_dir ):
        path = os.path.join( lib_dir, fname )
        if not os.path.isfile( path ) and not os.path.islink( path ):
            continue
        stem = _shared_stem_from_filename(
                fname, shlib_prefix, shlib_suffix, library_prefix=library_prefix
        )
        if stem:
            found.add( stem )
    return sorted( found )


def list_linkable_lib_stems(
        lib_dir,
        lib_prefix,
        lib_suffix,
        shlib_prefix,
        shlib_suffix,
        library_prefix="",
):
    """Return sorted unique stems that have a static and/or shared artefact."""
    stems = set( list_static_lib_stems(
            lib_dir, lib_prefix, lib_suffix, library_prefix=library_prefix
    ) )
    stems.update( list_shared_lib_stems(
            lib_dir, shlib_prefix, shlib_suffix, library_prefix=library_prefix
    ) )
    return sorted( stems )


def heuristic_default_use_libs( stems, package_slug=None, dependency_name=None ):
    """Guess a default link set when the manifest omits ``default_use_libs``.

    | ``lib/`` contents | Default |
    |-------------------|---------|
    | No linkable libs | ``[]`` |
    | Exactly one stem | That stem |
    | Multiple stems, one equals package slug / BuildWith name | That stem |
    | Otherwise | ``[]`` (refuse to guess) |
    """
    stems = list( stems or [] )
    if not stems:
        return []
    if len( stems ) == 1:
        return [ stems[0] ]

    wanted = _stem_variants( package_slug ) | _stem_variants( dependency_name )
    matches = [ stem for stem in stems if stem in wanted ]
    if len( matches ) == 1:
        return [ matches[0] ]
    # Prefer an exact slug / name hit when several variant forms collide.
    for candidate in ( package_slug, dependency_name ):
        if candidate and candidate in stems:
            return [ str( candidate ) ]
    return []


def find_static_library_path( lib_dir, stem, lib_prefix, lib_suffix, library_prefix="" ):
    """Return the path to ``lib{prefix}{stem}{suffix}`` when it exists."""
    library_prefix = library_prefix or ""
    prefix = "" if stem.startswith( library_prefix ) else library_prefix
    path = os.path.join(
            lib_dir,
            ( lib_prefix or "" ) + prefix + stem + ( lib_suffix or "" ),
    )
    return path if os.path.isfile( path ) else None


def find_shared_library_path( lib_dir, stem, shlib_prefix, shlib_suffix, library_prefix="" ):
    """Return a path to a shared artefact for ``stem``, preferring the unversioned name."""
    library_prefix = library_prefix or ""
    prefix = "" if stem.startswith( library_prefix ) else library_prefix
    shlib_prefix = shlib_prefix or ""
    shlib_suffix = shlib_suffix or ""
    exact = os.path.join( lib_dir, shlib_prefix + prefix + stem + shlib_suffix )
    if os.path.isfile( exact ) or os.path.islink( exact ):
        return exact
    if not lib_dir or not os.path.isdir( lib_dir ):
        return None
    # Versioned sonames: libfmt.so.12.2.0
    matches = []
    for fname in sorted( os.listdir( lib_dir ) ):
        path = os.path.join( lib_dir, fname )
        if not ( os.path.isfile( path ) or os.path.islink( path ) ):
            continue
        found = _shared_stem_from_filename(
                fname, shlib_prefix, shlib_suffix, library_prefix=library_prefix
        )
        if found == stem:
            matches.append( path )
    return matches[0] if matches else None


def resolve_library_artefact(
        lib_dir,
        stem,
        env,
        library_prefix="",
        link=LINK_PREFER_STATIC,
):
    """Resolve ``stem`` to ``('static', path)`` or ``('shared', link_name)``.

    Raises ``StopError`` when neither artefact exists (or the forced mode is missing).
    """
    mode = normalise_link_mode( link )
    lib_prefix, lib_suffix, shlib_prefix, shlib_suffix = env_lib_naming( env )

    static_path = find_static_library_path(
            lib_dir, stem, lib_prefix, lib_suffix, library_prefix=library_prefix
    )
    shared_path = find_shared_library_path(
            lib_dir, stem, shlib_prefix, shlib_suffix, library_prefix=library_prefix
    )

    if mode == LINK_STATIC:
        if static_path:
            return "static", static_path
        raise SCons.Errors.StopError(
                "Package library [{}] requested as static but [{}] was not found under [{}]".format(
                        stem, ( lib_prefix or "" ) + stem + ( lib_suffix or "" ), lib_dir
                )
        )
    if mode == LINK_SHARED:
        if shared_path:
            return "shared", stem
        raise SCons.Errors.StopError(
                "Package library [{}] requested as shared but no matching "
                "shared artefact was found under [{}]".format( stem, lib_dir )
        )
    if mode == LINK_PREFER_SHARED:
        if shared_path:
            return "shared", stem
        if static_path:
            return "static", static_path
    else:  # prefer_static
        if static_path:
            return "static", static_path
        if shared_path:
            return "shared", stem

    raise SCons.Errors.StopError(
            "Package library [{}] not found under [{}] "
            "(looked for static [{}] and shared [{}{}])".format(
                    stem,
                    lib_dir,
                    ( lib_prefix or "" ) + stem + ( lib_suffix or "" ),
                    ( shlib_prefix or "" ) + stem,
                    shlib_suffix or "",
            )
    )


def _remove_from_env_list( env, key, items ):
    if not items:
        return
    current = list( env.get( key ) or [] )
    drop = { str( item ) for item in items }
    env[key] = [ item for item in current if str( item ) not in drop ]


def clear_package_link_contribution( env, contrib_key ):
    """Remove a previous ``use_libs`` contribution recorded for ``contrib_key``."""
    store = env.get( _LINK_CONTRIB_KEY ) or {}
    contrib = store.pop( contrib_key, None )
    if _LINK_CONTRIB_KEY in env:
        env[_LINK_CONTRIB_KEY] = store
    if not contrib:
        return
    _remove_from_env_list( env, "STATICLIBS", contrib.get( "static" ) or [] )
    _remove_from_env_list( env, "SHAREDLIBS", contrib.get( "shared" ) or [] )
    _remove_from_env_list( env, "LIBPATH", contrib.get( "libpath" ) or [] )


def record_package_link_contribution( env, contrib_key, static=None, shared=None, libpath=None ):
    """Remember what this package added so a later ``use_libs`` can replace it."""
    store = env.setdefault( _LINK_CONTRIB_KEY, {} )
    store[contrib_key] = {
            "static": list( static or [] ),
            "shared": list( shared or [] ),
            "libpath": list( libpath or [] ),
    }


def apply_resolved_libs( env, lib_dir, libs, library_prefix="", link=LINK_PREFER_STATIC, package_id=None ):
    """Append resolved static files and/or shared stems for ``libs``.

    Returns the contribution dict that was applied (for recording / tests).
    """
    from SCons.Script import Flatten

    libs = Flatten( [ libs ] )
    static_nodes = []
    shared_stems = []
    for lib in libs:
        kind, value = resolve_library_artefact(
                lib_dir,
                str( lib ),
                env,
                library_prefix=library_prefix,
                link=link,
        )
        if kind == "static":
            static_nodes.append( env.File( value ) )
            logger.debug(
                    "Linking static package library [{}] from [{}] for [{}]".format(
                            as_info( str( lib ) ),
                            as_notice( value ),
                            as_info( package_id or lib_dir ),
                    )
            )
        else:
            shared_stems.append( value )
            logger.debug(
                    "Linking shared package library [{}] via LIBPATH [{}] for [{}]".format(
                            as_info( str( lib ) ),
                            as_notice( lib_dir ),
                            as_info( package_id or lib_dir ),
                    )
            )

    libpath = []
    if shared_stems:
        libpath = [ lib_dir ]
        env.AppendUnique( LIBPATH = libpath )
        env.AppendUnique( SHAREDLIBS = shared_stems )
    if static_nodes:
        env.AppendUnique( STATICLIBS = static_nodes )

    return {
            "static": static_nodes,
            "shared": shared_stems,
            "libpath": libpath,
    }
