#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Downloads listing — hierarchical --list-downloads
#-------------------------------------------------------------------------------

"""Collect archives under ``downloads_root`` and the dependency trees they feed."""

import os

from cuppa.core import (
    dependency_identity,
    dependency_inventory,
    dependency_storage,
    dependency_tree,
)
from cuppa.utility import storage


def walk_download_files( downloads_root ):
    """Yield archive file paths under ``downloads_root`` (top-level + GitLab + toolchains)."""
    if not downloads_root or not os.path.isdir( downloads_root ):
        return
    try:
        names = sorted( os.listdir( downloads_root ) )
    except OSError:
        return
    for name in names:
        if name.startswith( '.' ):
            continue
        path = os.path.join( downloads_root, name )
        if os.path.isfile( path ):
            yield path
            continue
        if name == 'toolchains' and os.path.isdir( path ):
            try:
                identities = sorted( os.listdir( path ) )
            except OSError:
                continue
            for identity in identities:
                identity_dir = os.path.join( path, identity )
                if not os.path.isdir( identity_dir ):
                    continue
                try:
                    qualifiers = sorted( os.listdir( identity_dir ) )
                except OSError:
                    continue
                for qualifier in qualifiers:
                    qualifier_dir = os.path.join( identity_dir, qualifier )
                    if not os.path.isdir( qualifier_dir ):
                        continue
                    try:
                        archives = sorted( os.listdir( qualifier_dir ) )
                    except OSError:
                        continue
                    for archive in archives:
                        archive_path = os.path.join( qualifier_dir, archive )
                        if os.path.isfile( archive_path ):
                            yield archive_path
            continue
        if name != 'packages' or not os.path.isdir( path ):
            continue
        try:
            packages = sorted( os.listdir( path ) )
        except OSError:
            continue
        for package in packages:
            package_dir = os.path.join( path, package )
            if not os.path.isdir( package_dir ):
                continue
            try:
                versions = sorted( os.listdir( package_dir ) )
            except OSError:
                continue
            for version in versions:
                version_dir = os.path.join( package_dir, version )
                if not os.path.isdir( version_dir ):
                    continue
                try:
                    archives = sorted( os.listdir( version_dir ) )
                except OSError:
                    continue
                for archive in archives:
                    archive_path = os.path.join( version_dir, archive )
                    if os.path.isfile( archive_path ):
                        yield archive_path


def describe_download_file( path, downloads_root ):
    """Identity fields for an archive file under the downloads root."""
    real = storage.real_path( path ) if os.path.exists( path ) else path
    rel = os.path.relpath( real, storage.real_path( downloads_root ) )
    parts = [ part for part in rel.replace( '\\', '/' ).split( '/' ) if part ]
    basename = os.path.basename( real.rstrip( '\\/' ) )
    if len( parts ) >= 4 and parts[0] == 'packages':
        package = parts[1]
        version = parts[2]
        tool_variant = tool_variant_from_gitlab_archive( package, basename )
        return {
            'type': 'gitlab',
            'dependency': package,
            'short_name': package,
            'package_folder': package,
            'stem': package,
            'qualifier': version,
            'tool_variant': tool_variant,
            'archive': basename,
            'source_url': None,
            'remote_location': None,
        }
    if len( parts ) >= 4 and parts[0] == 'toolchains':
        identity = parts[1]
        qualifier = parts[2]
        return {
            'type': 'toolchain',
            'dependency': identity,
            'short_name': identity,
            'package_folder': identity,
            'stem': identity,
            'qualifier': qualifier,
            'tool_variant': None,
            'archive': basename,
            'source_url': None,
            'remote_location': None,
        }
    described = dependency_identity.enrich_described(
            basename,
            {
                'type': 'archive',
                'dependency': basename,
                'qualifier': None,
                'tool_variant': None,
            },
    )
    return {
            'type': 'archive',
            'dependency': described.get( 'short_name' ) or basename,
            'short_name': described.get( 'short_name' ) or basename,
            'package_folder': None,
            'stem': described.get( 'stem' ) or basename,
            'qualifier': described.get( 'qualifier' ),
            'tool_variant': None,
            'archive': basename,
            'source_url': described.get( 'source_url' ),
            'remote_location': described.get( 'source_url' ),
    }


