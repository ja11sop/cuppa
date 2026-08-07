#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency listing tree — hierarchical --list-dependencies presentation
#-------------------------------------------------------------------------------

"""Build and render the §4.9 dependency tree from enriched leaf rows."""

import os
import re

from cuppa.colourise import as_emphasised, as_error, as_info, as_subdued
from cuppa.core import dependency_inventory
from cuppa.core.dependency_identity import (
    display_qualifier,
    gitlab_archive_name,
    gitlab_package_from_remote,
    strip_vcs_qualifier,
    with_download_mark,
    with_vcs_qualifier,
)
from cuppa.utility import storage


TYPE_LABELS = (
    ( 'repository', 'repository dependencies' ),
    ( 'gitlab', 'gitlab packages' ),
    ( 'conan', 'conan packages' ),
    ( 'archive', 'source archives' ),
    ( 'toolchain', 'toolchains' ),
)

REFERENCED_STATES = frozenset( ( 'referenced', 'missing', 'cached' ) )

# Match --list-builds: fixed width, right-aligned size column.
SIZE_WIDTH = 8
RULE = '-'


def _max_epoch( left, right ):
    if left is None:
        return right
    if right is None:
        return left
    return max( left, right )


def _remark_for_used( used_count, leaf_state=None ):
    if leaf_state == 'missing':
        return 'missing'
    if leaf_state == 'cached':
        # Develop-shadowed stems: remark lives on the identity row as ``develop``.
        return ''
    if leaf_state in ( 'referenced', ):
        return 'in use'
    # Identity rollups: only call out when more than one leaf is in use.
    if used_count > 1:
        return '{} used'.format( used_count )
    return ''


def _remark_count( count, word ):
    if count <= 0:
        return ''
    return '{} {}'.format( count, word )


def _identity_label( registry_name, short_name, section, remote_location=None, missing_only=False ):
    """Return ``(full_label, name_part, detail_part)``.

    ``detail_part`` is the bracketed short name / remote location without brackets,
    or ``None`` when the label is a single token. Referenced missing-only rows prefer
    ``remote_location`` over the short name so the gap is actionable.
    """
    if missing_only and remote_location:
        detail = remote_location
    else:
        detail = short_name or registry_name or '-'
    if section == 'referenced' and registry_name:
        if detail and detail != registry_name:
            return (
                '{} [{}]'.format( registry_name, detail ),
                registry_name,
                detail,
            )
        return registry_name, registry_name, None
    label = detail or short_name or '-'
    return label, label, None


def _spacer_node():
    return {
        'kind': 'spacer',
        'label': '',
        'size_bytes': None,
        'last_used_epoch': None,
        'remark': '',
        'location': '',
        'children': [],
    }


def _iter_leaves( node ):
    if node.get( 'kind' ) == 'leaf':
        yield node
        return
    for child in node.get( 'children' ) or []:
        for leaf in _iter_leaves( child ):
            yield leaf


def _measured_size( size_bytes, state=None, remark=None ):
    """Bytes that should contribute to a rollup; missing rows do not invent 0B."""
    if state == 'missing' or remark == 'missing':
        return None
    if size_bytes is None:
        return None
    return int( size_bytes )


def _sum_measured_sizes( items, size_attr='size_bytes' ):
    total = 0
    saw = False
    for item in items:
        value = _measured_size(
                item.get( size_attr ),
                item.get( 'state' ),
                item.get( 'remark' ),
        )
        if value is None:
            continue
        saw = True
        total += value
    return total if saw else None


