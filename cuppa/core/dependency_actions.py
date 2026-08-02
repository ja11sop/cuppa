#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency storage actions — list (and later remove) dependency trees
#-------------------------------------------------------------------------------

"""Opt-in actions that report or remove what cuppa wrote under ``dependencies_root``.

Listings run instead of a build. Report body goes to stdout (mode banner via the logger).
"""

import os
import sys

from cuppa.colourise import as_emphasised, as_error, as_info, as_info_label, as_subdued
from cuppa.core import dependency_inventory, dependency_storage
from cuppa.log import logger
from cuppa.utility import storage


INDENT = '  '
RULE = '-'

COLUMNS = [
    ( 'size', 'SIZE' ),
    ( 'dependency', 'DEPENDENCY' ),
    ( 'qualifier', 'VERSION / BRANCH' ),
    ( 'tool_variant', 'TOOLCHAIN VARIANT' ),
    ( 'last_used', 'LAST USED' ),
    ( 'state', 'STATE' ),
]


def add_dependency_action_options( add_option ):
    add_option(
        '--list-dependencies', dest='list_dependencies', action='store_true',
        help="List dependency trees under the dependencies root and exit",
    )
    add_option(
        '--exact-sizes', dest='exact_sizes', action='store_true',
        help="Measure dependency tree sizes with a full walk (updates the inventory cache)",
    )
    add_option(
        '--remove-dependencies', dest='remove_dependencies', type='string', nargs=1,
        action='store',
        help="Remove named dependencies for the current selection (comma-separated), then exit",
    )
    add_option(
        '--remove-all-dependencies', dest='remove_all_dependencies', action='store_true',
        help="Remove every default dependency for the current selection, then exit",
    )


def process_dependency_action_options( cuppa_env ):
    cuppa_env['list_dependencies'] = bool( cuppa_env.get_option( 'list_dependencies' ) )
    cuppa_env['exact_sizes'] = bool( cuppa_env.get_option( 'exact_sizes' ) )
    cuppa_env['remove_all_dependencies'] = bool( cuppa_env.get_option( 'remove_all_dependencies' ) )
    remove = cuppa_env.get_option( 'remove_dependencies' )
    if isinstance( remove, ( list, tuple ) ):
        remove = remove[0] if remove else None
    cuppa_env['remove_dependencies'] = remove


def wants_dependency_action( cuppa_env ):
    return bool(
        cuppa_env.get( 'list_dependencies' )
        or cuppa_env.get( 'remove_dependencies' )
        or cuppa_env.get( 'remove_all_dependencies' )
    )


def _dependencies_root( cuppa_env ):
    root = cuppa_env.get( 'dependencies_root' )
    if not root:
        raise storage.StorageError( "dependencies_root is not configured" )
    if not os.path.isabs( root ):
        root = os.path.abspath( os.path.join( cuppa_env['sconstruct_dir'], root ) )
    return root


def _isdir( path ):
    return os.path.isdir( path ) and not os.path.islink( path )


def _walk_dependency_trees( dependencies_root ):
    """Yield ownership-unit directories under the root — never nested source folders.

    Layouts recognised:

    - ``<tool_variant>/<package>/<version>/`` — GitLab / Boost package extracts
    - ``conan/<name>/<fingerprint>/`` — Conan consumer installs
    - anything else at the top level (``git_*``, archive folders, …) — one row per
      top-level directory; do not recurse into VCS trees
    """
    if not os.path.isdir( dependencies_root ):
        return

    skip_names = { dependency_inventory.INVENTORY_DIR_NAME }

    for name in sorted( os.listdir( dependencies_root ) ):
        if name in skip_names or name.startswith( '.' ):
            continue
        top = os.path.join( dependencies_root, name )
        if not _isdir( top ):
            continue

        if name == 'conan':
            for dep_name in sorted( os.listdir( top ) ):
                dep_dir = os.path.join( top, dep_name )
                if not _isdir( dep_dir ):
                    continue
                for fingerprint in sorted( os.listdir( dep_dir ) ):
                    finger_dir = os.path.join( dep_dir, fingerprint )
                    if _isdir( finger_dir ):
                        yield finger_dir
            continue

        if dependency_storage.looks_like_tool_variant_dir( name ):
            for package in sorted( os.listdir( top ) ):
                package_dir = os.path.join( top, package )
                if not _isdir( package_dir ):
                    continue
                versions = [
                    v for v in sorted( os.listdir( package_dir ) )
                    if _isdir( os.path.join( package_dir, v ) )
                ]
                if versions:
                    for version in versions:
                        yield os.path.join( package_dir, version )
                else:
                    # Incomplete package tree — still report the package folder.
                    yield package_dir
            continue

        # Location / archive trees: the top-level folder is the ownership unit.
        yield top


