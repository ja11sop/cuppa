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


_APPLY_STACK_KEY = "_cuppa_transitive_apply_stack"
# Re-export for callers / tests that imported stems helpers from this module.
__all__ = [
        "apply_transitive_build_with",
        "apply_transitive_use_libs",
        "list_linkable_lib_stems",
        "list_static_lib_stems",
]
_VERSION_PINS_KEY = "_cuppa_package_version_pins"
_TRANSITIVE_LIBS_APPLIED_KEY = "_cuppa_transitive_use_libs_applied"


def _factory_owner( factory ):
    return getattr( factory, "__self__", None )


def _factory_version( factory ):
    owner = _factory_owner( factory )
    if owner is None:
        return None
    return getattr( owner, "_version", None )


def _resolve_registry( entry_registry, parent_registry ):
    if entry_registry in ( None, "same", "" ):
        return parent_registry
    return entry_registry


def _ensure_registered( env, entry, parent_registry ):
    """Ensure ``entry['name']`` is in ``env['dependencies']``; return the name.

    Synthesizes a ``package_dependency`` factory when the name is not already
    registered. Concrete version pins must agree when the name is already present.
    """
    name = entry["name"]
    version = entry["version"]
    pins = env.setdefault( _VERSION_PINS_KEY, {} )

    if name in env.get( "dependencies", {} ):
        factory = env["dependencies"][name]
        existing = pins.get( name )
        if existing is None:
            existing = _factory_version( factory )
            if existing is not None:
                pins[name] = existing
        if existing is not None and str( existing ) != str( version ):
            raise SCons.Errors.StopError(
                "Transitive package [{}] requires version [{}] but [{}] is already "
                "registered or pinned as [{}].".format( name, version, name, existing )
            )
        pins[name] = str( version ) if existing is None else str( existing )
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
            version=version,
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
    pins[name] = str( version )
    logger.debug(
            "Registered transitive package dependency [{}] (package [{}], version [{}]) "
            "from the traveling package manifest".format(
                    as_info( name ),
                    as_notice( entry.get( "package" ) or name ),
                    as_info( str( version ) ),
            )
    )
    return name


def apply_stack( env ):
    """Return the current transitive BuildWith apply stack (may be empty)."""
    return env.get( _APPLY_STACK_KEY ) or []


def apply_transitive_build_with( env, package_dir, parent_name, parent_registry ):
    """``BuildWith`` each manifest dependency (includes / modules); detect cycles."""
    document = read_traveling_manifest( package_dir )
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
            name = _ensure_registered( env, entry, parent_registry )
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
    document = read_traveling_manifest( package_dir )
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
        name = _ensure_registered( env, entry, parent_registry )
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