def build_tree( leaves ):
    """Group enriched leaves into section → type → identity → variant nodes.

    Each leaf needs: type, short_name, stem, dependency (registry), qualifier,
    tool_variant, state, size_bytes, last_used_epoch, path, source_url,
    remote_location (optional), location.
    """
    groups = {}  # (type, group_key) -> dict

    for leaf in leaves:
        storage_type = leaf.get( 'type' ) or 'unknown'
        short = leaf.get( 'short_name' ) or leaf.get( 'stem' ) or leaf.get( 'dependency' ) or '-'
        # Prefer short_name as the stable family key so boost_package and disk boost/ meet.
        group_key = short
        key = ( storage_type, group_key )
        group = groups.get( key )
        if group is None:
            group = {
                'type': storage_type,
                'short_name': short,
                'registry_name': None,
                'remote_location': None,
                'leaves': [],
            }
            groups[key] = group
        if leaf.get( 'state' ) in REFERENCED_STATES and leaf.get( 'dependency' ):
            # Prefer a real registry name over an encoded folder.
            name = leaf['dependency']
            if (
                    name
                    and name != short
                    and not name.startswith( 'git_' )
                    and not name.startswith( 'https_' )
            ):
                group['registry_name'] = name
            elif (
                    group['registry_name'] is None
                    and name
                    and not name.startswith( 'git_' )
                    and not name.startswith( 'https_' )
            ):
                group['registry_name'] = name
        if leaf.get( 'remote_location' ) and not group.get( 'remote_location' ):
            group['remote_location'] = leaf['remote_location']
        elif leaf.get( 'source_url' ) and not group.get( 'remote_location' ):
            group['remote_location'] = leaf['source_url']
        group['leaves'].append( leaf )

    referenced_idents = []
    unreferenced_idents = []

    for group in groups.values():
        leaves_in = group['leaves']
        pulls_referenced = any( leaf.get( 'state' ) in REFERENCED_STATES for leaf in leaves_in )
        section = 'referenced' if pulls_referenced else 'unreferenced'
        identity = _build_identity( group, section )
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
            _build_section( 'referenced', sort_idents( referenced_idents ) ),
            _build_section( 'unreferenced', sort_idents( unreferenced_idents ) ),
        ],
    }


def _build_identity( group, section ):
    storage_type = group['type']
    leaves_in = group['leaves']
    short = group['short_name']
    registry = group.get( 'registry_name' )
    remote_location = group.get( 'remote_location' )

    if storage_type == 'gitlab':
        children = _gitlab_children( leaves_in )
    elif storage_type == 'repository':
        children = _location_children( leaves_in )
    elif storage_type == 'conan':
        children = _flat_variant_children( leaves_in, label_key='qualifier' )
    elif storage_type == 'archive':
        children = _archive_children( leaves_in )
    elif storage_type == 'toolchain':
        children = _flat_variant_children( leaves_in, label_key='qualifier' )
    else:
        children = _flat_variant_children( leaves_in, label_key='qualifier' )

    used = sum( 1 for leaf in leaves_in if leaf.get( 'state' ) == 'referenced' )
    missing = sum( 1 for leaf in leaves_in if leaf.get( 'state' ) == 'missing' )
    develop = sum( 1 for leaf in leaves_in if leaf.get( 'state' ) == 'cached' )
    size_bytes = sum( int( leaf.get( 'size_bytes' ) or 0 ) for leaf in leaves_in )
    epoch = None
    for leaf in leaves_in:
        epoch = _max_epoch( epoch, leaf.get( 'last_used_epoch' ) )
    remark = ''
    missing_only = bool( missing ) and used == 0
    # Keep ``missing`` on the leaf only so REMARK counts one entry per gap.
    # Under --develop, shadowed stems are blank on the branch; the identity says ``develop``.
    if develop and used == 0 and not missing_only:
        remark = 'develop'
    elif used > 1:
        remark = _remark_for_used( used )

    # LOCATION (verbose): location identities show the bare repository URL (no branch);
    # each leaf carries URL@branch. GitLab identity stays blank — version holds the registry URL.
    location = ''
    if storage_type == 'repository':
        base = remote_location or ''
        if not base:
            for leaf in leaves_in:
                base = leaf.get( 'remote_location' ) or leaf.get( 'source_url' ) or ''
                if base:
                    break
        if base:
            stripped = strip_vcs_qualifier( base )
            # Prefer a clean repo URL without a trailing bare '@'.
            location = stripped[:-1] if stripped.endswith( '@' ) else stripped
    elif storage_type not in ( 'gitlab', 'archive', 'toolchain' ) and len( leaves_in ) == 1:
        leaf = leaves_in[0]
        location = (
            leaf.get( 'remote_location' )
            or leaf.get( 'source_url' )
            or remote_location
            or ''
        )

    full_label, name_part, detail_part = _identity_label(
            registry, short, section,
            remote_location=remote_location or (
                leaves_in[0].get( 'source_url' ) if leaves_in else ''
            ) or location,
            missing_only=missing_only,
    )
    return {
        'kind': 'identity',
        'type': storage_type,
        'label': full_label,
        'label_name': name_part,
        'label_detail': detail_part,
        'registry_name': registry,
        'short_name': short,
        'size_bytes': None if missing_only else size_bytes,
        'last_used_epoch': None if missing_only else epoch,
        'remark': remark,
        'missing': missing_only,
        'location': location,
        'children': children,
        'used_count': used,
    }