def tool_variant_from_gitlab_archive( package, archive_name ):
    """Recover ``tool_variant`` from ``{package}_{os}_{tool_variant}{ext}`` when possible."""
    if not package or not archive_name:
        return None
    from cuppa.package_managers.gitlab import strip_package_archive_extension

    stem = strip_package_archive_extension( archive_name )
    prefix = package + '_'
    if not stem.startswith( prefix ):
        return None
    rest = stem[len( prefix ):]
    _system, sep, remainder = rest.partition( '_' )
    if not sep or not remainder:
        return None
    if dependency_storage.looks_like_tool_variant_dir( remainder ):
        return remainder
    return None


def matching_products( meta, products ):
    """Return product dicts that pair with a download described by ``meta``.

    Used by ``--list-downloads`` and purge so archive↔extract matching stays one place.
    Each product is a mapping with at least ``path``, ``type``, ``dependency``,
    ``short_name``, ``qualifier``, and ``tool_variant``.
    """
    matches = []
    storage_type = meta.get( 'type' )
    for product in products:
        if storage_type == 'gitlab':
            if product.get( 'type' ) != 'gitlab':
                continue
            parts = [
                    part for part in str( product.get( 'path' ) or '' ).replace( '\\', '/' ).split( '/' )
                    if part
            ]
            folder_pkg = parts[-2] if len( parts ) >= 2 else None
            meta_folder = meta.get( 'package_folder' )
            meta_names = { meta.get( 'short_name' ), meta.get( 'dependency' ), meta_folder }
            product_names = { product.get( 'short_name' ), product.get( 'dependency' ), folder_pkg }
            meta_names.discard( None )
            meta_names.discard( '' )
            product_names.discard( None )
            product_names.discard( '' )
            folder_match = bool( meta_folder and folder_pkg and meta_folder == folder_pkg )
            if not folder_match and meta_names.isdisjoint( product_names ):
                continue
            if meta.get( 'qualifier' ) and str( product.get( 'qualifier' ) or '' ) not in (
                    '', '-', str( meta.get( 'qualifier' ) )
            ):
                continue
            if meta.get( 'tool_variant' ) and product.get( 'tool_variant' ) not in (
                    None, '', '-', meta.get( 'tool_variant' )
            ):
                continue
            matches.append( product )
            continue
        if storage_type == 'toolchain':
            if product.get( 'type' ) != 'toolchain':
                continue
            meta_names = { meta.get( 'short_name' ), meta.get( 'dependency' ) }
            product_names = { product.get( 'short_name' ), product.get( 'dependency' ) }
            meta_names.discard( None )
            meta_names.discard( '' )
            product_names.discard( None )
            product_names.discard( '' )
            if meta_names.isdisjoint( product_names ):
                continue
            if meta.get( 'qualifier' ) and str( product.get( 'qualifier' ) or '' ) not in (
                    '', '-', str( meta.get( 'qualifier' ) )
            ):
                continue
            matches.append( product )
            continue
        archive_name = meta.get( 'archive' ) or ''
        product_base = os.path.basename( str( product.get( 'path' ) or '' ).rstrip( '\\/' ) )
        if archive_name and product_base == archive_name:
            matches.append( product )
    return matches


def _file_size( path ):
    try:
        return int( os.lstat( path ).st_size )
    except OSError:
        return 0


def _product_size_and_epoch( path, inventory_by_path ):
    real = storage.real_path( path ) if os.path.exists( path ) else path
    entry = inventory_by_path.get( real )
    if entry:
        size_info = entry.get( 'size' ) or {}
        bytes_ = int( size_info.get( 'bytes' ) or 0 )
        epoch = None
        last_used = entry.get( 'last_used' )
        if last_used:
            try:
                from datetime import datetime, timezone
                epoch = datetime.strptime(
                        last_used.replace( 'Z', '' ), '%Y-%m-%dT%H:%M:%S'
                ).replace( tzinfo=timezone.utc ).timestamp()
            except ValueError:
                epoch = None
        if not epoch:
            try:
                epoch = os.lstat( path ).st_mtime
            except OSError:
                epoch = None
        return bytes_, epoch
    if not os.path.isdir( path ):
        return 0, None
    size_info = dependency_inventory.measure_size( path, exact=False )
    try:
        epoch = os.lstat( path ).st_mtime
    except OSError:
        epoch = None
    return int( size_info.get( 'bytes' ) or 0 ), epoch