def _collect_rows( construct, cuppa_env ):
    dependencies_root = _dependencies_root( cuppa_env )
    exact = bool( cuppa_env.get( 'exact_sizes' ) )
    sconstruct_dir = cuppa_env.get( 'sconstruct_dir' )

    names = dependency_storage.default_dependency_names( cuppa_env )
    selections = dependency_storage.selection_build_envs( construct, cuppa_env )
    owned, skips = dependency_storage.resolve_named_dependencies(
            construct, cuppa_env, names, selections=selections
    )

    referenced = set()
    for item in owned:
        if item.category == 'dependencies' and not item.develop:
            referenced.add( storage.real_path( item.path ) )

    # Touch inventory for referenced dependency trees that exist.
    for item in owned:
        if item.category != 'dependencies' or item.develop:
            continue
        if not os.path.isdir( item.path ):
            continue
        try:
            dependency_inventory.touch_entry(
                    dependencies_root,
                    item.path,
                    kind=item.kind,
                    dependency=item.dependency,
                    qualifier=item.qualifier,
                    tool_variant=item.tool_variant,
                    downloads=[
                        p.path for p in owned
                        if p.dependency == item.dependency and p.category == 'downloads'
                    ],
                    sconstruct_dir=sconstruct_dir,
                    exact_sizes=exact,
            )
        except storage.StorageError as error:
            skips.append( dependency_storage.Skip(
                    dependency=item.dependency, reason=str( error )
            ) )

    by_path = {}
    for entry in dependency_inventory.load_all_entries( dependencies_root ):
        path = entry.get( 'path' )
        if not path:
            continue
        real = storage.real_path( path ) if os.path.exists( path ) else path
        by_path[real] = entry

    for path in _walk_dependency_trees( dependencies_root ):
        real = storage.real_path( path )
        if real in by_path:
            continue
        described = dependency_storage.describe_tree_path( path, dependencies_root )
        size = dependency_inventory.measure_size( path, exact=exact )
        by_path[real] = {
            'path': real,
            'kind': described['kind'],
            'dependency': described['dependency'],
            'qualifier': described['qualifier'],
            'tool_variant': described['tool_variant'],
            'last_used': None,
            'size': size,
            '_provisional': True,
        }

    # Refresh sizes for inventoried rows when asked or stale.
    rows = []
    total_bytes = 0
    unreferenced_bytes = 0
    estimated = False
    for real, entry in sorted( by_path.items(), key=lambda item: (
            item[1].get( 'dependency' ) or '',
            item[1].get( 'qualifier' ) or '',
            item[1].get( 'tool_variant' ) or '',
            item[0],
    ) ):
        path = entry.get( 'path' ) or real
        if not os.path.isdir( path ):
            continue
        size_info = entry.get( 'size' )
        if (
                exact
                or not size_info
                or dependency_inventory.size_needs_refresh( entry, path )
        ):
            size_info = dependency_inventory.measure_size( path, exact=exact )
            if not entry.get( '_provisional' ):
                entry['size'] = size_info
                try:
                    dependency_inventory.write_entry( dependencies_root, entry, key=entry.get( '_key' ) )
                except storage.StorageError:
                    pass
        bytes_ = int( ( size_info or {} ).get( 'bytes' ) or 0 )
        total_bytes += bytes_
        state = 'referenced' if real in referenced else 'unreferenced'
        if state == 'unreferenced':
            unreferenced_bytes += bytes_
        if ( size_info or {} ).get( 'method' ) == 'sampled':
            estimated = True

        rows.append( {
            'size': dependency_inventory.format_size_cell( size_info ),
            'size_bytes': bytes_,
            'dependency': entry.get( 'dependency' ) or '-',
            'qualifier': entry.get( 'qualifier' ) or '-',
            'tool_variant': entry.get( 'tool_variant' ) or '-',
            'last_used': dependency_inventory.format_age( entry.get( 'last_used' ) ),
            'state': state,
            'path': path,
            'kind': entry.get( 'kind' ),
        } )

    return {
        'dependencies_root': dependencies_root,
        'rows': rows,
        'skips': skips,
        'total_bytes': total_bytes,
        'unreferenced_bytes': unreferenced_bytes,
        'estimated': estimated,
        'referenced_paths': referenced,
    }


