#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Resolve package layout paths from BuildWith
#-------------------------------------------------------------------------------

"""Look up GitLab (and similar) package dirs after ``env.BuildWith`` / auto-enable.

Safe to call ``BuildWith`` again for a name already auto-enabled: Cuppa caches
the underlying package object. Raises ``BuildWithException`` / ``StopError`` when
the dependency is missing or has no ``package_dir``.

Callers may pass a BuildWith **name** string or a dependency / package object
that exposes ``name()``.
"""

from __future__ import annotations

import os

import SCons.Errors

from cuppa.utility.types import is_string


def resolve_build_with_name( name_or_dep ):
    """Return the Cuppa BuildWith registry name for a string or dependency object."""
    if is_string( name_or_dep ):
        return str( name_or_dep )
    name_attr = getattr( name_or_dep, 'name', None )
    if name_attr is None:
        raise SCons.Errors.StopError(
                "Expected a package name string or dependency with name(); got {!r}"
                .format( name_or_dep )
        )
    try:
        resolved = name_attr() if callable( name_attr ) else name_attr
    except Exception as error:
        raise SCons.Errors.StopError(
                "dependency name() failed: {}".format( error )
        )
    if not is_string( resolved ) or not resolved:
        raise SCons.Errors.StopError(
                "dependency name() must return a non-empty string (got {!r})"
                .format( resolved )
        )
    return str( resolved )


def build_with_dependency( env, name_or_dep ):
    """Return the dependency object from ``env.BuildWith`` (single name)."""
    name = resolve_build_with_name( name_or_dep )
    dependency = env.BuildWith( name )
    if isinstance( dependency, ( list, tuple ) ):
        if len( dependency ) != 1:
            raise ValueError(
                    "BuildWith([{!r}]) returned {} dependencies; expected one"
                    .format( name, len( dependency ) )
            )
        dependency = dependency[0]
    return dependency


def underlying_package( dependency ):
    """Return the package manager object (``dependency.package()`` when present)."""
    package_fn = getattr( dependency, 'package', None )
    if callable( package_fn ):
        return package_fn()
    return dependency


def package_version( env, name_or_dep ):
    """Concrete version string for a BuildWith package dependency."""
    name = resolve_build_with_name( name_or_dep )
    package = underlying_package( build_with_dependency( env, name ) )
    version_fn = getattr( package, 'version', None )
    if callable( version_fn ):
        version = version_fn()
    else:
        version = getattr( package, '_version', None )
    if version is None:
        raise SCons.Errors.StopError(
                "Package [{}] has no version() for publisher dependency fill"
                .format( name )
        )
    return str( version )


def package_dir( env, name_or_dep ):
    """Absolute package root (``…/<name>/<version>``) for ``name_or_dep``."""
    name = resolve_build_with_name( name_or_dep )
    package = underlying_package( build_with_dependency( env, name ) )
    dir_fn = getattr( package, 'package_dir', None )
    if not callable( dir_fn ):
        raise SCons.Errors.StopError(
                "Package [{}] has no package_dir()".format( name )
        )
    return str( dir_fn() )


def package_lib( env, name_or_dep ):
    """``lib/`` under the package root."""
    name = resolve_build_with_name( name_or_dep )
    package = underlying_package( build_with_dependency( env, name ) )
    lib_fn = getattr( package, 'lib_dir', None )
    if callable( lib_fn ):
        return str( lib_fn() )
    return os.path.join( package_dir( env, name ), 'lib' )


def package_bin( env, name_or_dep, *parts ):
    """Path under the package ``bin/`` directory (``parts`` joined when given)."""
    root = os.path.join( package_dir( env, name_or_dep ), 'bin' )
    if parts:
        return os.path.join( root, *( str( part ) for part in parts ) )
    return root