def _product_label( storage_type, path, qualifier, tool_variant, dependencies_root, short_name=None ):
    if storage_type == 'gitlab' and tool_variant:
        return dependency_identity.with_extract_mark( tool_variant )
    if storage_type == 'archive':
        version = qualifier or ''
        name = short_name or ''
        if not name or name in ( '-', ):
            try:
                rel = os.path.relpath(
                        storage.real_path( path ),
                        storage.real_path( dependencies_root ),
                ).replace( '\\', '/' )
            except ValueError:
                rel = os.path.basename( path.rstrip( '\\/' ) )
            name = ( rel.split( '/' )[0] if rel else 'extract' )
        if version and version not in ( '-', '' ):
            return dependency_identity.with_extract_mark( '{}/{}'.format( name, version ) )
        return dependency_identity.with_extract_mark(
                name or os.path.basename( path.rstrip( '\\/' ) )
        )
    if qualifier and qualifier not in ( '-', '' ):
        return dependency_identity.with_extract_mark(
                dependency_identity.display_qualifier( qualifier, storage_type )
        )
    return dependency_identity.with_extract_mark(
            os.path.basename( path.rstrip( '\\/' ) ) or path
    )


def collect_download_rows( construct, cuppa_env ):
    """Return listing data for ``--list-downloads``."""
    dependencies_root = cuppa_env.get( 'dependencies_root' )
    if dependencies_root and not os.path.isabs( dependencies_root ):
        dependencies_root = os.path.abspath(
                os.path.join( cuppa_env.get( 'sconstruct_dir' ) or os.getcwd(), dependencies_root )
        )
    downloads_root = cuppa_env.get( 'downloads_root' ) or cuppa_env.get( 'cache_root' )
    if downloads_root and not os.path.isabs( downloads_root ):
        downloads_root = os.path.abspath(
                os.path.join( cuppa_env.get( 'sconstruct_dir' ) or os.getcwd(), downloads_root )
        )

    names = dependency_storage.default_dependency_names( cuppa_env )
    selections = dependency_storage.selection_build_envs( construct, cuppa_env )
    owned, skips = dependency_storage.resolve_named_dependencies(
            construct, cuppa_env, names, selections=selections
    )

    owned_downloads = []
    owned_products = []
    for item in owned:
        if item.category == 'downloads' and item.path:
            owned_downloads.append( item )
        elif item.category in ( 'dependencies', 'cached' ) and item.path:
            owned_products.append( item )

    gitlab_folder_to_registry = {}
    for item in list( owned_downloads ) + list( owned_products ):
        if item.storage_type != 'gitlab' or not item.dependency:
            continue
        folder = None
        if item.category == 'downloads' and item.path and downloads_root and os.path.exists( item.path ):
            folder = describe_download_file( item.path, downloads_root ).get( 'package_folder' )
        elif item.path and dependencies_root:
            described = dependency_storage.describe_tree_path( item.path, dependencies_root )
            if described.get( 'type' ) == 'gitlab':
                folder = described.get( 'dependency' )
        if folder:
            gitlab_folder_to_registry[folder] = item.dependency

    inventory_by_path = {}
    if dependencies_root:
        for entry in dependency_inventory.load_all_entries( dependencies_root ):
            path = entry.get( 'path' )
            if not path:
                continue
            real = storage.real_path( path ) if os.path.exists( path ) else path
            inventory_by_path[real] = entry

    products_by_key = []
    if dependencies_root:
        from cuppa.core.dependency_actions import _walk_dependency_trees
        for path in _walk_dependency_trees( dependencies_root ):
            described = dependency_identity.enrich_described(
                    path,
                    dependency_storage.describe_tree_path( path, dependencies_root ),
            )
            real = storage.real_path( path )
            products_by_key.append( {
                    'path': real,
                    'type': described.get( 'type' ) or 'unknown',
                    'dependency': described.get( 'dependency' ),
                    'short_name': described.get( 'short_name' ),
                    'qualifier': described.get( 'qualifier' ),
                    'tool_variant': described.get( 'tool_variant' ),
                    'source_url': described.get( 'source_url' ),
                    'stem': described.get( 'stem' ),
            } )
    for item in owned_products:
        real = storage.real_path( item.path ) if os.path.exists( item.path ) else item.path
        if not real:
            continue
        if any( product['path'] == real for product in products_by_key ):
            # Prefer registry name from resolve.
            for product in products_by_key:
                if product['path'] == real and item.dependency:
                    product['dependency'] = item.dependency
                    if item.qualifier is not None:
                        product['qualifier'] = item.qualifier
                    if item.tool_variant:
                        product['tool_variant'] = item.tool_variant
            continue
        described = dependency_identity.enrich_described(
                item.path,
                {
                    'type': item.storage_type,
                    'dependency': item.dependency,
                    'qualifier': item.qualifier,
                    'tool_variant': item.tool_variant,
                },
        )
        products_by_key.append( {
                'path': real,
                'type': item.storage_type or described.get( 'type' ) or 'unknown',
                'dependency': item.dependency,
                'short_name': described.get( 'short_name' ) or item.dependency,
                'qualifier': item.qualifier if item.qualifier is not None else described.get( 'qualifier' ),
                'tool_variant': item.tool_variant or described.get( 'tool_variant' ),
                'source_url': described.get( 'source_url' ) or item.remote_location,
                'stem': described.get( 'stem' ),
        } )

    archive_files = list( walk_download_files( downloads_root ) ) if downloads_root else []
    seen_archives = set()
    rows = []

    def add_archive_row( path, meta, state ):
        real = storage.real_path( path ) if os.path.exists( path ) else path
        if real in seen_archives:
            return
        seen_archives.add( real )
        rows.append( {
            'role': 'archive',
            'size_bytes': _file_size( path ),
            'type': meta.get( 'type' ) or 'archive',
            'dependency': meta.get( 'dependency' ) or '-',
            'short_name': meta.get( 'short_name' ) or meta.get( 'dependency' ) or '-',
            'stem': meta.get( 'stem' ),
            'qualifier': meta.get( 'qualifier' ),
            'tool_variant': meta.get( 'tool_variant' ),
            'state': state,
            'path': real,
            'label': meta.get( 'archive' ) or os.path.basename( real.rstrip( '\\/' ) ),
            'location': storage.display_path( real ),
            'source_url': meta.get( 'source_url' ),
            'remote_location': meta.get( 'remote_location' ) or meta.get( 'source_url' ),
            'last_used_epoch': None,
            'package_folder': meta.get( 'package_folder' ),
        } )

    def add_product_row( product, state, dependency_name=None, short_name=None ):
        path = product['path']
        real = storage.real_path( path ) if os.path.exists( path ) else path
        size_bytes, epoch = _product_size_and_epoch( path, inventory_by_path )
        storage_type = product.get( 'type' ) or 'unknown'
        qualifier = product.get( 'qualifier' )
        tool_variant = product.get( 'tool_variant' )
        rows.append( {
            'role': 'product',
            'size_bytes': size_bytes,
            'type': storage_type,
            'dependency': dependency_name or product.get( 'dependency' ) or '-',
            'short_name': short_name or product.get( 'short_name' ) or product.get( 'dependency' ) or '-',
            'stem': product.get( 'stem' ),
            'qualifier': qualifier,
            'tool_variant': tool_variant,
            'state': state,
            'path': real,
            'label': _product_label(
                    storage_type, path, qualifier, tool_variant, dependencies_root,
                    short_name=short_name or product.get( 'short_name' ),
            ),
            'location': storage.display_path( real ),
            'source_url': product.get( 'source_url' ),
            'remote_location': product.get( 'source_url' ),
            'last_used_epoch': epoch,
        } )

    def apply_registry_name( meta ):
        folder = meta.get( 'package_folder' )
        registry = gitlab_folder_to_registry.get( folder ) if folder else None
        if registry:
            meta['dependency'] = registry
            meta['short_name'] = registry
        return meta

    def stamp_archive_epoch( archive_real, products ):
        epochs = []
        for product in products:
            _size, epoch = _product_size_and_epoch( product['path'], inventory_by_path )
            if epoch is not None:
                epochs.append( epoch )
        if not epochs:
            return
        latest = max( epochs )
        for row in rows:
            if row.get( 'role' ) == 'archive' and row.get( 'path' ) == archive_real:
                row['last_used_epoch'] = latest

    # Owned downloads first (referenced for this selection).
    for item in owned_downloads:
        if not item.path or not os.path.isfile( item.path ):
            continue
        meta = describe_download_file( item.path, downloads_root )
        if item.dependency:
            meta['dependency'] = item.dependency
            if item.storage_type == 'gitlab':
                meta['short_name'] = item.dependency
            else:
                meta['short_name'] = meta.get( 'short_name' ) or item.dependency
        if item.qualifier is not None:
            meta['qualifier'] = item.qualifier
        if item.tool_variant:
            meta['tool_variant'] = item.tool_variant
        if item.remote_location:
            meta['remote_location'] = item.remote_location
        apply_registry_name( meta )
        add_archive_row( item.path, meta, 'referenced' )
        products = matching_products( meta, products_by_key )
        for product in products:
            add_product_row(
                    product, 'referenced',
                    dependency_name=meta.get( 'dependency' ),
                    short_name=meta.get( 'short_name' ),
            )
        stamp_archive_epoch( storage.real_path( item.path ), products )

    # Remaining scan hits (unreferenced / orphans).
    for path in archive_files:
        real = storage.real_path( path )
        if real in seen_archives:
            continue
        meta = describe_download_file( path, downloads_root )
        state = 'unreferenced'
        for item in owned_products:
            found = dependency_identity.find_cached_download(
                    downloads_root,
                    storage_type=item.storage_type,
                    path=item.path,
                    package=(
                        ( meta.get( 'package_folder' ) or meta.get( 'short_name' ) )
                        if meta.get( 'type' ) == 'gitlab' else None
                    ),
                    version=item.qualifier or meta.get( 'qualifier' ),
                    tool_variant=item.tool_variant,
            )
            if found and storage.real_path( found ) == real:
                state = 'referenced'
                if item.dependency:
                    meta['dependency'] = item.dependency
                    if meta.get( 'type' ) == 'gitlab':
                        meta['short_name'] = item.dependency
                break
        apply_registry_name( meta )
        add_archive_row( path, meta, state )
        products = matching_products( meta, products_by_key )
        for product in products:
            add_product_row(
                    product, state,
                    dependency_name=meta.get( 'dependency' ),
                    short_name=meta.get( 'short_name' ),
            )
        stamp_archive_epoch( real, products )

    # Deduplicate product rows by path within the same identity grouping.
    deduped = []
    seen_product_keys = set()
    for row in rows:
        if row['role'] == 'product':
            key = ( row.get( 'short_name' ), row.get( 'path' ), row.get( 'role' ) )
            if key in seen_product_keys:
                continue
            seen_product_keys.add( key )
        deduped.append( row )
    rows = deduped

    archive_bytes = sum(
            int( row.get( 'size_bytes' ) or 0 )
            for row in rows if row.get( 'role' ) == 'archive'
    )
    unreferenced_archive_bytes = sum(
            int( row.get( 'size_bytes' ) or 0 )
            for row in rows
            if row.get( 'role' ) == 'archive' and row.get( 'state' ) == 'unreferenced'
    )
    archive_count = sum( 1 for row in rows if row.get( 'role' ) == 'archive' )

    tree = build_downloads_tree( rows )
    return {
        'dependencies_root': dependencies_root,
        'downloads_root': downloads_root,
        'rows': rows,
        'tree': tree,
        'skips': skips,
        'archive_count': archive_count,
        'total_bytes': archive_bytes,
        'unreferenced_bytes': unreferenced_archive_bytes,
    }


