#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Storage actions — list and remove builds
#-------------------------------------------------------------------------------

"""Opt-in actions that report or remove what cuppa wrote under the build root.

Listings and removals run instead of a build: resolve selection, report, act, exit. Scope follows
the same toolchain and variant options that decide where a build writes. Artefacts outside
`build_root` are deliberately out of scope.
"""

import os
import re
import sys
from collections import defaultdict

import SCons.Script

from cuppa.colourise import (
    as_emphasised,
    as_error,
    as_info,
    as_info_label,
    as_remove_error,
    as_remove_notice,
    as_subdued,
    as_warning,
)
from cuppa.core import build_layout
from cuppa.log import logger
from cuppa.utility import storage


INDENT = '  '
RULE = '-'
# Shared across all three sections so SIZE / middle / tree columns share one grid.
SIZE_WIDTH = 8
# Fits "LAST BUILD", "SELECTED", ages such as "2 months ago", and centered marks.
MIDDLE_WIDTH = 12


def add_storage_action_options( add_option ):

    add_option(
        '--list-builds', dest='list_builds', action='store_true',
        help="List build trees under the build root (folder, toolchain, sconscript views) and exit",
    )
    add_option(
        '--remove-builds', dest='remove_builds', action='store_true',
        help="Remove every variant subtree under the build root that matches the current"
             " toolchain / variant selection, then exit",
    )
    add_option(
        '--remove-all-builds', dest='remove_all_builds', action='store_true',
        help="Remove the entire build root, then exit",
    )
    add_option(
        '--list-format', dest='list_format', choices=( 'text', 'verbose', 'json' ),
        nargs=1, action='store', default='text',
        help="Output format for --list-* options: text (default), verbose (text plus "
             "LOCATION for --list-dependencies), or json",
    )
    from cuppa.core import dependency_actions
    dependency_actions.add_dependency_action_options( add_option )


def process_storage_action_options( cuppa_env ):
    cuppa_env['list_builds'] = bool( cuppa_env.get_option( 'list_builds' ) )
    cuppa_env['remove_builds'] = bool( cuppa_env.get_option( 'remove_builds' ) )
    cuppa_env['remove_all_builds'] = bool( cuppa_env.get_option( 'remove_all_builds' ) )
    list_format = cuppa_env.get_option( 'list_format', default='text' )
    if isinstance( list_format, ( list, tuple ) ):
        list_format = list_format[0] if list_format else 'text'
    cuppa_env['list_format'] = list_format or 'text'
    from cuppa.core import dependency_actions
    dependency_actions.process_dependency_action_options( cuppa_env )


def wants_storage_action( cuppa_env ):
    from cuppa.core import dependency_actions
    return bool(
        cuppa_env.get( 'list_builds' )
        or cuppa_env.get( 'remove_builds' )
        or cuppa_env.get( 'remove_all_builds' )
        or dependency_actions.wants_dependency_action( cuppa_env )
    )


def dry_run( cuppa_env ):
    """SCons ``-n`` / ``--no-exec``: report what would be removed, remove nothing."""
    try:
        return bool( SCons.Script.GetOption( 'no_exec' ) )
    except Exception:
        return bool( cuppa_env.get_option( 'no_exec' ) )


def selected_tool_variant_dirs( construct, cuppa_env ):
    """Tool-variant path suffixes the current options would write."""
    suffixes = []
    for toolchain in cuppa_env.get( 'active_toolchains' ) or []:
        for build_env in construct.create_build_envs( toolchain, cuppa_env ):
            suffixes.append( build_layout.tool_variant_dir(
                toolchain.name(),
                build_env['variant'],
                build_env['target_arch'],
                build_env['abi'],
            ) )
    # Unique, stable order.
    seen = set()
    ordered = []
    for suffix in suffixes:
        key = os.path.normpath( suffix )
        if key not in seen:
            seen.add( key )
            ordered.append( suffix )
    return ordered


def _split_tool_variant( tool_variant ):
    """``toolchain`` and ``variant/arch/abi`` — the collapse used in the sconscript tree."""
    parts = tool_variant.split( os.sep )
    if len( parts ) < 4:
        return tool_variant, ''
    return parts[0], os.path.join( *parts[1:] )


def _sconscript_segments( entry ):
    toolchain, rest = _split_tool_variant( entry['tool_variant'] )
    sconscript = entry['sconscript']
    if sconscript == '.':
        return [ toolchain, rest ]
    return sconscript.split( os.sep ) + [ toolchain, rest ]


def _max_mtime( left, right ):
    if left is None:
        return right
    if right is None:
        return left
    return max( left, right )


class _TreeNode( object ):
    __slots__ = (
        'name', 'children', 'size_bytes', 'mtime', 'selected', 'selection',
        'result', 'is_leaf', 'is_sconscript_name', 'is_toolchain',
    )

    def __init__( self, name ):
        self.name = name
        self.children = {}
        self.size_bytes = 0
        self.mtime = None
        self.selected = False
        self.selection = 'none'
        self.result = 'none'
        self.is_leaf = False
        self.is_sconscript_name = False
        self.is_toolchain = False


def _combine_results( results ):
    """Roll child removal results up to a parent: removed, failed, mixed, or none."""
    active = [ result for result in results if result != 'none' ]
    if not active:
        return 'none'
    if all( result == 'removed' for result in active ):
        return 'removed'
    if all( result == 'failed' for result in active ):
        return 'failed'
    return 'mixed'


def _sconscript_path_parts( sconscript ):
    if sconscript == '.':
        return []
    return sconscript.split( os.sep )


def _child_names( node ):
    """Toolchain children first, then remaining folders, each group alphabetically."""
    return sorted(
        node.children,
        key=lambda name: ( 0 if node.children[name].is_toolchain else 1, name ),
    )


