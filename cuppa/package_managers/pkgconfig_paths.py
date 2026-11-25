#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Compose pkg-config search directories from Cuppa package dependency trees.

Consume runs ``pkg-config --with-path=<P> …`` for a package that opted into
pkg-config. Installed ``.pc`` files may still ``Requires:`` modules that live
in other Cuppa extracts. This module discovers those directories so repeated
``--with-path`` flags can list them. A missing traveling ``pkg_config_dir`` on
a *dependency* may still contribute ``lib/pkgconfig`` or ``share/pkgconfig``
when that directory contains ``*.pc`` files. That fallback is only for search
path contribution — it does not turn pkg-config on for the dependency's own
``use_libs``.

See ``design/plans/pkgconfig-dependency-search-path.md``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Sequence

from cuppa.package_managers.cuppa_publish_manifest import (
        package_pkg_config_dir,
        read_traveling_manifest,
)


_FALLBACK_RELATIVE = (
        os.path.join( "lib", "pkgconfig" ),
        os.path.join( "share", "pkgconfig" ),
)


def _has_pc_files( directory: str ) -> bool:
    try:
        names = os.listdir( directory )
    except OSError:
        return False
    return any( name.endswith( ".pc" ) for name in names )


def discover_pkg_config_dir( package_dir: str | None ) -> str | None:
    """Absolute pkg-config directory for search-path contribution, or ``None``.

    Traveling ``pkg_config_dir`` wins when present. Otherwise the first of
    ``lib/pkgconfig`` / ``share/pkgconfig`` that contains ``*.pc`` is used.
    """
    if not package_dir:
        return None
    root = os.path.abspath( package_dir )
    if not os.path.isdir( root ):
        return None

    spec = package_pkg_config_dir( root )
    if spec:
        path = spec if os.path.isabs( spec ) else os.path.join( root, spec )
        path = os.path.abspath( path )
        return path if os.path.isdir( path ) else None

    for relative in _FALLBACK_RELATIVE:
        path = os.path.join( root, relative )
        if os.path.isdir( path ) and _has_pc_files( path ):
            return os.path.abspath( path )
    return None


def traveling_dependency_names( package_dir: str | None ) -> list[str]:
    """BuildWith names listed on the traveling manifest (direct edges only)."""
    if not package_dir:
        return []
    try:
        document = read_traveling_manifest( package_dir )
    except ValueError:
        return []
    if not document:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for entry in document.get( "dependencies" ) or []:
        name = entry.get( "name" ) if isinstance( entry, dict ) else None
        if not name or name in seen:
            continue
        seen.add( name )
        names.append( str( name ) )
    return names


def dependency_pkg_config_dirs(
        root_package_dir: str | None,
        resolve_package_dir: Callable[[str], str | None],
) -> list[str]:
    """Pkg-config directories for the traveling dependency closure of ``root``.

    ``resolve_package_dir(name)`` returns that dependency's package root, or
    ``None`` when it is not available. Walk is BFS and cycle-safe. The root
    package's own directory is not included — callers put the primary
    ``--with-path`` first.
    """
    if not root_package_dir:
        return []

    queue = traveling_dependency_names( root_package_dir )
    seen_names: set[str] = set()
    dirs: list[str] = []
    seen_dirs: set[str] = set()

    while queue:
        name = queue.pop( 0 )
        if name in seen_names:
            continue
        seen_names.add( name )

        package_dir = None
        try:
            package_dir = resolve_package_dir( name )
        except Exception:
            package_dir = None
        if not package_dir:
            continue

        discovered = discover_pkg_config_dir( package_dir )
        if discovered and discovered not in seen_dirs:
            seen_dirs.add( discovered )
            dirs.append( discovered )

        for child in traveling_dependency_names( package_dir ):
            if child not in seen_names:
                queue.append( child )

    return dirs


def merge_pkg_config_search_dirs(
        primary: str | None,
        dependency_dirs: Iterable[str] | None = None,
) -> list[str]:
    """Primary directory first, then dependency dirs, deduped."""
    merged: list[str] = []
    seen: set[str] = set()
    for path in [ primary, *( dependency_dirs or () ) ]:
        if not path:
            continue
        absolute = os.path.abspath( path )
        if absolute in seen:
            continue
        seen.add( absolute )
        merged.append( absolute )
    return merged


def pkg_config_with_path_args( directories: Sequence[str] ) -> str:
    """``--with-path=a --with-path=b`` (one flag per directory).

    A single ``--with-path`` with colon-separated directories is not portable
    on pkgconf; repeated flags are.
    """
    parts = []
    for path in directories:
        if path:
            parts.append( "--with-path={}".format( path ) )
    return " ".join( parts )