def build_downloads_tree( rows ):
    """Group archive/product rows into section → type → identity → leaves."""
    groups = {}
    for row in rows:
        storage_type = row.get( 'type' ) or 'unknown'
        short = row.get( 'short_name' ) or row.get( 'dependency' ) or '-'
        key = ( storage_type, short )
        group = groups.get( key )
        if group is None:
            group = {
                'type': storage_type,
                'short_name': short,
                'registry_name': None,
                'remote_location': None,
                'rows': [],
            }
            groups[key] = group
        if row.get( 'state' ) in dependency_tree.REFERENCED_STATES and row.get( 'dependency' ):
            name = row['dependency']
            if name and name != short and not str( name ).startswith( ( 'git_', 'https_' ) ):
                group['registry_name'] = name
            elif group['registry_name'] is None and name and not str( name ).startswith( ( 'git_', 'https_' ) ):
                group['registry_name'] = name
        if row.get( 'remote_location' ) and not group.get( 'remote_location' ):
            group['remote_location'] = row['remote_location']
        group['rows'].append( row )

    referenced_idents = []
    unreferenced_idents = []
    for group in groups.values():
        # Match dependency listing: any selected leaf pulls the whole identity
        # (including unused sibling archives) into the referenced section.
        pulls_referenced = any(
                row.get( 'state' ) in dependency_tree.REFERENCED_STATES
                for row in group['rows']
        )
        section = 'referenced' if pulls_referenced else 'unreferenced'
        identity = _build_downloads_identity( group, section )
        if section == 'referenced':
            referenced_idents.append( identity )
        else:
            unreferenced_idents.append( identity )

    def sort_idents( items ):
        return sorted( items, key=lambda node: (
                0 if node['type'] == 'repository' else
                1 if node['type'] == 'gitlab' else
                2 if node['type'] == 'conan' else
                3 if node['type'] == 'archive' else
                4 if node['type'] == 'toolchain' else 5,
                ( node.get( 'registry_name' ) or node.get( 'short_name' ) or '' ).lower(),
        ) )

    return {
        'sections': [
            _build_downloads_section( 'referenced', sort_idents( referenced_idents ) ),
            _build_downloads_section( 'unreferenced', sort_idents( unreferenced_idents ) ),
        ],
    }