def _location_children( leaves_in ):
    by_qual = {}
    for leaf in leaves_in:
        qual = display_qualifier( leaf.get( 'qualifier' ), 'repository' )
        by_qual.setdefault( qual, [] ).append( leaf )
    children = []
    # `@` (unspecified) first, then alpha.
    for qual in sorted( by_qual.keys(), key=lambda q: ( 0 if q == '@' else 1, q ) ):
        group = by_qual[qual]
        # One folder per qualifier for locations (tool_variant usually blank).
        for leaf in sorted( group, key=lambda item: item.get( 'path' ) or '' ):
            base = (
                leaf.get( 'remote_location' )
                or leaf.get( 'source_url' )
                or ''
            )
            if base:
                loc = with_vcs_qualifier( base, leaf.get( 'qualifier' ) )
            else:
                loc = leaf.get( 'location' ) or leaf.get( 'path' ) or ''
            children.append( _leaf_node(
                    leaf,
                    label=qual,
                    location=with_download_mark( loc, leaf.get( 'has_download' ) ),
            ) )
    return children


def _gitlab_children( leaves_in ):
    by_version = {}
    for leaf in leaves_in:
        version = leaf.get( 'qualifier' ) or '-'
        by_version.setdefault( version, [] ).append( leaf )
    children = []
    # Descending version-ish sort: try numeric tuples, else reverse alpha.
    def version_key( text ):
        parts = []
        for piece in re_split_version( text ):
            parts.append( piece )
        return parts

    for version in sorted( by_version.keys(), key=version_key, reverse=True ):
        variants = by_version[version]
        size_bytes = sum( int( leaf.get( 'size_bytes' ) or 0 ) for leaf in variants )
        epoch = None
        used = 0
        missing = 0
        for leaf in variants:
            epoch = _max_epoch( epoch, leaf.get( 'last_used_epoch' ) )
            if leaf.get( 'state' ) == 'referenced':
                used += 1
            elif leaf.get( 'state' ) == 'missing':
                missing += 1
        # Version row: registry/package/version. Toolchain leaf: archive basename.
        version_location = ''
        for leaf in variants:
            if leaf.get( 'remote_location' ):
                version_location = leaf['remote_location']
                break
        package_name, _version = gitlab_package_from_remote( version_location )
        if not package_name:
            # Path shape: …/<tool_variant>/<package>/<version>
            for leaf in variants:
                path = leaf.get( 'path' ) or ''
                parts = [ p for p in path.replace( '\\', '/' ).split( '/' ) if p ]
                if len( parts ) >= 2:
                    package_name = parts[-2]
                    break
        version_has_download = any( leaf.get( 'has_download' ) for leaf in variants )
        tool_children = []
        for leaf in sorted( variants, key=lambda item: item.get( 'tool_variant' ) or '' ):
            archive = leaf.get( 'package_archive' )
            download_path = leaf.get( 'download_path' )
            if download_path:
                archive = os.path.basename( str( download_path ).rstrip( '\\/' ) )
            if not archive:
                archive = gitlab_archive_name(
                        package_name, leaf.get( 'tool_variant' )
                )
            tool_children.append( _leaf_node(
                    leaf,
                    label=leaf.get( 'tool_variant' ) or '-',
                    location=with_download_mark(
                            archive or '', leaf.get( 'has_download' )
                    ),
            ) )
        missing_only = bool( missing ) and used == 0 and missing == len( variants )
        remark = _remark_for_used( used ) if used else ''
        children.append( {
            'kind': 'version',
            'label': str( version ),
            'size_bytes': None if missing_only else size_bytes,
            'last_used_epoch': None if missing_only else epoch,
            'remark': remark,
            # Registry URL is not a downloads-root archive — [D] belongs on toolchain leaves.
            'location': version_location,
            'has_download': version_has_download,
            'children': tool_children,
        } )
    return children