def _build_sconscript_tree( entries ):
    root = _TreeNode( '' )
    for entry in entries:
        parts = _sconscript_path_parts( entry['sconscript'] )
        toolchain, rest = _split_tool_variant( entry['tool_variant'] )
        segments = parts + [ toolchain, rest ]
        node = root
        for index, segment in enumerate( segments ):
            if segment not in node.children:
                node.children[segment] = _TreeNode( segment )
            node = node.children[segment]
            # The last sconscript path segment is the sconscript "name" (parent of toolchains).
            if parts and index == len( parts ) - 1:
                node.is_sconscript_name = True
            if index == len( parts ):
                node.is_toolchain = True
        node.is_leaf = True
        node.size_bytes = entry['size_bytes']
        node.mtime = entry.get( 'mtime' )
        node.selected = entry['selected']
        node.selection = 'full' if entry['selected'] else 'none'
        node.result = entry.get( 'result' ) or 'none'

    def rollup( node ):
        if node.is_leaf and not node.children:
            return node.size_bytes, node.mtime, node.selection, node.result
        total = 0
        newest = None
        child_selections = []
        child_results = []
        for child in node.children.values():
            size, mtime, selection, result = rollup( child )
            total += size
            newest = _max_mtime( newest, mtime )
            child_selections.append( selection )
            child_results.append( result )
        node.size_bytes = total
        node.mtime = newest
        if child_selections and all( status == 'full' for status in child_selections ):
            node.selection = 'full'
        elif child_selections and all( status == 'none' for status in child_selections ):
            node.selection = 'none'
        else:
            node.selection = 'partial'
        node.selected = node.selection == 'full'
        node.result = _combine_results( child_results )
        return total, newest, node.selection, node.result

    rollup( root )
    return root


def _tree_to_json( node ):
    children = [
        _tree_to_json( node.children[name] )
        for name in _child_names( node )
    ]
    payload = {
        'name': node.name,
        'size': storage.human_size( node.size_bytes ),
        'size_bytes': node.size_bytes,
        'last_build': storage.relative_age( node.mtime ),
        'mtime': node.mtime,
        'selected': node.selected,
        'selection': node.selection,
        'result': node.result,
        'sconscript_name': node.is_sconscript_name,
        'toolchain': node.is_toolchain,
    }
    if children:
        payload['children'] = children
    return payload


def _collect_variant_rows( abs_build_root, selected_suffixes ):
    variants = build_layout.discover_build_variants( abs_build_root, selected_suffixes )
    rows = []
    for entry in variants:
        stats = storage.directory_stats( entry.path )
        rows.append( {
            'size': storage.human_size( stats.bytes ),
            'size_bytes': stats.bytes,
            'mtime': stats.mtime,
            'last_build': storage.relative_age( stats.mtime ),
            'sconscript': entry.sconscript,
            'tool_variant': entry.tool_variant,
            'selected': entry.selected,
            'path': entry.path,
        } )
    return rows


def _collect_all_variant_rows( abs_build_root ):
    """Every variant under the build root, all marked selected (for --remove-all-builds)."""
    rows = _collect_variant_rows( abs_build_root, selected_suffixes=() )
    for row in rows:
        row['selected'] = True
    return rows


def _toolchain_name( tool_variant ):
    return tool_variant.split( os.sep )[0]


def _variant_arch_abi( tool_variant ):
    parts = tool_variant.split( os.sep )
    if len( parts ) < 4:
        return os.path.join( *parts[1:] ) if len( parts ) > 1 else tool_variant
    return os.path.join( *parts[1:] )


def _selection_from_children( child_selections ):
    if child_selections and all( status == 'full' for status in child_selections ):
        return 'full'
    if child_selections and all( status == 'none' for status in child_selections ):
        return 'none'
    return 'partial'


def _toolchain_variant_tree( rows ):
    """Roll up rows into ``toolchain → variant/arch/abi`` nodes for the toolchain section."""
    groups = defaultdict( lambda: {
        'size_bytes': 0, 'mtime': None, 'selected': False, 'result': 'none',
    } )
    for row in rows:
        group = groups[row['tool_variant']]
        group['size_bytes'] += row['size_bytes']
        group['mtime'] = _max_mtime( group['mtime'], row['mtime'] )
        group['selected'] = group['selected'] or row['selected']
        group['result'] = _combine_results( [
            group['result'], row.get( 'result' ) or 'none'
        ] )

    by_toolchain = defaultdict( list )
    for tool_variant in sorted( groups ):
        group = groups[tool_variant]
        selected = group['selected']
        by_toolchain[_toolchain_name( tool_variant )].append( {
            'name': _variant_arch_abi( tool_variant ),
            'tool_variant': tool_variant,
            'size': storage.human_size( group['size_bytes'] ),
            'size_bytes': group['size_bytes'],
            'mtime': group['mtime'],
            'last_build': storage.relative_age( group['mtime'] ),
            'selected': selected,
            'selection': 'full' if selected else 'none',
            'result': group['result'] if selected else 'none',
            'children': [],
        } )

    tree = []
    for toolchain in sorted( by_toolchain ):
        children = by_toolchain[toolchain]
        selection = _selection_from_children( [ child['selection'] for child in children ] )
        result = _combine_results( [ child['result'] for child in children ] )
        size_bytes = sum( child['size_bytes'] for child in children )
        mtime = None
        for child in children:
            mtime = _max_mtime( mtime, child['mtime'] )
        tree.append( {
            'name': toolchain,
            'tool_variant': toolchain,
            'size': storage.human_size( size_bytes ),
            'size_bytes': size_bytes,
            'mtime': mtime,
            'last_build': storage.relative_age( mtime ),
            'selected': selection == 'full',
            'selection': selection,
            'result': result,
            'children': children,
        } )
    return tree


def _toolchain_variant_to_json( node ):
    payload = {
        'name': node['name'],
        'tool_variant': node['tool_variant'],
        'size': node['size'],
        'size_bytes': node['size_bytes'],
        'last_build': node['last_build'],
        'mtime': node['mtime'],
        'selected': node['selected'],
        'selection': node['selection'],
        'result': node.get( 'result', 'none' ),
    }
    if node.get( 'children' ):
        payload['children'] = [
            _toolchain_variant_to_json( child ) for child in node['children']
        ]
    return payload


