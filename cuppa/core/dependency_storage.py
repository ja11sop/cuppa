#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency storage — resolve-only path discovery
#-------------------------------------------------------------------------------

"""Resolve dependency on-disk paths without retrieving them.

Optional ``storage_paths()`` on a dependency instance returns the folders that dependency owns.
Types that omit it are reported as skipped (layout not declared), never guessed.

``cuppa_env['storage_resolve_only']`` disables fetch/extract while factories still compute paths
(the same idea as ``retrieval_disabled_reason()`` for ``--offline`` / ``--clean``).
"""

from collections import namedtuple

from cuppa.log import logger
from cuppa.colourise import as_info, as_warning


RESOLVE_ONLY_REASON = "storage action"

# One owned path discovered for a named dependency under the current selection.
OwnedPath = namedtuple(
    'OwnedPath',
    [
        'dependency',       # sconstruct / registry name
        'kind',             # location | package | conan | boost | …
        'category',         # dependencies | downloads | build | develop
        'path',
        'qualifier',        # @branch, version, fingerprint prefix, …
        'tool_variant',     # toolchain_variant_arch_abi or None
        'develop',          # True when this path is a develop working copy
    ],
)

Skip = namedtuple( 'Skip', [ 'dependency', 'reason' ] )


def enable_resolve_only( cuppa_env ):
    """Mark the environment so dependency factories do not retrieve or extract."""
    cuppa_env['storage_resolve_only'] = True


def resolve_only_active( env ):
    return bool( env.get( 'storage_resolve_only' ) )


def empty_storage_paths():
    return {
        'dependencies': [],
        'downloads': [],
        'build': [],
        'develop': [],
    }


def normalise_storage_paths( paths ):
    """Coerce a ``storage_paths()`` result into the standard four lists."""
    result = empty_storage_paths()
    if not paths:
        return result
    for key in result:
        value = paths.get( key ) or []
        if isinstance( value, ( str, bytes ) ):
            value = [ value ]
        result[key] = [ p for p in value if p ]
    return result


def _dependency_kind( instance ):
    module = getattr( type( instance ), '__module__', '' ) or ''
    name = type( instance ).__name__
    if 'conan' in module or 'conan' in name.lower():
        return 'conan'
    if 'boost' in module or name == 'Boost':
        return 'boost'
    if 'package' in module or 'Package' in name:
        return 'package'
    if 'location' in module or hasattr( instance, '_location' ):
        return 'location'
    return 'dependency'


def _call_storage_paths( instance ):
    method = getattr( instance, 'storage_paths', None )
    if method is None:
        return None
    return normalise_storage_paths( method() )


def _meta_from_instance( instance ):
    qualifier = None
    tool_variant = None
    for attr in ( 'storage_qualifier', 'qualifier' ):
        getter = getattr( instance, attr, None )
        if callable( getter ):
            qualifier = getter()
            break
        if getter is not None and not callable( getter ):
            qualifier = getter
            break
    for attr in ( 'storage_tool_variant', 'tool_variant' ):
        getter = getattr( instance, attr, None )
        if callable( getter ):
            tool_variant = getter()
            break
        if getter is not None and not callable( getter ):
            tool_variant = getter
            break
    # Location / boost expose branch via the wrapped Location.
    if qualifier is None:
        location = getattr( instance, '_location', None )
        if location is not None:
            branch = getattr( location, 'branch', None )
            if callable( branch ):
                branch = branch()
            if branch:
                qualifier = '@' + str( branch )
            local_folder = getattr( location, 'local_folder', None )
            if callable( local_folder ):
                folder = local_folder()
                if folder and '@' in folder:
                    qualifier = '@' + folder.rsplit( '@', 1 )[-1]
    return qualifier, tool_variant


def resolve_named_dependencies( construct, cuppa_env, names ):
    """Create each named dependency for the active selection and collect owned paths.

    Returns ``(owned_paths, skips)``. Factories that return ``None`` or lack
    ``storage_paths`` are skipped with a reason.
    """
    enable_resolve_only( cuppa_env )
    factories = cuppa_env.get( 'dependencies' ) or {}
    known = sorted( factories.keys() )
    owned = []
    skips = []
    seen_paths = set()

    toolchains = cuppa_env.get( 'active_toolchains' ) or []
    if not toolchains:
        skips.append( Skip( dependency='*', reason='no active toolchains' ) )
        return owned, skips

    for name in names:
        factory = factories.get( name )
        if factory is None:
            skips.append( Skip(
                dependency=name,
                reason='unknown dependency (known: {})'.format( ', '.join( known ) or 'none' ),
            ) )
            continue

        created_any = False
        declared = False
        for toolchain in toolchains:
            for build_env in construct.create_build_envs( toolchain, cuppa_env ):
                try:
                    instance = factory( build_env )
                except Exception as error:
                    logger.warn( "Could not resolve dependency [{}] for storage: {}".format(
                            as_warning( name ), as_warning( str( error ) )
                    ) )
                    skips.append( Skip( dependency=name, reason=str( error ) ) )
                    created_any = True
                    continue

                if instance is None:
                    continue
                created_any = True

                paths = _call_storage_paths( instance )
                if paths is None:
                    # Try the wrapped package / location if the outer wrapper has none.
                    for attr in ( '_package', '_location' ):
                        inner = getattr( instance, attr, None )
                        if inner is not None:
                            paths = _call_storage_paths( inner )
                            if paths is not None:
                                break
                if paths is None:
                    continue

                declared = True
                kind = _dependency_kind( instance )
                qualifier, tool_variant = _meta_from_instance( instance )
                if tool_variant is None and 'tool_variant_dir' in build_env:
                    # Flatten tool_variant_dir (toolchain/variant/arch/abi) to package style.
                    tool_variant = build_env['tool_variant_dir'].replace( '/', '_' ).replace( '\\', '_' )

                for category, path_list in paths.items():
                    for path in path_list:
                        key = ( category, path )
                        if key in seen_paths:
                            continue
                        seen_paths.add( key )
                        owned.append( OwnedPath(
                            dependency=name,
                            kind=kind,
                            category=category,
                            path=path,
                            qualifier=qualifier,
                            tool_variant=tool_variant if category != 'develop' else None,
                            develop=( category == 'develop' ),
                        ) )

        if not created_any:
            skips.append( Skip( dependency=name, reason='factory returned nothing' ) )
        elif not declared:
            skips.append( Skip( dependency=name, reason='layout not declared' ) )
            logger.info( "Dependency [{}] has no storage_paths(); skipped".format( as_info( name ) ) )

    return owned, skips


def default_dependency_names( cuppa_env ):
    """Names Phase 3 treats as known to this build (default_dependencies only for now)."""
    return list( cuppa_env.get( 'default_dependencies' ) or [] )