def re_split_version( text ):
    text = str( text or '' )
    numbers = re.findall( r'\d+', text )
    if numbers:
        return [ int( n ) for n in numbers ]
    return [ text ]


def _archive_children( leaves_in ):
    """Version leaves for HTTP/Boost archives; LOCATION prefers the remote URL."""
    children = []
    for leaf in sorted( leaves_in, key=lambda item: (
            re_split_version( item.get( 'qualifier' ) ),
            item.get( 'path' ) or '',
    ) ):
        label = display_qualifier( leaf.get( 'qualifier' ), 'archive' )
        location = (
            leaf.get( 'remote_location' )
            or leaf.get( 'source_url' )
            or leaf.get( 'location' )
            or ''
        )
        children.append( _leaf_node(
                leaf,
                label=label,
                location=with_download_mark( location, leaf.get( 'has_download' ) ),
        ) )
    return children


def _flat_variant_children( leaves_in, label_key='qualifier' ):
    children = []
    for leaf in sorted( leaves_in, key=lambda item: (
            str( item.get( label_key ) or '' ),
            item.get( 'path' ) or '',
    ) ):
        label = display_qualifier( leaf.get( label_key ), leaf.get( 'type' ) or 'archive' )
        if leaf.get( 'type' ) == 'conan':
            label = leaf.get( 'qualifier' ) or '-'
        children.append( _leaf_node( leaf, label=label ) )
    return children


def _leaf_node( leaf, label, location=None ):
    state = leaf.get( 'state' )
    remark = ''
    if state == 'missing':
        remark = 'missing'
    elif state == 'referenced':
        remark = 'in use'
    # state == 'cached': blank — identity row carries ``develop`` instead.
    missing = state == 'missing'
    if location is None:
        location = leaf.get( 'location' ) or leaf.get( 'path' ) or ''
        location = with_download_mark( location, leaf.get( 'has_download' ) )
    return {
        'kind': 'leaf',
        'label': label,
        'size_bytes': None if missing else int( leaf.get( 'size_bytes' ) or 0 ),
        'last_used_epoch': None if missing else leaf.get( 'last_used_epoch' ),
        'remark': remark,
        'location': location,
        'has_download': bool( leaf.get( 'has_download' ) ),
        'state': state,
        'path': leaf.get( 'path' ),
        'children': [],
    }


def _spacer_between_identities( identities ):
    """Blank row below the type heading and between each dependency."""
    children = [ _spacer_node() ]
    for index, identity in enumerate( identities ):
        if index > 0:
            children.append( _spacer_node() )
        children.append( identity )
    return children