def _folder_summary( abs_build_root, rows ):
    folder = storage.directory_stats( abs_build_root )
    selected = [ row for row in rows if row['selected'] ]
    selected_bytes = sum( row['size_bytes'] for row in selected )
    selected_mtime = None
    for row in selected:
        selected_mtime = _max_mtime( selected_mtime, row['mtime'] )
    return {
        'path': abs_build_root,
        'display_path': storage.display_path( abs_build_root ),
        'size': storage.human_size( folder.bytes ),
        'size_bytes': folder.bytes,
        'mtime': folder.mtime,
        'last_build': storage.relative_age( folder.mtime ),
        'entries': len( rows ),
        'selected_entries': len( selected ),
        'selected_size': storage.human_size( selected_bytes ),
        'selected_bytes': selected_bytes,
        'selected_mtime': selected_mtime,
        'selected_last_build': storage.relative_age( selected_mtime ),
    }


def _size_cell( size_bytes ):
    return storage.human_size( size_bytes ).rjust( SIZE_WIDTH )


def _middle_cell( text ):
    return text.ljust( MIDDLE_WIDTH )


def _age_cell( mtime ):
    return _middle_cell( storage.relative_age( mtime ) )


def _mark_cell( text ):
    """Place a mark under the SELECTED heading (one column left of field-centre)."""
    if not text:
        return ' ' * MIDDLE_WIDTH
    centered = text.center( MIDDLE_WIDTH )
    if centered.startswith( ' ' ):
        return centered[1:] + ' '
    return centered


def _node_selected_cell( node ):
    """Leaves use a single check; rollups use the full / partial / blank triple."""
    if node.is_leaf:
        return _mark_cell( storage.selected_mark() if node.selected else '' )
    if node.selection == 'none':
        return _mark_cell( '' )
    return _mark_cell( storage.selection_triple( node.selection ) )


def _node_outcome_cell( node ):
    """Removal report marks: check for success, ballot for failure."""
    if node.is_leaf:
        if node.result == 'removed':
            return _mark_cell( storage.selected_mark() )
        if node.result == 'failed':
            return _mark_cell( storage.failed_mark() )
        return _mark_cell( '' )
    if node.result == 'none' or node.selection == 'none':
        return _mark_cell( '' )
    return _mark_cell( storage.outcome_triple( node.selection, node.result ) )


def _accent_for_result( result ):
    if result == 'failed':
        return 'remove_error'
    if result in ( 'removed', 'mixed' ):
        return 'remove_notice'
    return 'info'


def _paint( text, dim ):
    return as_subdued( text ) if dim else text


def _accent_colour( accent ):
    if accent in ( 'error', 'remove_error' ):
        return as_remove_error if accent == 'remove_error' else as_error
    if accent == 'remove_notice':
        return as_remove_notice
    if accent == 'warning':
        return as_warning
    return as_info


def _paint_name_row_size( size, is_name_row, dim ):
    """Size on a fully selected/removed sconscript or toolchain name row is emphasised."""
    if dim:
        return as_subdued( size )
    if is_name_row:
        return as_emphasised( size )
    return size


def _paint_sconscript_name( name, is_sconscript_name, dim, accent='info' ):
    """Name rows use the accent colour; fully matched names are also emphasised."""
    if is_sconscript_name:
        coloured = _accent_colour( accent )( name )
        if dim:
            return as_subdued( coloured )
        return as_emphasised( coloured )
    return as_subdued( name ) if dim else name


def _paint_sconscript_mark( mark, is_sconscript_name, dim, accent='info' ):
    """Accent-coloured marks; fully matched name-row marks are also emphasised."""
    colour_mark = is_sconscript_name or accent in (
            'error', 'warning', 'remove_notice', 'remove_error',
    )
    if colour_mark and mark.strip():
        display = mark
        # Emphasised name rows use the heavier check / ballot so they read as settled.
        if is_sconscript_name and not dim:
            display = storage.with_heavy_marks( mark )
        coloured = _accent_colour( accent )( display )
        if dim:
            return as_subdued( coloured )
        if is_sconscript_name:
            return as_emphasised( coloured )
        return coloured
    return as_subdued( mark ) if dim else mark


def _ruled_header( columns, width ):
    """Header ruled above and below, matching the develop-report shape."""
    rule = as_subdued( INDENT + RULE * max( width - len( INDENT ), len( columns ) ) )
    return [ rule, INDENT + columns, rule ]


def _closing_rule( width ):
    return as_subdued( INDENT + RULE * ( width - len( INDENT ) ) )


def _section_width( *lines ):
    return max( len( line ) for line in lines ) if lines else 40


def _columns( middle_heading, third_heading ):
    return "{}  {}  {}".format(
        'SIZE'.rjust( SIZE_WIDTH ),
        middle_heading.ljust( MIDDLE_WIDTH ),
        third_heading,
    )


def _folder_hang_label( folder, hang='selected' ):
    total = folder['entries']
    matched = folder['selected_entries']
    unit = "entry" if total == 1 else "entries"
    if hang == 'removing':
        if total and matched == total:
            return "removing all {} {}".format( total, unit )
        return "removing ({} of {} {})".format( matched, total, unit )
    if hang == 'removed':
        if total and matched == total:
            return "removed all {} {}".format( total, unit )
        return "removed ({} of {} {})".format( matched, total, unit )
    if total and matched == total:
        return "all {} {} selected".format( total, unit )
    return "selected ({} of {} {})".format( matched, total, unit )


def _folder_lines( folder, colour=False, accent='info', hang='selected' ):
    """Folder rows; ``colour`` paints the totals row and subdues the hang branch."""
    _tee, elbow, _pipe, _gap = storage.glyphs()
    root = INDENT + "{}  {}  {}".format(
        _size_cell( folder['size_bytes'] ),
        _age_cell( folder['mtime'] ),
        folder['display_path'],
    )
    if colour:
        root = _accent_colour( accent )( root )
    branch = as_subdued( elbow ) if colour else elbow
    size = _size_cell( folder['selected_bytes'] )
    age = _age_cell( folder['selected_mtime'] )
    label = _folder_hang_label( folder, hang=hang )
    if (
            colour
        and folder['entries']
        and folder['selected_entries'] == folder['entries']
    ):
        size = as_emphasised( size )
        label = as_emphasised( label )
    selected = INDENT + "{}  {}  {}{}".format( size, age, branch, label )
    return root, selected