def _archive_size( rows ):
    total = 0
    saw = False
    for row in rows:
        if row.get( 'role' ) != 'archive':
            continue
        saw = True
        total += int( row.get( 'size_bytes' ) or 0 )
    return total if saw else None


def _max_epoch( rows ):
    epoch = None
    for row in rows:
        epoch = dependency_tree._max_epoch( epoch, row.get( 'last_used_epoch' ) )
    return epoch


def _leaf_from_row( row ):
    state = row.get( 'state' )
    remark = 'in use' if state == 'referenced' and row.get( 'role' ) == 'archive' else (
            'in use' if state == 'referenced' and row.get( 'role' ) == 'product' else ''
    )
    return {
        'kind': 'leaf',
        'label': row.get( 'label' ) or '-',
        'size_bytes': int( row.get( 'size_bytes' ) or 0 ),
        'last_used_epoch': row.get( 'last_used_epoch' ),
        'remark': remark,
        'location': row.get( 'location' ) or '',
        'state': state,
        'path': row.get( 'path' ),
        'role': row.get( 'role' ),
        'tool_variant': row.get( 'tool_variant' ),
        'qualifier': row.get( 'qualifier' ),
        'children': [],
    }


def _build_downloads_identity( group, section ):
    storage_type = group['type']
    rows_in = group['rows']
    short = group['short_name']
    registry = group.get( 'registry_name' )
    remote_location = group.get( 'remote_location' )
    used = sum( 1 for row in rows_in if row.get( 'state' ) == 'referenced' and row.get( 'role' ) == 'archive' )

    if storage_type == 'gitlab':
        children = _gitlab_download_children( rows_in )
    else:
        children = _flat_download_children( rows_in )

    full_label, name_part, detail_part = dependency_tree._identity_label(
            registry, short, section, remote_location=remote_location
    )
    return {
        'kind': 'identity',
        'type': storage_type,
        'label': full_label,
        'label_name': name_part,
        'label_detail': detail_part,
        'registry_name': registry,
        'short_name': short,
        'size_bytes': _archive_size( rows_in ),
        'last_used_epoch': _max_epoch( rows_in ),
        'remark': dependency_tree._remark_for_used( used ) if used > 1 else '',
        'location': remote_location or '',
        'children': children,
        'used_count': used,
    }