def _write_ruled_table( out, columns, rows ):
    lines = storage.render_table( columns, rows )
    if not lines:
        return 0
    width = max( len( line ) for line in lines )
    rule = as_subdued( INDENT + RULE * width )
    out.write( rule + "\n" )
    out.write( INDENT + lines[0] + "\n" )
    out.write( rule + "\n" )
    for line in lines[1:]:
        out.write( INDENT + line + "\n" )
    out.write( rule + "\n" )
    return width


def _render_skip_tree( skips ):
    if not skips:
        return []
    glyphs = storage.glyphs()
    lines = [ "Skipped dependencies:" ]
    for index, skip in enumerate( skips ):
        last = index == len( skips ) - 1
        branch = glyphs.last if last else glyphs.mid
        lines.append( "{}{} [{}]: {}".format(
                INDENT, branch, skip.dependency, skip.reason
        ) )
    return lines


def list_dependencies( construct, cuppa_env, out=None ):
    """``--list-dependencies``. Always exits 0 unless a storage error is raised."""
    out = out or sys.stdout
    data = _collect_rows( construct, cuppa_env )
    root = data['dependencies_root']
    rows = data['rows']

    if cuppa_env.get( 'list_format' ) == 'json':
        payload = {
            'dependencies_root': root,
            'entries': [
                {
                    'size': row['size'],
                    'size_bytes': row['size_bytes'],
                    'dependency': row['dependency'],
                    'qualifier': row['qualifier'],
                    'tool_variant': row['tool_variant'],
                    'last_used': row['last_used'],
                    'state': row['state'],
                    'path': row['path'],
                    'kind': row['kind'],
                }
                for row in rows
            ],
            'total_bytes': data['total_bytes'],
            'unreferenced_bytes': data['unreferenced_bytes'],
            'skips': [
                { 'dependency': s.dependency, 'reason': s.reason } for s in data['skips']
            ],
        }
        out.write( storage.render_json_payload( payload ) + "\n" )
        return 0

    out.write( "\n" )
    out.write( "Dependencies in {}\n".format(
            as_info( storage.display_path( root ) )
    ) )
    names = dependency_storage.default_dependency_names( cuppa_env )
    if names:
        out.write( "Default dependencies: {}\n".format(
                as_info( ', '.join( names ) )
        ) )

    table_rows = []
    for row in rows:
        painted = dict( row )
        if row['state'] == 'unreferenced':
            for key in ( 'size', 'dependency', 'qualifier', 'tool_variant', 'last_used', 'state' ):
                painted[key] = as_subdued( str( row[key] ) )
        elif row['state'] == 'referenced':
            painted['dependency'] = as_info( str( row['dependency'] ) )
            painted['state'] = as_info( str( row['state'] ) )
        table_rows.append( painted )

    _write_ruled_table( out, COLUMNS, table_rows )

    total = storage.human_size( data['total_bytes'] )
    unref = storage.human_size( data['unreferenced_bytes'] )
    estimate_note = ''
    if data['estimated']:
        estimate_note = '   (~ estimated; --exact-sizes measures)'
    out.write( "{}{} entries, {} total, {} unreferenced{}\n".format(
            INDENT,
            len( rows ),
            total,
            unref,
            estimate_note,
    ) )

    for line in _render_skip_tree( data['skips'] ):
        out.write( line + "\n" )

    if any( row['state'] == 'unreferenced' for row in rows ):
        out.write( "\n" )
        out.write( "Review unreferenced trees, then remove by name with:\n\n" )
        out.write( as_emphasised( "cuppa -D --remove-dependencies=<name>" ) + "\n" )

    return 0


def run( construct, cuppa_env, out=None ):
    out = out or sys.stdout
    try:
        if cuppa_env.get( 'remove_all_dependencies' ) or cuppa_env.get( 'remove_dependencies' ):
            # Slice D — stub until removal lands.
            logger.error( as_error(
                    "--remove-dependencies / --remove-all-dependencies are not implemented yet"
            ) )
            out.write( "error: dependency removal is not implemented yet\n" )
            return 1

        if cuppa_env.get( 'list_dependencies' ):
            logger.info( as_info_label(
                    "Running in LIST DEPENDENCIES mode, no building will be attempted" ) )
            return list_dependencies( construct, cuppa_env, out=out )
    except storage.StorageError as error:
        logger.error( as_error( str( error ) ) )
        out.write( "error: {}\n".format( error ) )
        return 1
    return 0