def _toolchain_label_parts( node, mode='selection' ):
    if mode == 'outcome':
        result = node.get( 'result', 'none' )
        if result == 'none' or node['selection'] == 'none':
            mark = storage.selection_triple( 'none' )
        else:
            mark = storage.outcome_triple( node['selection'], result )
        return mark, node['name']
    return (
        storage.selection_triple( node['selection'] ),
        node['name'],
    )


# Width of ``✓✓✓ `` / ``--- `` so variant children hang under the toolchain name.
_TOOLCHAIN_MARK_PAD = '    '


def _toolchain_lines( tree, colour=False, accent='info', mode='selection' ):
    tee, elbow, pipe, gap = storage.glyphs()
    lines = []

    def emit( node, prefix, is_last ):
        branch = elbow if is_last else tee
        size = _size_cell( node['size_bytes'] )
        age = _age_cell( node['mtime'] )
        mark, name = _toolchain_label_parts( node, mode=mode )
        stem = prefix + branch
        row_accent = accent
        if mode == 'outcome':
            row_accent = _accent_for_result( node.get( 'result', 'none' ) )
        if colour:
            dim = node['selection'] != 'full'
            is_toolchain_name = bool( node.get( 'children' ) )
            size = _paint_name_row_size( size, is_toolchain_name, dim )
            age = _paint( age, dim )
            stem = as_subdued( stem )
            # Toolchain parents use the same accent as sconscript names/marks.
            if is_toolchain_name:
                mark = _paint_sconscript_mark( mark, True, dim, accent=row_accent )
                name = _paint_sconscript_name( name, True, dim, accent=row_accent )
            elif mode == 'outcome':
                mark = _paint_sconscript_mark( mark, False, dim, accent=row_accent )
                name = _paint( name, dim )
            else:
                mark = _paint( mark, dim )
                name = _paint( name, dim )
        lines.append( INDENT + "{}  {}  {}{} {}".format(
            size, age, stem, mark, name
        ) )
        children = node.get( 'children' ) or []
        # Indent past the selection triple so children hang under the toolchain name.
        child_prefix = prefix + ( gap if is_last else pipe ) + _TOOLCHAIN_MARK_PAD
        for index, child in enumerate( children ):
            emit( child, child_prefix, index == len( children ) - 1 )

    for index, node in enumerate( tree ):
        emit( node, '', index == len( tree ) - 1 )
    return lines


def _sconscript_rows( tree, mode='selection' ):
    """Plain sconscript-tree rows as data, so width and colour can share one walk."""
    tee, elbow, pipe, gap = storage.glyphs()
    rows = []

    def walk( node, prefix ):
        names = _child_names( node )
        for index, name in enumerate( names ):
            child = node.children[name]
            last = index == len( names ) - 1
            branch = elbow if last else tee
            if mode == 'outcome':
                mark = _node_outcome_cell( child )
                accent = _accent_for_result( child.result )
            else:
                mark = _node_selected_cell( child )
                accent = 'info'
            rows.append( {
                'size': _size_cell( child.size_bytes ),
                'mark': mark,
                'stem': prefix + branch,
                'name': child.name,
                'dim': child.selection != 'full',
                'is_sconscript_name': child.is_sconscript_name,
                'accent': accent,
            } )
            walk( child, prefix + ( gap if last else pipe ) )

    walk( tree, '' )
    return rows


def _format_sconscript_line( row, colour=False, accent='info' ):
    size = row['size']
    mark = row['mark']
    stem = row['stem']
    name = row['name']
    row_accent = row.get( 'accent', accent )
    if colour:
        size = _paint_name_row_size( size, row['is_sconscript_name'], row['dim'] )
        mark = _paint_sconscript_mark(
            mark, row['is_sconscript_name'], row['dim'], accent=row_accent
        )
        stem = as_subdued( stem )
        name = _paint_sconscript_name(
            name, row['is_sconscript_name'], row['dim'], accent=row_accent
        )
    return INDENT + "{}  {}  {}{}".format( size, mark, stem, name )


def _render_folder_section( folder, width, accent='info', hang='selected' ):
    heading = _columns( 'LAST BUILD', 'BUILD FOLDER' )
    root_line, selected_line = _folder_lines(
        folder, colour=True, accent=accent, hang=hang
    )
    lines = _ruled_header( heading, width )
    lines.append( root_line )
    lines.append( selected_line )
    lines.append( _closing_rule( width ) )
    return lines


def _render_toolchain_section( tree, width, accent='info', mode='selection' ):
    heading = _columns( 'LAST BUILD', 'BY TOOLCHAIN VARIANT' )
    lines = _ruled_header( heading, width )
    body = _toolchain_lines( tree, colour=True, accent=accent, mode=mode )
    lines.extend( body )
    if body:
        lines.append( _closing_rule( width ) )
    return lines


def _render_sconscript_section(
        tree, width, middle_heading='SELECTED', accent='info', mode='selection'
):
    heading = _columns( middle_heading, 'BY SCONSCRIPT' )
    lines = _ruled_header( heading, width )
    rows = _sconscript_rows( tree, mode=mode )
    for row in rows:
        lines.append( _format_sconscript_line( row, colour=True, accent=accent ) )
    if rows:
        lines.append( _closing_rule( width ) )
    return lines


def _report_width(
        folder, toolchain_tree, sconscript_tree,
        middle_heading='SELECTED', hang='selected', mode='selection'
):
    """One rule width for every section, based on the widest plain-text line."""
    root_line, selected_line = _folder_lines( folder, colour=False, hang=hang )
    candidates = [
        INDENT + _columns( 'LAST BUILD', 'BUILD FOLDER' ),
        INDENT + _columns( 'LAST BUILD', 'BY TOOLCHAIN VARIANT' ),
        INDENT + _columns( middle_heading, 'BY SCONSCRIPT' ),
        root_line,
        selected_line,
    ]
    candidates.extend( _toolchain_lines( toolchain_tree, colour=False, mode=mode ) )
    candidates.extend(
        _format_sconscript_line( row, colour=False )
        for row in _sconscript_rows( sconscript_tree, mode=mode )
    )
    return _section_width( *candidates )