def _build_section( name, identities ):
    # Nest identities under type group rows.
    by_type = {}
    for identity in identities:
        by_type.setdefault( identity['type'], [] ).append( identity )
    type_nodes = []
    for type_key, type_label in TYPE_LABELS:
        items = by_type.pop( type_key, [] )
        if not items:
            continue
        epoch = None
        used = sum( int( node.get( 'used_count' ) or 0 ) for node in items )
        for node in items:
            epoch = _max_epoch( epoch, node.get( 'last_used_epoch' ) )
        type_nodes.append( {
            'kind': 'type',
            'label': type_label,
            'size_bytes': _sum_measured_sizes( items ),
            'last_used_epoch': epoch,
            'remark': _remark_count( used, 'used' ),
            'location': '',
            'children': _spacer_between_identities( items ),
        } )
    for type_key, items in sorted( by_type.items() ):
        size_bytes = _sum_measured_sizes( items )
        epoch = None
        for node in items:
            epoch = _max_epoch( epoch, node.get( 'last_used_epoch' ) )
        type_nodes.append( {
            'kind': 'type',
            'label': type_key,
            'size_bytes': size_bytes,
            'last_used_epoch': epoch,
            'remark': '',
            'location': '',
            'children': _spacer_between_identities( items ),
        } )

    size_bytes = _sum_measured_sizes( type_nodes )
    epoch = None
    used = 0
    for node in type_nodes:
        epoch = _max_epoch( epoch, node.get( 'last_used_epoch' ) )
        for child in node.get( 'children' ) or []:
            used += int( child.get( 'used_count' ) or 0 )

    children = []
    remark = ''
    if name == 'referenced' and type_nodes:
        used_bytes = None
        unused_bytes = None
        missing_bytes = None
        used_epoch = None
        unused_epoch = None
        missing_epoch = None
        used_count = 0
        unused_count = 0
        missing_count = 0
        used_saw = False
        unused_saw = False
        missing_saw = False
        for type_node in type_nodes:
            for leaf in _iter_leaves( type_node ):
                leaf_bytes = _measured_size(
                        leaf.get( 'size_bytes' ),
                        leaf.get( 'state' ),
                        leaf.get( 'remark' ),
                )
                leaf_epoch = leaf.get( 'last_used_epoch' )
                state = leaf.get( 'state' )
                if state == 'referenced':
                    used_count += 1
                    if leaf_bytes is not None:
                        used_saw = True
                        used_bytes = ( used_bytes or 0 ) + leaf_bytes
                    used_epoch = _max_epoch( used_epoch, leaf_epoch )
                elif state == 'missing':
                    # Expected by this project but absent — not "stale".
                    missing_count += 1
                    if leaf_bytes is not None:
                        missing_saw = True
                        missing_bytes = ( missing_bytes or 0 ) + leaf_bytes
                    missing_epoch = _max_epoch( missing_epoch, leaf_epoch )
                else:
                    unused_count += 1
                    if leaf_bytes is not None:
                        unused_saw = True
                        unused_bytes = ( unused_bytes or 0 ) + leaf_bytes
                    unused_epoch = _max_epoch( unused_epoch, leaf_epoch )
        if not used_saw:
            used_bytes = None
        if not unused_saw:
            unused_bytes = None
        if not missing_saw:
            missing_bytes = None
        total = used_count + unused_count + missing_count
        remark = _remark_count( total, 'total' )
        children.append( _spacer_node() )
        if used_count:
            children.append( {
                'kind': 'summary',
                'label': 'dependencies in use',
                'size_bytes': used_bytes,
                'last_used_epoch': used_epoch,
                'remark': _remark_count( used_count, 'used' ),
                'location': '',
                'children': [],
            } )
        if missing_count:
            children.append( {
                'kind': 'summary',
                'label': 'missing dependencies',
                'size_bytes': missing_bytes,
                'last_used_epoch': missing_epoch,
                'remark': _remark_count( missing_count, 'missing' ),
                'state': 'missing',
                'location': '',
                'children': [],
            } )
        if unused_count:
            children.append( {
                'kind': 'summary',
                'label': 'potentially stale dependencies',
                'size_bytes': unused_bytes,
                'last_used_epoch': unused_epoch,
                'remark': _remark_count( unused_count, 'unused' ),
                'location': '',
                'children': [],
            } )
        children.append( _spacer_node() )

    for index, type_node in enumerate( type_nodes ):
        # Empty row above each type group. Referenced already has a spacer after
        # the used/unused summaries before the first type.
        if name != 'referenced' or index > 0:
            children.append( _spacer_node() )
        wrapped = dict( type_node )
        # Spacers between identities are already in type_node children.
        children.append( wrapped )

    return {
        'kind': 'section',
        'label': name,
        'size_bytes': size_bytes,
        'last_used_epoch': epoch,
        'remark': remark,
        'location': '',
        'children': children,
        'used_count': used,
    }