def _product_matches_archive( archive, product ):
    archive_name = archive.get( 'label' ) or os.path.basename(
            str( archive.get( 'path' ) or '' ).rstrip( '\\/' )
    )
    product_base = os.path.basename( str( product.get( 'path' ) or '' ).rstrip( '\\/' ) )
    if archive_name and product_base == archive_name:
        return True
    archive_tool = archive.get( 'tool_variant' )
    if archive_tool and product.get( 'tool_variant' ) == archive_tool:
        return True
    return False


def _archive_leaves_with_extracts( archives, products ):
    remaining = list( products )
    leaves = []
    for archive in sorted( archives, key=lambda item: item.get( 'label' ) or '' ):
        leaf = _leaf_from_row( archive )
        matched = []
        unmatched = []
        for product in remaining:
            if _product_matches_archive( archive, product ):
                matched.append( product )
            else:
                unmatched.append( product )
        remaining = unmatched
        leaf['children'] = [
                _leaf_from_row( product )
                for product in sorted(
                        matched,
                        key=lambda item: item.get( 'tool_variant' ) or item.get( 'label' ) or '',
                )
        ]
        leaves.append( leaf )
    return leaves


def _gitlab_download_children( rows_in ):
    by_version = {}
    for row in rows_in:
        version = row.get( 'qualifier' ) or '-'
        by_version.setdefault( version, [] ).append( row )
    children = []
    for version in sorted( by_version.keys(), key=dependency_tree.re_split_version, reverse=True ):
        group = by_version[version]
        archives = [ row for row in group if row.get( 'role' ) == 'archive' ]
        products = [ row for row in group if row.get( 'role' ) == 'product' ]
        children.append( {
            'kind': 'version',
            'label': str( version ),
            'size_bytes': _archive_size( group ),
            'last_used_epoch': _max_epoch( group ),
            'remark': '',
            'location': '',
            'children': _archive_leaves_with_extracts( archives, products ),
        } )
    return children