def _write_build_report(
        out, folder, toolchain_tree, sconscript_tree,
        accent='info', middle_heading='SELECTED', hang='selected', mode='selection'
):
    """Print the three list/remove views with a shared rule width."""
    width = _report_width(
        folder, toolchain_tree, sconscript_tree,
        middle_heading=middle_heading, hang=hang, mode=mode,
    )
    for line in _render_folder_section( folder, width, accent=accent, hang=hang ):
        out.write( line + "\n" )
    out.write( "\n" )
    for line in _render_toolchain_section(
            toolchain_tree, width, accent=accent, mode=mode
    ):
        out.write( line + "\n" )
    out.write( "\n" )
    for line in _render_sconscript_section(
            sconscript_tree, width,
            middle_heading=middle_heading, accent=accent, mode=mode,
    ):
        out.write( line + "\n" )


def _effective_selection_settings( construct, cuppa_env, rows=None ):
    """Variant and toolchain flags for the selected builds that exist on disk.

    Defaults and CLI flags can name variants that are not present under the build root. The
    summary command is for ``--remove-builds``, so it only includes variants and toolchains that
    appear in selected entries discovered on disk. When nothing selected exists yet, it falls
    back to the active option selection.
    """
    settings = {}
    selected_rows = [ row for row in ( rows or [] ) if row.get( 'selected' ) ]
    if selected_rows:
        variants = set()
        toolchains = []
        seen = set()
        for row in selected_rows:
            parts = row['tool_variant'].split( os.sep )
            if not parts:
                continue
            toolchain = parts[0]
            if toolchain not in seen:
                seen.add( toolchain )
                toolchains.append( toolchain )
            if len( parts ) > 1:
                variants.add( parts[1] )
        for variant in sorted( variants ):
            settings[variant] = True
        if toolchains:
            settings['toolchains'] = toolchains
        return settings

    variants = set()
    toolchain_names = []
    seen = set()
    for toolchain in cuppa_env.get( 'active_toolchains' ) or []:
        name = toolchain.name()
        if name not in seen:
            seen.add( name )
            toolchain_names.append( name )
        for build_env in construct.create_build_envs( toolchain, cuppa_env ):
            variants.add( build_env['variant'] )
    for variant in sorted( variants ):
        settings[variant] = True
    requested = cuppa_env.get_option( 'toolchains' )
    if requested:
        if isinstance( requested, ( list, tuple ) ):
            settings['toolchains'] = [ str( name ) for name in requested ]
        else:
            settings['toolchains'] = [ str( requested ) ]
    elif toolchain_names:
        settings['toolchains'] = toolchain_names
    return settings


def _command_line_from_settings( settings, colour=True ):
    """Format settings as a cuppa command suffix, matching ``--show-conf`` style."""
    emphasise = as_emphasised if colour else ( lambda text: text )
    info = as_info if colour else ( lambda text: text )
    commands = []
    for key in sorted( settings ):
        value = settings[key]
        command = emphasise( "--" + key )
        if value is not True and value is not False:
            if isinstance( value, list ):
                command += "=" + info( ",".join( value ) )
            else:
                command += "=" + info( str( value ) )
        commands.append( command )
    return " ".join( commands )


def _selection_summary( construct, cuppa_env, folder, rows=None ):
    """Closing note: selected size plus an explicit command for those builds."""
    settings = _effective_selection_settings( construct, cuppa_env, rows=rows )
    command_suffix = _command_line_from_settings( settings, colour=False )
    equivalent = "cuppa -D"
    if command_suffix:
        equivalent = "cuppa -D " + command_suffix
    return {
        'selected_bytes': folder['selected_bytes'],
        'selected_size': folder['selected_size'],
        'total_bytes': folder['size_bytes'],
        'total_size': folder['size'],
        'selected_entries': folder['selected_entries'],
        'entries': folder['entries'],
        'settings': settings,
        'equivalent_command': equivalent,
    }


def _render_summary( summary ):
    settings = summary.get( 'settings' ) or {}
    coloured = "cuppa -D"
    suffix = _command_line_from_settings( settings, colour=True )
    if suffix:
        coloured = "cuppa -D " + suffix
    selected_size = summary['selected_size']
    total_size = as_emphasised( summary['total_size'] )
    if summary['selected_bytes'] < summary['total_bytes']:
        selected_size = as_emphasised( as_info( selected_size ) )
    else:
        selected_size = as_emphasised( selected_size )
    return [
        "Selected {} of {} ({} of {} entries)".format(
            selected_size,
            total_size,
            summary['selected_entries'],
            summary['entries'],
        ),
        "",
        "Explicit command for the selected builds:",
        "",
        coloured,
        "",
        "Append --remove-builds to clear those folders.",
    ]


def _confirm_list_builds_lines( construct, cuppa_env, rows ):
    """After a removal, point at the same selection with ``--list-builds`` to verify."""
    settings = _effective_selection_settings( construct, cuppa_env, rows=rows )
    coloured = "cuppa -D"
    suffix = _command_line_from_settings( settings, colour=True )
    if suffix:
        coloured = "cuppa -D " + suffix
    coloured += " " + as_emphasised( "--list-builds" )
    return [
        "",
        "Verify the removal with the same selection by adding --list-builds:",
        "",
        coloured,
    ]


def _removal_announce_line(
        planning, candidate_count, size_bytes, abs_build_root, project_dir=None
):
    unit = "entry" if candidate_count == 1 else "entries"
    path = storage.short_path( abs_build_root, project_dir=project_dir )
    return "{} {} {} ({}) under {}".format(
        "Would remove" if planning else "Removing",
        as_emphasised( str( candidate_count ) ),
        unit,
        as_emphasised( storage.human_size( size_bytes ) ),
        as_info( path ),
    )


def _removal_result_line( planning, removed_count, removed_bytes ):
    unit = "entry" if removed_count == 1 else "entries"
    size = storage.human_size( removed_bytes )
    if planning:
        return "Would remove {} {} freeing up {} of disk space.".format(
            removed_count, unit, size
        )
    return "Removed {} {} freeing up {} of disk space.".format(
        removed_count, unit, size
    )


def _plural( count, noun, plural_noun=None ):
    if count == 1:
        return "{} {}".format( count, noun )
    return "{} {}".format( count, plural_noun or noun + "s" )


