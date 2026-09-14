#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Cascade build-and-publish of GitLab package dependencies
#-------------------------------------------------------------------------------

"""Opt-in nested publish of package dependencies before the tip package.

See ``design/plans/package-build-publish-deps.md``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import defaultdict, deque

import SCons.Errors

from cuppa.colourise import as_info, as_notice
from cuppa.log import logger
from cuppa.package_managers.cuppa_dependency_manifest import (
        coerce_dependency_entry,
        fill_dependency_versions,
)
from cuppa.package_managers.cuppa_publish_manifest import (
        PUBLISH_FILENAME,
        read_publish_manifest,
)


CASCADE_OPTION = "build-and-publish-dependencies"
PUBLISHER_ROOT_OPTION = "publisher-root"
NESTED_ENV = "CUPPA_CASCADE_NESTED"


def cascade_enabled( env ) -> bool:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return False
    return bool( getter( CASCADE_OPTION ) )


def publisher_root_option( env ) -> str | None:
    getter = getattr( env, "get_option", None )
    if not callable( getter ):
        return None
    value = getter( PUBLISHER_ROOT_OPTION )
    if not value:
        return None
    return os.path.expanduser( str( value ) )


def _is_nested() -> bool:
    return os.environ.get( NESTED_ENV ) == "1"


def _node_key( name: str, package: str, version: str ) -> tuple:
    return ( str( name ), str( package ), str( version ) )


def _looks_like_url( value: str ) -> bool:
    lower = value.lower()
    return lower.startswith( ( "http://", "https://", "git@", "ssh://" ) ) or lower.endswith( ".git" )


def resolve_publisher_dir( env, entry: dict ) -> str:
    """Return an existing publisher working tree for ``entry``."""
    package_source = entry.get( "package_source" )
    name = entry["name"]
    package = entry["package"]

    if package_source:
        source = os.path.expanduser( str( package_source ) )
        if _looks_like_url( source ):
            # Phase 2: clone. For MVP try publisher-root first, else StopError.
            root = publisher_root_option( env )
            resolved = _resolve_under_publisher_root( root, name, package ) if root else None
            if resolved:
                return resolved
            raise SCons.Errors.StopError(
                    "package_source for [{}] is a URL [{}]; Phase 1 cascade "
                    "requires a local working tree (set --{} or a filesystem "
                    "package_source). Clone support is Phase 2."
                    .format( name, source, PUBLISHER_ROOT_OPTION )
            )
        if not os.path.isabs( source ):
            base = env.get( "sconstruct_dir" ) or os.getcwd()
            source = os.path.abspath( os.path.join( str( base ), source ) )
        if os.path.isdir( source ):
            return source
        raise SCons.Errors.StopError(
                "package_source for [{}] is not a directory: [{}]"
                .format( name, source )
        )

    root = publisher_root_option( env )
    if not root:
        raise SCons.Errors.StopError(
                "dependency [{}] has no package_source and --{} is not set; "
                "cannot resolve a publisher working tree"
                .format( name, PUBLISHER_ROOT_OPTION )
        )
    resolved = _resolve_under_publisher_root( root, name, package )
    if resolved:
        return resolved
    raise SCons.Errors.StopError(
            "could not resolve publisher for [{}] under --{}=[{}] "
            "(tried {{root}}/{{name}}, {{root}}/{{package}}, and one-level nesting)"
            .format( name, PUBLISHER_ROOT_OPTION, root )
    )


def _resolve_under_publisher_root( root: str, name: str, package: str ) -> str | None:
    if not root or not os.path.isdir( root ):
        return None
    candidates = [
            os.path.join( root, name ),
            os.path.join( root, package ),
    ]
    for path in candidates:
        if os.path.isdir( path ) and _looks_like_publisher_tree( path ):
            return path
    try:
        children = sorted( os.listdir( root ) )
    except OSError:
        return None
    for child in children:
        child_path = os.path.join( root, child )
        if not os.path.isdir( child_path ):
            continue
        for leaf in ( name, package ):
            nested = os.path.join( child_path, leaf )
            if os.path.isdir( nested ) and _looks_like_publisher_tree( nested ):
                return nested
    return None


def _looks_like_publisher_tree( path: str ) -> bool:
    for name in ( "sconstruct", "SConstruct", PUBLISH_FILENAME ):
        if os.path.isfile( os.path.join( path, name ) ):
            return True
    return False


def _edges_from_publisher( env, publisher ) -> list[dict]:
    deps = getattr( publisher, "_dependencies", None ) or []
    if not deps:
        return []
    filled = fill_dependency_versions( env, deps ) or []
    return [ coerce_dependency_entry( item ) for item in filled ]


def _edges_from_publish_file( directory: str ) -> list[dict]:
    document = read_publish_manifest( directory )
    if not document:
        return []
    return list( document.get( "dependencies" ) or [] )


def build_cascade_graph( env, publisher ):
    """Return ``(nodes, edges)`` for the tip's package dependency DAG.

    ``nodes`` maps node_key → entry dict (includes ``_publisher_dir``).
    ``edges`` maps parent key → set of child (dependency) keys.
    """
    nodes: dict[tuple, dict] = {}
    edges: dict[tuple, set[tuple]] = defaultdict( set )
    queue: deque[dict] = deque()

    for entry in _edges_from_publisher( env, publisher ):
        if entry.get( "version" ) is None:
            raise SCons.Errors.StopError(
                    "cascade dependency [{}] has no version "
                    "(fill from BuildWith or set it explicitly)"
                    .format( entry.get( "name" ) )
            )
        queue.append( entry )

    while queue:
        entry = queue.popleft()
        key = _node_key( entry["name"], entry["package"], entry["version"] )
        if key in nodes:
            if entry.get( "package_source" ) and not nodes[key].get( "package_source" ):
                nodes[key]["package_source"] = entry["package_source"]
            continue
        nodes[key] = dict( entry )
        publisher_dir = resolve_publisher_dir( env, nodes[key] )
        nodes[key]["_publisher_dir"] = publisher_dir
        for child in _edges_from_publish_file( publisher_dir ):
            child_key = _node_key( child["name"], child["package"], child["version"] )
            edges[key].add( child_key )
            queue.append( child )

    for parent, children in list( edges.items() ):
        for child in children:
            if child not in nodes:
                raise SCons.Errors.StopError(
                        "cascade graph incomplete: [{}] requires missing node {}"
                        .format( parent, child )
                )

    return nodes, edges


def topological_publish_order( nodes: dict, edges: dict ) -> list[tuple]:
    """Leaves (no further package deps) first."""
    node_keys = list( nodes.keys() )
    waiting = { key: len( edges.get( key, () ) ) for key in node_keys }
    dependents: dict[tuple, set[tuple]] = defaultdict( set )
    for parent, children in edges.items():
        for child in children:
            dependents[child].add( parent )

    ready = deque( sorted( [ key for key, count in waiting.items() if count == 0 ], key=str ) )
    ordered: list[tuple] = []
    while ready:
        node = ready.popleft()
        ordered.append( node )
        for parent in sorted( dependents.get( node, () ), key=str ):
            waiting[parent] -= 1
            if waiting[parent] == 0:
                ready.append( parent )

    if len( ordered ) != len( node_keys ):
        raise SCons.Errors.StopError(
                "cascade dependency cycle detected among {}".format(
                        [ key for key in node_keys if key not in ordered ]
                )
        )
    return ordered


def _settings_for_nested( env ) -> dict:
    settings = dict( env.get( "configured_options" ) or {} )
    settings.pop( CASCADE_OPTION, None )
    settings.pop( PUBLISHER_ROOT_OPTION, None )
    settings.pop( "amend-package-manifest", None )
    settings["publish-package"] = True
    return settings


def _argv_from_settings( settings: dict ) -> list[str]:
    args = [ sys.executable, "-m", "cuppa", "-D" ]
    for key in sorted( settings ):
        value = settings[key]
        if value is False or value is None:
            continue
        flag = "--" + key
        if value is True:
            args.append( flag )
        elif isinstance( value, list ):
            args.append( "{}={}".format( flag, ",".join( str( item ) for item in value ) ) )
        else:
            args.append( "{}={}".format( flag, value ) )
    return args


def invalidate_package_consume_cache( env, package: str, version: str ) -> list[str]:
    """Remove download archives and extracts for ``package``/``version``.

    Cascade-internal refresh so the tip (and later siblings) do not keep stale
    same-version bits. Returns paths removed.
    """
    removed: list[str] = []
    downloads_root = env.get( "downloads_root" ) or env.get( "cache_root" )
    dependencies_root = env.get( "dependencies_root" )
    variant = None
    try:
        from cuppa.package_managers.gitlab import tool_variant
        variant = tool_variant( env )
    except Exception:
        variant = None

    if downloads_root:
        cache_dir = os.path.join( str( downloads_root ), "packages", package, str( version ) )
        if os.path.isdir( cache_dir ):
            shutil.rmtree( cache_dir )
            removed.append( cache_dir )

    if dependencies_root and variant:
        extract_pkg = os.path.join(
                str( dependencies_root ), variant, package, str( version )
        )
        if os.path.isdir( extract_pkg ):
            shutil.rmtree( extract_pkg )
            removed.append( extract_pkg )
        # Installer layout may nest under downloads/packages/.../<tool_variant>
        if downloads_root:
            alt_variant = os.path.join(
                    str( downloads_root ), "packages", package, str( version ), variant
            )
            if os.path.isdir( alt_variant ):
                shutil.rmtree( alt_variant )
                removed.append( alt_variant )

    return removed


def run_nested_publish( env, publisher_dir: str, label: str ) -> None:
    settings = _settings_for_nested( env )
    argv = _argv_from_settings( settings )
    nested_env = os.environ.copy()
    nested_env[NESTED_ENV] = "1"
    root = str( env.get( "sconstruct_dir" ) or "" )
    pythonpath_parts = []
    if root:
        pythonpath_parts.append( root )
    # Prefer the Cuppa being developed (repo) when present on PYTHONPATH.
    existing = nested_env.get( "PYTHONPATH", "" )
    if existing:
        pythonpath_parts.extend( part for part in existing.split( os.pathsep ) if part )
    # Ensure this cuppa package is importable (tests / editable install).
    cuppa_root = os.path.abspath( os.path.join( os.path.dirname( __file__ ), "..", ".." ) )
    if cuppa_root not in pythonpath_parts:
        pythonpath_parts.insert( 0, cuppa_root )
    nested_env["PYTHONPATH"] = os.pathsep.join( pythonpath_parts )

    logger.info(
            "Cascade: publishing dependency [{}] from [{}]..."
            .format( as_info( label ), as_notice( publisher_dir ) )
    )
    logger.info( "Cascade command: {}".format( as_notice( " ".join( argv ) ) ) )
    completion = subprocess.run(
            argv,
            cwd=publisher_dir,
            env=nested_env,
    )
    if completion.returncode != 0:
        raise SCons.Errors.StopError(
                "cascade publish of [{}] failed with return code [{}] "
                "(cwd={})"
                .format( label, completion.returncode, publisher_dir )
        )


def maybe_run_cascade( env, publisher ) -> None:
    """Run cascade when the flag is set; no-op for nested invokes or when unset."""
    if not cascade_enabled( env ):
        return
    if _is_nested():
        logger.info(
                "Cascade: nested invoke — skipping further "
                "--{}".format( CASCADE_OPTION )
        )
        return
    if not env.get_option( "publish-package" ):
        raise SCons.Errors.StopError(
                "--{} requires --publish-package"
                .format( CASCADE_OPTION )
        )

    tip_package = str( getattr( publisher, "_package", "" ) )
    tip_version = str( getattr( publisher, "_version", "" ) )

    nodes, edges = build_cascade_graph( env, publisher )
    if not nodes:
        logger.info(
                "Cascade: tip [{}] declares no package dependencies — nothing to publish"
                .format( as_info( tip_package ) )
        )
        return

    order = topological_publish_order( nodes, edges )
    logger.info(
            "Cascade: publishing {} package dependenc(ies) before tip [{}]=={}"
            .format( len( order ), as_info( tip_package ), as_info( tip_version ) )
    )

    for key in order:
        entry = nodes[key]
        label = "{} {} ({})".format( entry["name"], entry["version"], entry["package"] )
        run_nested_publish( env, entry["_publisher_dir"], label )
        removed = invalidate_package_consume_cache(
                env, entry["package"], entry["version"]
        )
        if removed:
            logger.info(
                    "Cascade: refreshed consume cache for [{}]: {}"
                    .format( as_info( label ), as_notice( ", ".join( removed ) ) )
            )
