#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency storage actions — list (and later remove) dependency trees
#-------------------------------------------------------------------------------

"""Opt-in actions that report or remove what cuppa wrote under ``dependencies_root``.

Listings and removals run instead of a build. Report body goes to stdout (mode banner via the logger).
"""

import os
import sys

from cuppa.colourise import as_emphasised, as_error, as_info, as_info_label, as_subdued
from cuppa.core import (
    dependency_identity,
    dependency_inventory,
    dependency_removal,
    dependency_storage,
    dependency_tree,
)
from cuppa.log import logger
from cuppa.utility import storage


INDENT = '  '
RULE = '-'

COLUMNS = [
    ( 'size', 'SIZE' ),
    ( 'type', 'TYPE' ),
    ( 'dependency', 'DEPENDENCY' ),
    ( 'qualifier', 'VERSION / BRANCH' ),
    ( 'tool_variant', 'TOOLCHAIN VARIANT' ),
    ( 'last_used', 'LAST USED' ),
    ( 'state', 'STATE' ),
]


def _last_used_epoch( iso_stamp ):
    if not iso_stamp:
        return None
    from datetime import datetime, timezone
    try:
        when = datetime.strptime(
                iso_stamp.replace( 'Z', '' ), '%Y-%m-%dT%H:%M:%S'
        ).replace( tzinfo=timezone.utc )
    except ValueError:
        return None
    return when.timestamp()


def _age_epoch_for_entry( entry, path ):
    """Age for the LAST USED column.

    Prefer inventory ``last_used`` only when it was stamped by a real resolve
    (``last_used_source == 'resolve'``). Listing must not invent usage dates —
    fall back to the directory mtime (when the tree was written / last changed
    on disk). Never use ``first_seen`` (inventory creation time).
    """
    if entry.get( 'last_used_source' ) == 'resolve':
        epoch = _last_used_epoch( entry.get( 'last_used' ) )
        if epoch is not None:
            return epoch
    try:
        return os.path.getmtime( path )
    except OSError:
        return None


def _format_age_epoch( epoch ):
    if epoch is None:
        return '-'
    return storage.relative_age( epoch )


def _enrich_path( path, described ):
    return dependency_identity.enrich_described( path, dict( described ) )


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


def _backfill_gitlab_remote_locations( rows, dependencies_root, by_path ):
    """Fill missing GitLab ``remote_location`` from known registry URLs.

    Disk layout alone cannot invent the registry host/project path. Fill gaps in order:

    1. Same-package sibling — any version of package *P* with a URL supplies the base for
       other versions of *P* (version segment substituted).
    2. Shared registry — when every known GitLab URL shares one registry prefix (typical for
       a company dependencies root), unreferenced packages that were never resolved in this
       listing still get ``{registry}/{package}/{version}``.

    Inferred URLs are written back to the inventory so later listings keep them.
    """
    templates = {}
    remotes = []
    for row in rows:
        if row.get( 'type' ) != 'gitlab':
            continue
        remote = row.get( 'remote_location' )
        if not remote:
            continue
        remotes.append( remote )
        package, _version = dependency_identity.gitlab_package_from_remote( remote )
        if package and package not in templates:
            templates[package] = remote
    if by_path:
        for entry in by_path.values():
            if entry.get( 'type' ) != 'gitlab':
                continue
            remote = entry.get( 'remote_location' ) or entry.get( 'source_url' )
            if not remote:
                continue
            remotes.append( remote )
            package, _version = dependency_identity.gitlab_package_from_remote( remote )
            if package and package not in templates:
                templates[package] = remote

    registry_bases = set()
    for remote in remotes:
        base = dependency_identity.gitlab_registry_base( remote )
        if base:
            registry_bases.add( base )
    shared_registry = next( iter( registry_bases ) ) if len( registry_bases ) == 1 else None

    if not templates and not shared_registry:
        return

    def _persist( row, remote ):
        row['remote_location'] = remote
        path = row.get( 'path' )
        if not path or not by_path:
            return
        real = storage.real_path( path ) if os.path.exists( path ) else path
        entry = by_path.get( real )
        if entry is None or entry.get( 'remote_location' ):
            return
        entry['remote_location'] = remote
        try:
            dependency_inventory.write_entry(
                    dependencies_root, entry, key=entry.get( '_key' )
            )
        except storage.StorageError:
            pass

    for row in rows:
        if row.get( 'type' ) != 'gitlab' or row.get( 'remote_location' ):
            continue
        package, path_version = dependency_identity.gitlab_package_from_path(
                row.get( 'path' ) or ''
        )
        if not package:
            package = row.get( 'short_name' )
        version = row.get( 'qualifier' )
        if version in ( None, '', '-' ):
            version = path_version
        if not package or not version:
            continue
        remote = None
        template = templates.get( package )
        if template:
            remote = dependency_identity.gitlab_remote_for_version( template, version )
        elif shared_registry:
            remote = dependency_identity.gitlab_remote_for_package_version(
                    shared_registry, package, version
            )
        if remote:
            _persist( row, remote )