def _format_removal_reason( error, project_dir, path=None ):
    """Human reason for a failed removal; values live in ``[...]`` for highlighting."""
    if isinstance( error, OSError ) and getattr( error, 'filename', None ):
        short = storage.short_path( error.filename, project_dir=project_dir )
        if error.errno is not None and error.strerror:
            return "[Errno {}] {}: [{}]".format( error.errno, error.strerror, short )
        if error.strerror:
            return "{}: [{}]".format( error.strerror, short )
        return "[{}]".format( short )
    text = storage.shorten_paths_in_text( str( error ), project_dir=project_dir )
    if path and '[' not in text:
        short = storage.short_path( path, project_dir=project_dir )
        return "{}: [{}]".format( text, short )
    # Prefer bracketed paths over quotes so highlight_values can pick them out.
    return re.sub(
        r"(['\"])([^'\"]+)\1",
        lambda match: "[{}]".format( match.group( 2 ) ),
        text,
    )


def _removal_failure_summary( failures ):
    errors = sum( 1 for item in failures if item['severity'] == 'error' )
    warnings = sum( 1 for item in failures if item['severity'] == 'warning' )
    parts = []
    if errors:
        parts.append( _plural( errors, 'error' ) )
    if warnings:
        parts.append( _plural( warnings, 'warning' ) )
    return ", ".join( parts )


def _removal_error_lines(
        failures, width=None,
        intro="Not all requested build entries could be removed"
):
    """Judgement tree for paths that could not be removed, matching --list-develop shape."""
    if not failures:
        return []

    tee, elbow, pipe, gap = storage.glyphs()
    stub = pipe.rstrip()
    colour_for = { 'error': as_error, 'warning': as_warning }
    heading_for = { 'error': 'error', 'warning': 'warning' }
    prose_width = width if width is not None else storage.WIDEST_PROSE

    summary = _removal_failure_summary( failures )
    summary_colour = as_error if any(
        item['severity'] == 'error' for item in failures
    ) else as_warning
    lines = [
        "",
        "{}: {}".format(
            intro,
            storage.highlight_values( "[{}]".format( summary ), summary_colour ),
        ),
        "",
    ]

    groups = []
    for severity in ( 'error', 'warning' ):
        group = [ item for item in failures if item['severity'] == severity ]
        if group:
            groups.append( ( severity, group ) )

    for group_index, ( severity, group ) in enumerate( groups ):
        if group_index:
            lines.append( "" )
        colour = colour_for[severity]
        lines.append( INDENT + colour( _plural( len( group ), heading_for[severity] ) ) )
        lines.append( as_subdued( INDENT + stub ) )
        for index, failure in enumerate( group ):
            last = index == len( group ) - 1
            branch = elbow if last else tee
            lines.append( as_subdued( INDENT + branch ) + colour( failure['label'] ) )
            note_under = gap if last else pipe
            note_branch = INDENT + note_under + elbow
            note_carried = INDENT + note_under + gap
            wrap_width = prose_width - len( note_branch )
            for piece in storage.wrapped( failure['reason'], wrap_width ):
                lines.append(
                    as_subdued( note_branch )
                    + storage.highlight_values( piece, colour )
                )
                note_branch = note_carried
            if not last:
                lines.append( as_subdued( INDENT + pipe.rstrip() ) )
    return lines


def _remove_all_announce_line( planning, abs_build_root, size_bytes, project_dir=None ):
    path = storage.short_path( abs_build_root, project_dir=project_dir )
    return "{} build root {} ({})".format(
        "Would remove" if planning else "Removing",
        as_info( path ),
        as_emphasised( storage.human_size( size_bytes ) ),
    )


def _remove_all_result_line( planning, abs_build_root, size_bytes, project_dir=None ):
    path = storage.short_path( abs_build_root, project_dir=project_dir )
    size = storage.human_size( size_bytes )
    if planning:
        return "Would remove build root {} freeing up {} of disk space.".format(
            as_info( path ),
            as_emphasised( size ),
        )
    return "Removed build root {} freeing up {} of disk space.".format(
        as_info( path ),
        as_emphasised( size ),
    )


def _apply_removal_outcomes( rows, outcomes_by_path ):
    """Stamp each selected row with removed/failed from the attempt map."""
    for row in rows:
        if not row['selected']:
            row['result'] = 'none'
            continue
        outcome = outcomes_by_path.get( row['path'] )
        if outcome is None:
            row['result'] = 'none'
            continue
        row['result'] = outcome['result']
        if outcome.get( 'reason' ):
            row['error'] = outcome['reason']


def list_builds( construct, cuppa_env, out=None ):
    """Print folder, toolchain-variant, and sconscript views of the build root."""
    out = out or sys.stdout
    abs_build_root = cuppa_env['abs_build_root']
    selected = selected_tool_variant_dirs( construct, cuppa_env )
    rows = _collect_variant_rows( abs_build_root, selected )
    folder = _folder_summary( abs_build_root, rows )
    toolchain_tree = _toolchain_variant_tree( rows )
    sconscript_tree = _build_sconscript_tree( rows )
    summary = _selection_summary( construct, cuppa_env, folder, rows=rows )

    if cuppa_env.get( 'list_format' ) == 'json':
        payload = {
            'build_root': abs_build_root,
            'folder': folder,
            'by_toolchain_variant': [
                _toolchain_variant_to_json( node ) for node in toolchain_tree
            ],
            'by_sconscript': [
                _tree_to_json( sconscript_tree.children[name] )
                for name in _child_names( sconscript_tree )
            ],
            'entries': [
                {
                    'size': row['size'],
                    'size_bytes': row['size_bytes'],
                    'last_build': row['last_build'],
                    'mtime': row['mtime'],
                    'sconscript': row['sconscript'],
                    'tool_variant': row['tool_variant'],
                    'selected': row['selected'],
                    'path': row['path'],
                }
                for row in rows
            ],
            'summary': summary,
            'total_bytes': folder['size_bytes'],
            'total': folder['size'],
        }
        out.write( storage.render_json_payload( payload ) )
        out.write( "\n" )
        return 0

    _write_build_report( out, folder, toolchain_tree, sconscript_tree )
    out.write( "\n" )
    for line in _render_summary( summary ):
        out.write( line + "\n" )
    return 0


