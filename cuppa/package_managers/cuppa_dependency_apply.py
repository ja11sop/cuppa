#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Apply traveling package manifest edges during GitLab package BuildWith / use_libs.

Prefers ``cuppa-publish.json``; falls back to legacy ``cuppa-dependency.json``.
"""

from __future__ import annotations

import SCons.Errors
import SCons.Script

from cuppa.colourise import as_info, as_notice
from cuppa.log import logger
from cuppa.package_managers.cuppa_publish_manifest import read_traveling_manifest
from cuppa.package_managers.package_link_libs import (
        list_linkable_lib_stems,
        list_static_lib_stems,
)
from cuppa.package_managers.package_version_bound import (
        VersionBoundConflict,
        VersionBoundError,
        intersect_version_bounds,
        parse_version_bound,
        version_satisfies,
)


_APPLY_STACK_KEY = "_cuppa_transitive_apply_stack"
# Re-export for callers / tests that imported stems helpers from this module.
__all__ = [
        "apply_transitive_build_with",
        "apply_transitive_use_libs",
        "list_linkable_lib_stems",
        "list_static_lib_stems",
]
_VERSION_PINS_KEY = "_cuppa_package_version_pins"
_VERSION_PIN_PARENTS_KEY = "_cuppa_package_version_pin_parents"
_TRANSITIVE_LIBS_APPLIED_KEY = "_cuppa_transitive_use_libs_applied"


def _factory_owner( factory ):
    return getattr( factory, "__self__", None )


def _factory_version( factory ):
    owner = _factory_owner( factory )
    if owner is None:
        return None
    return getattr( owner, "_version", None )


def _set_factory_version( factory, version ):
    owner = _factory_owner( factory )
    if owner is not None:
        owner._version = version


def _bound_token_for_factory( bound ):
    """Version string stored on the package_dependency class before resolve."""
    if bound.is_exact:
        return str( bound.version )
    return bound.display()


def _resolve_registry( entry_registry, parent_registry ):
    if entry_registry in ( None, "same", "" ):
        return parent_registry
    return entry_registry


def _parse_entry_bound( entry, parent_name ):
    raw = entry.get( "version" )
    try:
        return parse_version_bound( raw )
    except VersionBoundError as error:
        raise SCons.Errors.StopError(
                "Transitive package [{}] from [{}] has an invalid version: {}".format(
                        entry.get( "name" ),
                        parent_name or "?",
                        error,
                )
        ) from error


def _ensure_registered( env, entry, parent_registry, parent_name=None ):
    """Ensure ``entry['name']`` is in ``env['dependencies']``; return the name.

    Version edges use the bound grammar (exact / ``>=`` / ``latest``). Declared
    bounds are intersected in the env pin table; incompatible diamonds raise
    ``StopError`` naming both parents.
    """
    name = entry["name"]
    new_bound = _parse_entry_bound( entry, parent_name )
    pins = env.setdefault( _VERSION_PINS_KEY, {} )
    parents = env.setdefault( _VERSION_PIN_PARENTS_KEY, {} )

    if name in env.get( "dependencies", {} ):
        factory = env["dependencies"][name]
        existing = pins.get( name )
        if existing is None:
            factory_version = _factory_version( factory )
            if factory_version is not None:
                try:
                    existing = parse_version_bound( factory_version )
                except VersionBoundError as error:
                    raise SCons.Errors.StopError(
                            "Package [{}] is already registered with an invalid "
                            "version [{}]: {}".format(
                                    name, factory_version, error
                            )
                    ) from error
                pins[name] = existing
                parents.setdefault( name, [] ).append( "(registered)" )

        if existing is not None:
            try:
                merged = intersect_version_bounds( existing, new_bound )
            except VersionBoundConflict as conflict:
                prior = parents.get( name ) or []
                raise SCons.Errors.StopError(
                        "Transitive package [{}] version conflict: {} "
                        "(requested by [{}] as [{}]; already pinned as [{}] "
                        "from [{}]).".format(
                                name,
                                conflict,
                                parent_name or "?",
                                new_bound.display(),
                                existing.display(),
                                ", ".join( str( item ) for item in prior ) or "?",
                        )
                ) from conflict

            factory_version = _factory_version( factory )
            factory_bound = None
            if factory_version is not None:
                try:
                    factory_bound = parse_version_bound( factory_version )
                except VersionBoundError:
                    factory_bound = None
                if (
                        factory_bound is not None
                        and factory_bound.is_exact
                        and not version_satisfies( merged, factory_bound.version )
                ):
                    prior = parents.get( name ) or []
                    raise SCons.Errors.StopError(
                            "Transitive package [{}] version conflict: already "
                            "resolved as [{}] which does not satisfy [{}] "
                            "(requested by [{}]; prior pins from [{}]).".format(
                                    name,
                                    factory_bound.display(),
                                    merged.display(),
                                    parent_name or "?",
                                    ", ".join( str( item ) for item in prior ) or "?",
                            )
                    )

            pins[name] = merged
            if parent_name:
                parents.setdefault( name, [] ).append( parent_name )

            # Soft factory tokens track the intersected bound until default_version.
            # Exact concrete factories that still satisfy the merge are left alone.
            if factory_bound is None or factory_bound.is_soft:
                _set_factory_version( factory, _bound_token_for_factory( merged ) )
            return name

        pins[name] = new_bound
        if parent_name:
            parents.setdefault( name, [] ).append( parent_name )
        return name

    registry = _resolve_registry( entry.get( "registry" ), parent_registry )
    if not registry:
        raise SCons.Errors.StopError(
            "Cannot synthesize transitive package [{}]: parent registry is unknown "
            "and the manifest entry does not name a registry.".format( name )
        )

    from cuppa.build_with_package import package_dependency

    Factory = package_dependency(
            name,
            registry=registry,
            package=entry.get( "package" ) or name,
            version=_bound_token_for_factory( new_bound ),
    )
    # Declared package_dependency types register CLI options at cuppa.run()
    # time. Synthesized transitive factories skip that path, so package_info's
    # GetOption('<name>-package-manager') AttributeErrors unless we AddOption
    # here. Late registration is fine: unset options read as None and class
    # defaults (gitlab, version from the factory) still apply.
    # add_options is idempotent for the same dependency name (multi-toolchain
    # variant envs clone ``dependencies`` and re-enter synthesis).
    Factory.add_options( SCons.Script.AddOption )
    env.setdefault( "dependencies", {} )[name] = Factory.create
    pins[name] = new_bound
    if parent_name:
        parents.setdefault( name, [] ).append( parent_name )
    else:
        parents.setdefault( name, [] ).append( "(manifest)" )
    logger.debug(
            "Registered transitive package dependency [{}] (package [{}], version [{}]) "
            "from the traveling package manifest".format(
                    as_info( name ),
                    as_notice( entry.get( "package" ) or name ),
                    as_info( new_bound.display() ),
            )
    )
    return name


def apply_stack( env ):
    """Return the current transitive BuildWith apply stack (may be empty)."""
    return env.get( _APPLY_STACK_KEY ) or []


def _read_traveling_or_stop( package_dir, parent_name ):
    try:
        return read_traveling_manifest( package_dir )
    except ValueError as error:
        raise SCons.Errors.StopError(
                "Traveling package manifest under [{}] (package [{}]) is invalid: "
                "{}".format( package_dir, parent_name or "?", error )
        ) from error


def apply_transitive_build_with( env, package_dir, parent_name, parent_registry ):
    """``BuildWith`` each manifest dependency (includes / modules); detect cycles."""
    document = _read_traveling_or_stop( package_dir, parent_name )
    if not document:
        return
    dependencies = document.get( "dependencies" ) or []
    if not dependencies:
        return

    stack = env.setdefault( _APPLY_STACK_KEY, [] )
    if parent_name in stack:
        cycle = " -> ".join( stack + [ parent_name ] )
        raise SCons.Errors.StopError(
            "Cycle in transitive GitLab package dependencies: {}".format( cycle )
        )

    stack.append( parent_name )
    try:
        for entry in dependencies:
            name = _ensure_registered(
                    env, entry, parent_registry, parent_name=parent_name
            )
            if name in stack:
                cycle = " -> ".join( stack + [ name ] )
                raise SCons.Errors.StopError(
                    "Cycle in transitive GitLab package dependencies: {}".format( cycle )
                )
            logger.debug(
                    "Applying transitive BuildWith [{}] for package [{}]".format(
                            as_info( name ),
                            as_notice( parent_name ),
                    )
            )
            env.BuildWith( name )
    finally:
        stack.pop()


def apply_transitive_use_libs( env, package_dir, parent_name, parent_registry ):
    """Apply each manifest edge's ``use_libs`` against the dependency (once per parent)."""
    document = _read_traveling_or_stop( package_dir, parent_name )
    if not document:
        return

    applied = env.setdefault( _TRANSITIVE_LIBS_APPLIED_KEY, set() )
    if parent_name in applied:
        return
    applied.add( parent_name )

    for entry in document.get( "dependencies" ) or []:
        use_libs = entry.get( "use_libs" ) or []
        if not use_libs:
            continue
        name = _ensure_registered(
                env, entry, parent_registry, parent_name=parent_name
        )
        dependency = env.BuildWith( name )
        # BuildWith returns a single object or a list
        if isinstance( dependency, list ):
            if not dependency:
                raise SCons.Errors.StopError(
                    "Transitive package [{}] for [{}] could not be created.".format(
                            name, parent_name
                    )
                )
            dependency = dependency[0]
        use = getattr( dependency, "use_libs", None )
        if not callable( use ):
            raise SCons.Errors.StopError(
                "Transitive package [{}] does not support use_libs "
                "(required by [{}]'s traveling package manifest).".format(
                        name, parent_name
                )
            )
        logger.debug(
                "Applying transitive use_libs {} on [{}] for package [{}]".format(
                        as_info( str( use_libs ) ),
                        as_info( name ),
                        as_notice( parent_name ),
                )
        )
        use( use_libs )