def tree_to_json( tree ):
    """Serializable nested structure for ``--list-format=json``."""

    def convert( node ):
        if node.get( 'kind' ) == 'spacer':
            return None
        payload = {
            'kind': node.get( 'kind' ),
            'label': node.get( 'label' ),
            'size_bytes': node.get( 'size_bytes' ),
            'size': _size_text(
                    node.get( 'size_bytes' ), node.get( 'kind' ),
                    node.get( 'state' ), node.get( 'remark' ),
            ).strip(),
            'last_used': (
                '-' if node.get( 'state' ) == 'missing' or node.get( 'remark' ) == 'missing'
                else (
                    dependency_inventory.format_age(
                            _epoch_to_iso( node.get( 'last_used_epoch' ) )
                    ) if node.get( 'last_used_epoch' ) else (
                        '-' if node.get( 'kind' ) == 'leaf' else ''
                    )
                )
            ),
            'remark': node.get( 'remark' ) or '',
            'location': node.get( 'location' ) or '',
        }
        if node.get( 'path' ):
            payload['path'] = node['path']
        if node.get( 'state' ):
            payload['state'] = node['state']
        if node.get( 'short_name' ):
            payload['short_name'] = node['short_name']
        if node.get( 'registry_name' ):
            payload['registry_name'] = node['registry_name']
        if node.get( 'label_detail' ):
            payload['label_detail'] = node['label_detail']
        if node.get( 'missing' ):
            payload['missing'] = True
        if node.get( 'role' ):
            payload['role'] = node['role']
        if node.get( 'display_label' ):
            payload['display_label'] = node['display_label']
        children = []
        for child in node.get( 'children' ) or []:
            converted = convert( child )
            if converted is not None:
                children.append( converted )
        if children:
            payload['children'] = children
        return payload

    return {
        'sections': [
            payload for payload in (
                convert( section ) for section in tree.get( 'sections' ) or []
            ) if payload is not None
        ],
    }


def _epoch_to_iso( epoch ):
    if epoch is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp( epoch, tz=timezone.utc ).strftime( '%Y-%m-%dT%H:%M:%SZ' )


def _size_text( size_bytes, kind=None, state=None, remark=None ):
    if kind == 'spacer':
        return ''.rjust( SIZE_WIDTH )
    if state == 'missing' or remark == 'missing':
        text = '-'
    elif size_bytes is None:
        text = '-'
    else:
        text = storage.human_size( int( size_bytes ) )
    return text.rjust( SIZE_WIDTH )


def _mute_row_fields( label, size, last_used, remark, location ):
    if label:
        label = as_subdued( label )
    if size.strip():
        size = as_subdued( size )
    if last_used:
        last_used = as_subdued( last_used )
    if remark:
        remark = as_subdued( remark )
    if location:
        location = as_subdued( location )
    return label, size, last_used, remark, location


def _colour_identity_label( name, detail, accent, detail_accent=None ):
    """Colour the registry name; style the bracketed short name / remote separately."""
    if not name:
        return ''
    coloured_name = accent( name ) if name else name
    if detail:
        detail_fn = detail_accent or as_subdued
        return coloured_name + detail_fn( ' [{}]'.format( detail ) )
    return coloured_name


def _emphasised_info( text ):
    return as_emphasised( as_info( text ) )