def _collect_rows( construct, cuppa_env ):
    dependencies_root = _dependencies_root( cuppa_env )
    downloads_root = cuppa_env.get( 'downloads_root' ) or cuppa_env.get( 'cache_root' )
    exact = bool( cuppa_env.get( 'exact_sizes' ) )
    sconstruct_dir = cuppa_env.get( 'sconstruct_dir' )

    names = dependency_storage.default_dependency_names( cuppa_env )
    selections = dependency_storage.selection_build_envs( construct, cuppa_env )
    owned, skips = dependency_storage.resolve_named_dependencies(
            construct, cuppa_env, names, selections=selections
    )

    referenced = set()
    cached = set()
    for item in owned:
        if item.category == 'dependencies' and not item.develop:
            referenced.add( storage.real_path( item.path ) )
        elif item.category == 'cached':
            cached.add( storage.real_path( item.path ) )

    # Touch inventory for active dependency trees and develop-shadowed cached stems.
    for item in owned:
        if item.category not in ( 'dependencies', 'cached' ) or item.develop:
            continue
        if not os.path.isdir( item.path ):
            continue
        described = _enrich_path(
                item.path,
                {
                    'type': item.storage_type,
                    'dependency': item.dependency,
                    'qualifier': item.qualifier,
                    'tool_variant': item.tool_variant,
                },
        )
        try:
            dependency_inventory.touch_entry(
                    dependencies_root,
                    item.path,
                    storage_type=item.storage_type,
                    dependency=item.dependency,
                    qualifier=item.qualifier if item.qualifier is not None else described.get( 'qualifier' ),
                    tool_variant=item.tool_variant,
                    downloads=[
                        p.path for p in owned
                        if p.dependency == item.dependency and p.category == 'downloads'
                    ],
                    sconstruct_dir=sconstruct_dir,
                    exact_sizes=exact,
                    # Listing must not stamp last_used — that is for real resolve/build use.
                    update_last_used=False,
                    short_name=described.get( 'short_name' ),
                    stem=described.get( 'stem' ),
                    source_url=described.get( 'source_url' ) or item.remote_location,
                    remote_location=item.remote_location or described.get( 'source_url' ),
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
        # Refresh type if an older entry lacks it.
        if not entry.get( 'type' ):
            entry['type'] = dependency_storage.classify_storage_type( real, dependencies_root )
            entry['kind'] = entry['type']
        by_path[real] = entry

    for path in _walk_dependency_trees( dependencies_root ):
        real = storage.real_path( path )
        described = _enrich_path(
                path,
                dependency_storage.describe_tree_path( path, dependencies_root ),
        )
        if real in by_path:
            # Ensure walked trees keep a current type classification and identity.
            existing = by_path[real]
            if existing.get( 'type' ) in ( None, '', 'unknown' ):
                existing['type'] = described['type']
                existing['kind'] = described['type']
            changed = False
            old_short = existing.get( 'short_name' )
            new_short = described.get( 'short_name' )
            # Refresh when missing, or when an archive still carries the encoded folder.
            refresh_identity = bool( new_short ) and (
                    not old_short
                    or (
                        described.get( 'type' ) == 'archive'
                        and (
                            str( old_short ).startswith( 'https_' )
                            or old_short == existing.get( 'dependency' )
                        )
                    )
            )
            if refresh_identity:
                existing['short_name'] = new_short
                existing['stem'] = described.get( 'stem' )
                changed = True
            if described.get( 'qualifier' ) and existing.get( 'qualifier' ) in (
                    None, '', '-'
            ):
                existing['qualifier'] = described['qualifier']
                changed = True
            if described.get( 'source_url' ) and not existing.get( 'source_url' ):
                existing['source_url'] = described['source_url']
                changed = True
            if described.get( 'source_url' ) and not existing.get( 'remote_location' ):
                existing['remote_location'] = described['source_url']
                changed = True
            if changed:
                try:
                    dependency_inventory.write_entry(
                            dependencies_root, existing, key=existing.get( '_key' )
                    )
                except storage.StorageError:
                    pass
            continue
        try:
            entry = dependency_inventory.touch_entry(
                    dependencies_root,
                    path,
                    storage_type=described['type'],
                    dependency=described['dependency'],
                    qualifier=described['qualifier'],
                    tool_variant=described['tool_variant'],
                    exact_sizes=exact,
                    update_last_used=False,
                    short_name=described.get( 'short_name' ),
                    stem=described.get( 'stem' ),
                    source_url=described.get( 'source_url' ),
                    remote_location=described.get( 'source_url' ),
            )
        except storage.StorageError:
            entry = {
                'path': real,
                'type': described['type'],
                'kind': described['type'],
                'dependency': described['dependency'],
                'qualifier': described['qualifier'],
                'tool_variant': described['tool_variant'],
                'short_name': described.get( 'short_name' ),
                'stem': described.get( 'stem' ),
                'source_url': described.get( 'source_url' ),
                'last_used': None,
                'size': dependency_inventory.measure_size( path, exact=exact ),
            }
        by_path[real] = entry

    # Refresh sizes for inventoried rows when asked or stale.
    rows = []
    total_bytes = 0
    unreferenced_bytes = 0
    missing_count = 0
    estimated = False
    row_paths = set()
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
        if real in referenced:
            state = 'referenced'
        elif real in cached:
            # Present under --develop: registry identity known, checkout is the working copy.
            state = 'cached'
        else:
            state = 'unreferenced'
        if state == 'unreferenced':
            unreferenced_bytes += bytes_
        if ( size_info or {} ).get( 'method' ) == 'sampled':
            estimated = True

        storage_type = entry.get( 'type' ) or entry.get( 'kind' ) or 'unknown'
        dependency_name = entry.get( 'dependency' ) or '-'
        # Prefer registry name from resolve when the walk only had the encoded folder.
        if real in cached or real in referenced:
            for item in owned:
                if storage.real_path( item.path ) == real and item.dependency:
                    dependency_name = item.dependency
                    if item.qualifier is not None or item.category == 'cached':
                        entry['qualifier'] = item.qualifier
                    break

        if (
                not entry.get( 'short_name' )
                or (
                    storage_type == 'archive'
                    and str( entry.get( 'short_name' ) or '' ).startswith( 'https_' )
                )
        ):
            described = _enrich_path( path, {
                'type': storage_type,
                'dependency': dependency_name,
                'qualifier': entry.get( 'qualifier' ),
                'tool_variant': entry.get( 'tool_variant' ),
            } )
            entry['short_name'] = described.get( 'short_name' )
            entry['stem'] = described.get( 'stem' )
            if described.get( 'source_url' ):
                entry['source_url'] = described.get( 'source_url' )
                if not entry.get( 'remote_location' ):
                    entry['remote_location'] = described.get( 'source_url' )
            if described.get( 'qualifier' ) and entry.get( 'qualifier' ) in (
                    None, '', '-'
            ):
                entry['qualifier'] = described['qualifier']

        age_epoch = _age_epoch_for_entry( entry, path )
        remote_location = None
        package_archive = None
        for item in owned:
            if storage.real_path( item.path ) == real and item.remote_location:
                remote_location = item.remote_location
            if (
                    item.dependency == dependency_name
                    and item.category == 'downloads'
                    and item.path
            ):
                name = os.path.basename( item.path.rstrip( '\\/' ) )
                tool = entry.get( 'tool_variant' ) or item.tool_variant
                if tool and tool in name:
                    package_archive = name
                elif package_archive is None:
                    package_archive = name
        if not remote_location:
            remote_location = (
                entry.get( 'remote_location' ) or entry.get( 'source_url' )
            )
        location = dependency_identity.location_display(
                path, dependencies_root,
                source_url=remote_location or entry.get( 'source_url' ),
        )
        package_name = entry.get( 'short_name' )
        if storage_type == 'gitlab':
            from_path, _ = dependency_identity.gitlab_package_from_path( path )
            package_name = from_path or package_name
            if not package_archive:
                package_archive = dependency_identity.gitlab_archive_name(
                        package_name, entry.get( 'tool_variant' )
                )
        download_path = dependency_identity.find_cached_download(
                downloads_root,
                storage_type=storage_type,
                path=path,
                package=package_name,
                version=entry.get( 'qualifier' ),
                tool_variant=entry.get( 'tool_variant' ),
                package_archive=package_archive,
                inventory_downloads=entry.get( 'downloads' ),
        )
        rows.append( {
            'size': dependency_inventory.format_size_cell( size_info ),
            'size_bytes': bytes_,
            'type': storage_type,
            'dependency': dependency_name,
            'qualifier': entry.get( 'qualifier' ) or '-',
            'tool_variant': entry.get( 'tool_variant' ) or '-',
            'last_used': _format_age_epoch( age_epoch ),
            'last_used_epoch': age_epoch,
            'state': state,
            'path': path,
            'kind': storage_type,
            'short_name': entry.get( 'short_name' ),
            'stem': entry.get( 'stem' ),
            'source_url': entry.get( 'source_url' ),
            'remote_location': remote_location,
            'package_archive': package_archive,
            'location': location,
            'has_download': bool( download_path ),
            'download_path': download_path,
        } )
        row_paths.add( real )

    # Expected trees from resolve that are not on disk — STATE missing.
    for item in owned:
        if item.category != 'dependencies' or item.develop:
            continue
        if os.path.isdir( item.path ):
            continue
        real = storage.real_path( item.path )
        if real in row_paths:
            continue
        row_paths.add( real )
        qualifier = item.qualifier
        folder = os.path.basename( item.path.rstrip( '\\/' ) )
        stem, folder_qualifier = dependency_storage.split_location_folder_name( folder )
        if not qualifier:
            qualifier = folder_qualifier
        storage_type = item.storage_type or 'unknown'
        described = _enrich_path( item.path, {
            'type': storage_type,
            'dependency': item.dependency,
            'qualifier': qualifier,
            'tool_variant': item.tool_variant,
        } )
        # Missing trees have no .git — fall back to configured identity.
        short = described.get( 'short_name' ) or stem or item.dependency
        remote_location = item.remote_location or described.get( 'source_url' )
        package_name, _ver = dependency_identity.gitlab_package_from_remote( remote_location )
        package_archive = None
        if storage_type == 'gitlab':
            package_archive = dependency_identity.gitlab_archive_name(
                    package_name, item.tool_variant
            )
        location = dependency_identity.location_display(
                item.path, dependencies_root,
                source_url=remote_location or described.get( 'source_url' ),
        )
        download_path = dependency_identity.find_cached_download(
                downloads_root,
                storage_type=storage_type,
                path=item.path,
                package=package_name or short,
                version=qualifier,
                tool_variant=item.tool_variant,
                package_archive=package_archive,
        )
        rows.append( {
            'size': '-',
            'size_bytes': 0,
            'type': storage_type,
            'dependency': item.dependency or '-',
            'qualifier': qualifier or '-',
            'tool_variant': item.tool_variant or '-',
            'last_used': '-',
            'last_used_epoch': None,
            'state': 'missing',
            'path': item.path,
            'kind': storage_type,
            'short_name': short,
            'stem': described.get( 'stem' ) or stem,
            'source_url': described.get( 'source_url' ),
            'remote_location': remote_location,
            'package_archive': package_archive,
            'location': location,
            'has_download': bool( download_path ),
            'download_path': download_path,
        } )
        missing_count += 1

    _backfill_gitlab_remote_locations( rows, dependencies_root, by_path )

    rows.sort( key=lambda row: (
            row.get( 'dependency' ) or '',
            row.get( 'qualifier' ) or '',
            row.get( 'tool_variant' ) or '',
            row.get( 'path' ) or '',
    ) )

    tree = dependency_tree.build_tree( rows )

    return {
        'dependencies_root': dependencies_root,
        'downloads_root': downloads_root,
        'rows': rows,
        'tree': tree,
        'skips': skips,
        'total_bytes': total_bytes,
        'unreferenced_bytes': unreferenced_bytes,
        'missing_count': missing_count,
        'estimated': estimated,
        'referenced_paths': referenced,
        'has_download_marks': any( row.get( 'has_download' ) for row in rows ),
    }


def _write_ruled_table( out, columns, rows ):
    lines = storage.render_table( columns, rows )
    if not lines:
        return 0
    # Rule length follows visible columns; ANSI on subdued/info cells must not stretch it.
    width = max( storage.visible_len( line ) for line in lines )
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
    tee, elbow, _pipe, _gap = storage.glyphs()
    lines = [ "Skipped dependencies:" ]
    for index, skip in enumerate( skips ):
        last = index == len( skips ) - 1
        branch = elbow if last else tee
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
    tree = data.get( 'tree' ) or dependency_tree.build_tree( rows )
    list_format = cuppa_env.get( 'list_format' ) or 'text'
    verbose = list_format == 'verbose'

    if list_format == 'json':
        payload = {
            'dependencies_root': root,
            'tree': dependency_tree.tree_to_json( tree ),
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
                    'type': row['type'],
                    'kind': row['kind'],
                    'short_name': row.get( 'short_name' ),
                    'stem': row.get( 'stem' ),
                    'source_url': row.get( 'source_url' ),
                    'remote_location': row.get( 'remote_location' ),
                    'location': row.get( 'location' ),
                    'has_download': bool( row.get( 'has_download' ) ),
                    'download_path': row.get( 'download_path' ),
                }
                for row in rows
            ],
            'total_bytes': data['total_bytes'],
            'unreferenced_bytes': data['unreferenced_bytes'],
            'missing_count': data.get( 'missing_count' ) or 0,
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

    lines, _columns = dependency_tree.render_tree_lines( tree, verbose=verbose )
    if lines:
        width = max( storage.visible_len( line ) for line in lines )
        rule = as_subdued( INDENT + RULE * width )
        out.write( rule + "\n" )
        out.write( INDENT + lines[0] + "\n" )
        out.write( rule + "\n" )
        for line in lines[1:]:
            out.write( INDENT + line + "\n" )
        out.write( rule + "\n" )

    total = storage.human_size( data['total_bytes'] )
    unref = storage.human_size( data['unreferenced_bytes'] )
    estimate_note = ''
    if data['estimated']:
        estimate_note = '   (~ estimated; --exact-sizes measures)'
    missing = int( data.get( 'missing_count' ) or 0 )
    missing_note = ''
    if missing:
        missing_note = ', {} missing'.format( missing )
    out.write( "{}{} entries, {} total, {} unreferenced{}{}\n".format(
            INDENT,
            len( rows ),
            total,
            unref,
            missing_note,
            estimate_note,
    ) )

    for line in _render_skip_tree( data['skips'] ):
        out.write( line + "\n" )

    if data.get( 'has_download_marks' ):
        downloads_root = data.get( 'downloads_root' ) or cuppa_env.get( 'downloads_root' )
        out.write( "\n" )
        out.write(
            "{} = archive present under downloads".format(
                    as_info( dependency_identity.DOWNLOAD_MARK )
            )
        )
        if downloads_root:
            out.write( " ({})".format(
                    as_info( storage.display_path( downloads_root ) )
            ) )
        out.write( ".\n" )
        out.write(
            "If re-extracting a dependency fails, remove the corrupt archive there - "
            "deleting only the dependency tree is not enough.\n"
        )

    if any( row['state'] == 'unreferenced' for row in rows ):
        out.write( "\n" )
        out.write( "Review unreferenced trees, then remove by name with:\n\n" )
        out.write( as_emphasised( "cuppa -D --remove-dependencies=<name>" ) + "\n" )

    if any( row.get( 'state' ) == 'cached' for row in rows ):
        out.write( "\n" )
        out.write( 'You can view the state of dependencies marked as "develop" with:\n\n' )
        out.write( as_emphasised( "cuppa -D --list-develop" ) + "\n" )

    return 0


def run( construct, cuppa_env, out=None ):
    out = out or sys.stdout
    try:
        if cuppa_env.get( 'remove_all_dependencies' ) or cuppa_env.get( 'remove_dependencies' ):
            logger.info( as_info_label(
                    "Running in REMOVE DEPENDENCIES mode, no building will be attempted" ) )
            return dependency_removal.remove_dependencies( construct, cuppa_env, out=out )

        if cuppa_env.get( 'list_dependencies' ):
            logger.info( as_info_label(
                    "Running in LIST DEPENDENCIES mode, no building will be attempted" ) )
            return list_dependencies( construct, cuppa_env, out=out )
    except storage.StorageError as error:
        logger.error( as_error( str( error ) ) )
        out.write( "error: {}\n".format( error ) )
        return 1
    return 0