def _refuse_suspicious_build_root( abs_build_root, sconstruct_dir ):
    if storage.is_suspicious_root( abs_build_root ):
        raise storage.StorageError(
            "refusing to remove build root [{}]: it is a filesystem or home directory".format(
                abs_build_root
            )
        )
    if storage.real_path( abs_build_root ) == storage.real_path( sconstruct_dir ):
        raise storage.StorageError(
            "refusing to remove build root [{}]: it is the sconstruct directory".format(
                abs_build_root
            )
        )


def remove_builds( construct, cuppa_env, out=None ):
    """Remove variant subtrees matching the current selection. Returns an exit status."""
    out = out or sys.stdout
    abs_build_root = cuppa_env['abs_build_root']
    _refuse_suspicious_build_root( abs_build_root, cuppa_env['sconstruct_dir'] )

    suffixes = selected_tool_variant_dirs( construct, cuppa_env )
    if not suffixes:
        out.write( "nothing to remove (no active toolchain / variant selection)\n" )
        return 0

    candidates = []
    for suffix in suffixes:
        for path in build_layout.paths_ending_with( abs_build_root, suffix ):
            # Symlinks first: realpath containment would otherwise mis-report an escape.
            if os.path.islink( path ):
                raise storage.StorageError(
                    "refusing to remove through symlink [{}]".format( path )
                )
            storage.ensure_contained( path, abs_build_root, what="build path" )
            candidates.append( path )

    # Unique paths, deepest first so parents prune cleanly afterwards.
    candidates = sorted( set( candidates ), key=lambda path: path.count( os.sep ), reverse=True )

    if not candidates:
        out.write( "nothing to remove (no matching variant trees under {})\n".format(
            abs_build_root
        ) )
        return 0

    # Measure before acting so the post-removal report still has sizes to show.
    rows = _collect_variant_rows( abs_build_root, suffixes )
    folder = _folder_summary( abs_build_root, rows )
    planned_bytes = sum( row['size_bytes'] for row in rows if row['selected'] )
    planning = dry_run( cuppa_env )
    project_dir = cuppa_env['sconstruct_dir']

    out.write( _removal_announce_line(
        planning, len( candidates ), planned_bytes, abs_build_root,
        project_dir=project_dir,
    ) + "\n" )
    out.write( "\n" )

    outcomes_by_path = {}
    failures = []
    for path in candidates:
        label = os.path.relpath( path, abs_build_root )
        if planning:
            outcomes_by_path[path] = { 'result': 'removed' }
            continue
        try:
            storage.ensure_contained( path, abs_build_root, what="build path" )
            if not os.path.lexists( path ):
                raise storage.StorageError(
                    "not found (possibly already deleted)"
                )
            storage.remove_path( path, dry_run=False )
            storage.prune_empty_parents( os.path.dirname( path ), abs_build_root )
            outcomes_by_path[path] = { 'result': 'removed' }
        except storage.StorageError as error:
            reason = _format_removal_reason( error, project_dir, path=path )
            already_gone = "already deleted" in str( error ).lower() or (
                "not found" in str( error ).lower()
            )
            severity = 'warning' if already_gone else 'error'
            outcomes_by_path[path] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'label': label,
                'reason': reason,
                'path': path,
                'severity': severity,
            } )
        except OSError as error:
            reason = _format_removal_reason( error, project_dir, path=path )
            outcomes_by_path[path] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'label': label,
                'reason': reason,
                'path': path,
                'severity': 'error',
            } )

    _apply_removal_outcomes( rows, outcomes_by_path )
    removed_rows = [ row for row in rows if row.get( 'result' ) == 'removed' ]
    removed_bytes = sum( row['size_bytes'] for row in removed_rows )
    # Hang / accent reflect what succeeded; folder totals stay the pre-removal snapshot.
    folder['selected_entries'] = len( removed_rows )
    folder['selected_bytes'] = removed_bytes
    folder['selected_size'] = storage.human_size( removed_bytes )
    has_errors = any( item['severity'] == 'error' for item in failures )
    if removed_rows:
        folder_accent = 'remove_notice'
    elif has_errors:
        folder_accent = 'remove_error'
    elif failures:
        folder_accent = 'warning'
    else:
        folder_accent = 'remove_notice'
    toolchain_tree = _toolchain_variant_tree( rows )
    sconscript_tree = _build_sconscript_tree( rows )

    _write_build_report(
        out, folder, toolchain_tree, sconscript_tree,
        accent=folder_accent, middle_heading='REMOVED', hang='removed', mode='outcome',
    )

    for line in _removal_error_lines( failures ):
        out.write( line + "\n" )

    out.write( "\n" )
    out.write( _removal_result_line( planning, len( removed_rows ), removed_bytes ) + "\n" )
    if planning:
        out.write( "dry run (-n); nothing removed\n" )

    for line in _confirm_list_builds_lines( construct, cuppa_env, rows ):
        out.write( line + "\n" )
    return 1 if has_errors else 0


def _emit_outcome_tables( out, folder, rows, failures=None, intro=None ):
    """Print REMOVED tables (and optional failure tree) from stamped outcome rows."""
    removed_rows = [ row for row in rows if row.get( 'result' ) == 'removed' ]
    removed_bytes = sum( row['size_bytes'] for row in removed_rows )
    folder = dict( folder )
    folder['selected_entries'] = len( removed_rows )
    folder['selected_bytes'] = removed_bytes
    folder['selected_size'] = storage.human_size( removed_bytes )
    has_errors = any( item['severity'] == 'error' for item in ( failures or [] ) )
    if removed_rows:
        folder_accent = 'remove_notice'
    elif has_errors:
        folder_accent = 'remove_error'
    elif failures:
        folder_accent = 'warning'
    else:
        folder_accent = 'remove_notice'
    toolchain_tree = _toolchain_variant_tree( rows )
    sconscript_tree = _build_sconscript_tree( rows )
    _write_build_report(
        out, folder, toolchain_tree, sconscript_tree,
        accent=folder_accent, middle_heading='REMOVED', hang='removed', mode='outcome',
    )
    if failures:
        kwargs = {}
        if intro:
            kwargs['intro'] = intro
        for line in _removal_error_lines( failures, **kwargs ):
            out.write( line + "\n" )
    return removed_rows, removed_bytes, has_errors