def _emphasised_error( text ):
    return as_emphasised( as_error( text ) )


def _emphasised_normal( text ):
    return as_emphasised( text )


def _error_row_fields( label, size, last_used, remark, location ):
    if label:
        label = as_error( label )
    if size.strip():
        size = as_error( size )
    if last_used:
        last_used = as_error( last_used )
    if remark:
        remark = as_error( remark )
    if location:
        location = as_error( location )
    return label, size, last_used, remark, location


def render_tree_lines( tree, verbose=False, tree_header='DEPENDENCY' ):
    """Return ``(lines, columns)`` for the dependency tree text view."""
    columns = [
        ( 'size', 'SIZE'.rjust( SIZE_WIDTH ) ),
        ( 'last_used', 'LAST USED' ),
        ( 'remark', 'REMARK' ),
        ( 'dependency', tree_header ),
    ]
    if verbose:
        columns.append( ( 'location', 'LOCATION' ) )

    rows = []
    tee, elbow, pipe, gap = storage.glyphs()

    def walk( node, prefix, is_last, is_root=False, section=None, under_missing=False ):
        kind = node.get( 'kind' )
        if kind == 'section':
            section = node.get( 'label' )
        missing_identity = bool( kind == 'identity' and node.get( 'missing' ) )
        row_missing = under_missing or missing_identity
        state = node.get( 'state' )
        remark = node.get( 'remark' ) or ''
        if kind == 'spacer':
            # Hanging continuation only — no tee/elbow.
            stem = ( prefix + pipe ).rstrip() if prefix else pipe.rstrip()
            rows.append( {
                'size': ''.rjust( SIZE_WIDTH ),
                'last_used': '',
                'remark': '',
                'stem': stem,
                'label': '',
                'location': '',
                '_kind': kind,
                '_state': None,
                '_section': section,
                '_label_name': None,
                '_label_detail': None,
                '_missing_identity': False,
                '_under_missing': under_missing,
            } )
            return
        if is_root:
            stem = ''
            label = node.get( 'display_label' ) or node.get( 'label' ) or ''
        else:
            branch = elbow if is_last else tee
            stem = prefix + branch
            label = node.get( 'label' ) or ''
        size = _size_text( node.get( 'size_bytes' ), kind, state, remark )
        if state == 'missing' or remark == 'missing' or missing_identity:
            last_used = '-'
        elif node.get( 'last_used_epoch' ) is not None:
            last_used = dependency_inventory.format_age(
                    _epoch_to_iso( node.get( 'last_used_epoch' ) )
            )
        elif kind in ( 'leaf', 'summary' ) or node.get( 'size_bytes' ) is None:
            last_used = '-'
        else:
            last_used = ''
        rows.append( {
            'size': size,
            'last_used': last_used,
            'remark': remark,
            'stem': stem,
            'label': label,
            'location': node.get( 'location' ) or '',
            '_kind': kind,
            '_state': state,
            '_section': section,
            '_label_name': node.get( 'label_name' ),
            '_label_detail': node.get( 'label_detail' ),
            '_missing_identity': missing_identity,
            '_under_missing': row_missing,
        } )
        children = node.get( 'children' ) or []
        child_prefix = '' if is_root else prefix + ( gap if is_last else pipe )
        child_missing = under_missing or missing_identity
        for index, child in enumerate( children ):
            walk(
                    child, child_prefix, index == len( children ) - 1,
                    is_root=False, section=section, under_missing=child_missing,
            )

    sections = [
            section for section in tree.get( 'sections' ) or []
            if section.get( 'children' )
    ]
    for index, section in enumerate( sections ):
        if index > 0:
            rows.append( {
                'size': '',
                'last_used': '',
                'remark': '',
                'stem': '',
                'label': '',
                'location': '',
                '_kind': 'partition',
                '_state': None,
                '_section': None,
                '_label_name': None,
                '_label_detail': None,
                '_missing_identity': False,
                '_under_missing': False,
            } )
        walk( section, '', True, is_root=True )

    structure = []
    table_rows = []
    for row in rows:
        kind = row.get( '_kind' )
        if kind == 'partition':
            structure.append( 'partition' )
            continue
        structure.append( 'row' )

        stem = row.get( 'stem' ) or ''
        label = row.get( 'label' ) or ''
        size = row['size']
        last_used = row['last_used']
        remark = row['remark']
        location = row.get( 'location' ) or ''
        section = row.get( '_section' )
        label_name = row.get( '_label_name' )
        label_detail = row.get( '_label_detail' )

        if kind == 'spacer':
            dependency = as_subdued( stem ) if stem else ''
            table_rows.append( {
                'size': size,
                'last_used': last_used,
                'remark': remark,
                'dependency': dependency,
                'location': location,
            } )
            continue

        if row.get( '_missing_identity' ):
            # Missing dependency name: emphasised error; bracket detail error (not emphasised).
            if label_name:
                label = _colour_identity_label(
                        label_name, label_detail, _emphasised_error, detail_accent=as_error
                )
            else:
                label = _emphasised_error( label ) if label else label
            if size.strip():
                size = as_error( size )
            if last_used:
                last_used = as_error( last_used )
            if location:
                location = as_error( location )
        elif row.get( '_under_missing' ) or remark == 'missing' or row.get( '_state' ) == 'missing':
            # Subnodes under a missing dependency: error, not emphasised.
            label, size, last_used, remark, location = _error_row_fields(
                    label, size, last_used, remark, location
            )
        elif section == 'unreferenced':
            if kind == 'identity':
                if label_name:
                    label = _colour_identity_label(
                            label_name, label_detail, _emphasised_normal
                    )
                else:
                    label = _emphasised_normal( label ) if label else label
            elif kind == 'leaf':
                label, size, last_used, remark, location = _mute_row_fields(
                        label, size, last_used, remark, location
                )
        elif section == 'referenced':
            if kind == 'identity':
                if label_name:
                    label = _colour_identity_label(
                            label_name, label_detail, _emphasised_info
                    )
                else:
                    label = _emphasised_info( label ) if label else label
                # Size / age on the name row are secondary to the in-use leaf.
                if size.strip():
                    size = as_subdued( size )
                if last_used:
                    last_used = as_subdued( last_used )
                if remark in ( 'develop', 'in use' ):
                    remark = as_info( remark )
            elif kind == 'version':
                # Version rollups are secondary to the toolchain / variant leaf.
                if size.strip():
                    size = as_subdued( size )
                if last_used:
                    last_used = as_subdued( last_used )
            elif kind == 'summary' or remark == 'in use':
                if kind == 'summary' and 'stale' in ( label or '' ):
                    label, size, last_used, remark, location = _mute_row_fields(
                            label, size, last_used, remark, location
                    )
                else:
                    label = as_info( label ) if label else label
                    if remark:
                        remark = as_info( remark )
                    if location:
                        location = as_info( location )
                    if kind == 'summary' and size.strip():
                        size = as_info( size )
            elif kind == 'leaf':
                label, size, last_used, remark, location = _mute_row_fields(
                        label, size, last_used, remark, location
                )
            # section / type: normal colour (layout structure).

        # Tree glyphs stay muted regardless of row accent (same as --list-builds).
        dependency = ( as_subdued( stem ) if stem else '' ) + label
        table_rows.append( {
            'size': size,
            'last_used': last_used,
            'remark': remark,
            'dependency': dependency,
            'location': location,
        } )

    table_lines = storage.render_table( columns, table_rows )
    header = table_lines[0]
    body = table_lines[1:]
    width = max( storage.visible_len( line ) for line in table_lines ) if table_lines else 0
    lines = [ header ]
    body_index = 0
    for entry in structure:
        if entry == 'partition':
            lines.append( as_subdued( RULE * width ) )
        else:
            lines.append( body[body_index] )
            body_index += 1

    return lines, columns