def _flat_download_children( rows_in ):
    archives = [ row for row in rows_in if row.get( 'role' ) == 'archive' ]
    products = [ row for row in rows_in if row.get( 'role' ) == 'product' ]
    return _archive_leaves_with_extracts( archives, products )


_DOWNLOAD_SECTION_TITLES = {
    'referenced': 'referenced from downloads',
    'unreferenced': 'unreferenced downloads',
}


def _build_downloads_section( name, identities ):
    by_type = {}
    for identity in identities:
        by_type.setdefault( identity['type'], [] ).append( identity )
    type_nodes = []
    for type_key, type_label in dependency_tree.TYPE_LABELS:
        items = by_type.pop( type_key, [] )
        if not items:
            continue
        epoch = None
        used = sum( int( node.get( 'used_count' ) or 0 ) for node in items )
        for node in items:
            epoch = dependency_tree._max_epoch( epoch, node.get( 'last_used_epoch' ) )
        type_nodes.append( {
            'kind': 'type',
            'label': type_label,
            'size_bytes': _sum_archive_node_sizes( items ),
            'last_used_epoch': epoch,
            'remark': dependency_tree._remark_count( used, 'used' ),
            'location': '',
            'children': dependency_tree._spacer_between_identities( items ),
        } )
    for type_key, items in sorted( by_type.items() ):
        epoch = None
        for node in items:
            epoch = dependency_tree._max_epoch( epoch, node.get( 'last_used_epoch' ) )
        type_nodes.append( {
            'kind': 'type',
            'label': type_key,
            'size_bytes': _sum_archive_node_sizes( items ),
            'last_used_epoch': epoch,
            'remark': '',
            'location': '',
            'children': dependency_tree._spacer_between_identities( items ),
        } )

    epoch = None
    for node in type_nodes:
        epoch = dependency_tree._max_epoch( epoch, node.get( 'last_used_epoch' ) )

    children = []
    if type_nodes:
        children.append( dependency_tree._spacer_node() )
        children.extend( type_nodes )
    remark = ''
    if name == 'referenced' and identities:
        remark = dependency_tree._remark_count(
                sum( int( ident.get( 'used_count' ) or 0 ) for ident in identities ),
                'total',
        )
    return {
        'kind': 'section',
        'label': name,
        'display_label': _DOWNLOAD_SECTION_TITLES.get( name, name ),
        'size_bytes': _sum_archive_node_sizes( type_nodes ),
        'last_used_epoch': epoch,
        'remark': remark,
        'location': '',
        'children': children,
    }


def _sum_archive_node_sizes( nodes ):
    total = 0
    saw = False
    for node in nodes:
        value = node.get( 'size_bytes' )
        if value is None:
            continue
        saw = True
        total += int( value )
    return total if saw else None