def _failure_label_for_path( path, abs_build_root, project_dir ):
    """Prefer a path relative to the build root; otherwise a short project/home path."""
    if path and storage.is_contained( path, abs_build_root ):
        return os.path.relpath( path, abs_build_root )
    if path:
        return storage.short_path( path, project_dir=project_dir )
    return storage.short_path( abs_build_root, project_dir=project_dir )


def _stamp_remove_all_outcomes( rows, succeeded, error=None ):
    """Mark each variant removed or failed after a whole-root removal attempt."""
    culprit = None
    if error is not None and getattr( error, 'filename', None ):
        culprit = os.path.realpath( error.filename )
    for row in rows:
        row['selected'] = True
        if succeeded:
            row['result'] = 'removed'
            continue
        if not os.path.lexists( row['path'] ):
            row['result'] = 'removed'
            continue
        row['result'] = 'failed'
        if culprit and (
                os.path.realpath( row['path'] ) == culprit
                or storage.is_contained( culprit, row['path'] )
        ):
            row['error'] = str( error )


def remove_all_builds( cuppa_env, out=None ):
    """Remove the entire build root. Returns an exit status."""
    out = out or sys.stdout
    abs_build_root = cuppa_env['abs_build_root']
    project_dir = cuppa_env['sconstruct_dir']
    _refuse_suspicious_build_root( abs_build_root, project_dir )

    short_root = storage.short_path( abs_build_root, project_dir=project_dir )
    if not os.path.exists( abs_build_root ):
        out.write( storage.highlight_values(
            "nothing to remove (build root [{}] does not exist)".format( short_root ),
            as_info,
        ) + "\n" )
        return 0

    if os.path.islink( abs_build_root ):
        raise storage.StorageError(
            "refusing to remove build root through symlink [{}]".format( short_root )
        )

    # Inventory before acting so the report can still name what was under the root.
    rows = _collect_all_variant_rows( abs_build_root )
    folder = _folder_summary( abs_build_root, rows )
    size_bytes = folder['size_bytes']
    planning = dry_run( cuppa_env )

    out.write( _remove_all_announce_line(
        planning, abs_build_root, size_bytes, project_dir=project_dir
    ) + "\n" )
    out.write( "\n" )

    if planning:
        for row in rows:
            row['result'] = 'removed'
        _emit_outcome_tables( out, folder, rows )
        out.write( "\n" )
        out.write( _remove_all_result_line(
            True, abs_build_root, size_bytes, project_dir=project_dir
        ) + "\n" )
        out.write( "dry run (-n); nothing removed\n" )
        out.write( "\nVerify with --list-builds:\n\n" )
        out.write( as_emphasised( "cuppa -D --list-builds" ) + "\n" )
        return 0

    error = None
    already_gone = False
    try:
        if not os.path.lexists( abs_build_root ):
            raise storage.StorageError( "not found (possibly already deleted)" )
        storage.remove_path( abs_build_root, dry_run=False )
        succeeded = True
    except storage.StorageError as caught:
        succeeded = False
        error = caught
        already_gone = (
            "already deleted" in str( caught ).lower()
            or "not found" in str( caught ).lower()
        )
    except OSError as caught:
        succeeded = False
        error = caught

    _stamp_remove_all_outcomes( rows, succeeded, error=error )

    failures = []
    if not succeeded:
        severity = 'warning' if already_gone else 'error'
        fail_path = getattr( error, 'filename', None ) or abs_build_root
        label = _failure_label_for_path( fail_path, abs_build_root, project_dir )
        reason = _format_removal_reason( error, project_dir, path=fail_path )
        failures.append( {
            'label': label,
            'reason': reason,
            'path': fail_path,
            'severity': severity,
        } )

    removed_rows, removed_bytes, has_errors = _emit_outcome_tables(
        out, folder, rows, failures=failures,
        intro="The build root could not be removed" if failures else None,
    )

    out.write( "\n" )
    if succeeded:
        out.write( _remove_all_result_line(
            False, abs_build_root, size_bytes, project_dir=project_dir
        ) + "\n" )
    elif already_gone:
        out.write( "nothing removed (build root was already gone)\n" )
    else:
        out.write( "Build root was not removed.\n" )
        if removed_rows:
            out.write( _removal_result_line(
                False, len( removed_rows ), removed_bytes
            ) + "\n" )

    out.write( "\nVerify with --list-builds:\n\n" )
    out.write( as_emphasised( "cuppa -D --list-builds" ) + "\n" )
    return 1 if has_errors else 0


def run( construct, cuppa_env, out=None ):
    """Dispatch the requested storage action. Returns an exit status."""
    out = out or sys.stdout
    from cuppa.core import dependency_actions
    try:
        if cuppa_env.get( 'remove_all_builds' ) and (
                cuppa_env.get( 'remove_builds' ) or cuppa_env.get( 'list_builds' )
        ):
            logger.warn( "[{}] takes precedence over the other build storage actions".format(
                    as_warning( "--remove-all-builds" )
            ) )

        if cuppa_env.get( 'remove_all_builds' ):
            logger.info( as_info_label(
                    "Running in REMOVE ALL BUILDS mode, no building will be attempted" ) )
            return remove_all_builds( cuppa_env, out=out )

        if cuppa_env.get( 'remove_builds' ):
            logger.info( as_info_label(
                    "Running in REMOVE BUILDS mode, no building will be attempted" ) )
            return remove_builds( construct, cuppa_env, out=out )

        if cuppa_env.get( 'list_builds' ):
            logger.info( as_info_label(
                    "Running in LIST BUILDS mode, no building will be attempted" ) )
            return list_builds( construct, cuppa_env, out=out )

        if dependency_actions.wants_dependency_action( cuppa_env ):
            return dependency_actions.run( construct, cuppa_env, out=out )

    except storage.StorageError as error:
        logger.error( as_error( str( error ) ) )
        out.write( "error: {}\n".format( error ) )
        return 1

    return 0
