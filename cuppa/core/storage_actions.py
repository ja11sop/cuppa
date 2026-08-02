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
import sys
from collections import defaultdict

import SCons.Script

from cuppa.colourise import as_emphasised, as_error, as_info, as_info_label, as_subdued, as_warning
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
        '--remove-build', dest='remove_build', action='store_true',
        help="Remove every variant subtree under the build root that matches the current"
             " toolchain / variant selection, then exit",
    )
    add_option(
        '--remove-all-builds', dest='remove_all_builds', action='store_true',
        help="Remove the entire build root, then exit",
    )
    add_option(
        '--list-format', dest='list_format', choices=( 'text', 'json' ),
        nargs=1, action='store', default='text',
        help="Output format for --list-* options: text (default) or json",
    )


def process_storage_action_options( cuppa_env ):
    cuppa_env['list_builds'] = bool( cuppa_env.get_option( 'list_builds' ) )
    cuppa_env['remove_build'] = bool( cuppa_env.get_option( 'remove_build' ) )
    cuppa_env['remove_all_builds'] = bool( cuppa_env.get_option( 'remove_all_builds' ) )
    list_format = cuppa_env.get_option( 'list_format', default='text' )
    if isinstance( list_format, ( list, tuple ) ):
        list_format = list_format[0] if list_format else 'text'
    cuppa_env['list_format'] = list_format or 'text'


def wants_storage_action( cuppa_env ):
    return bool(
        cuppa_env.get( 'list_builds' )
        or cuppa_env.get( 'remove_build' )
        or cuppa_env.get( 'remove_all_builds' )
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
        'is_leaf', 'is_sconscript_name', 'is_toolchain',
    )

    def __init__( self, name ):
        self.name = name
        self.children = {}
        self.size_bytes = 0
        self.mtime = None
        self.selected = False
        self.selection = 'none'
        self.is_leaf = False
        self.is_sconscript_name = False
        self.is_toolchain = False


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

    def rollup( node ):
        if node.is_leaf and not node.children:
            return node.size_bytes, node.mtime, node.selection
        total = 0
        newest = None
        child_selections = []
        for child in node.children.values():
            size, mtime, selection = rollup( child )
            total += size
            newest = _max_mtime( newest, mtime )
            child_selections.append( selection )
        node.size_bytes = total
        node.mtime = newest
        if child_selections and all( status == 'full' for status in child_selections ):
            node.selection = 'full'
        elif child_selections and all( status == 'none' for status in child_selections ):
            node.selection = 'none'
        else:
            node.selection = 'partial'
        node.selected = node.selection == 'full'
        return total, newest, node.selection

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
    groups = defaultdict( lambda: { 'size_bytes': 0, 'mtime': None, 'selected': False } )
    for row in rows:
        group = groups[row['tool_variant']]
        group['size_bytes'] += row['size_bytes']
        group['mtime'] = _max_mtime( group['mtime'], row['mtime'] )
        group['selected'] = group['selected'] or row['selected']

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
            'children': [],
        } )

    tree = []
    for toolchain in sorted( by_toolchain ):
        children = by_toolchain[toolchain]
        selection = _selection_from_children( [ child['selection'] for child in children ] )
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


def _paint( text, dim ):
    return as_subdued( text ) if dim else text


def _paint_name_row_size( size, is_name_row, dim ):
    """Size on a fully selected sconscript/toolchain name row is emphasised."""
    if dim:
        return as_subdued( size )
    if is_name_row:
        return as_emphasised( size )
    return size


def _paint_sconscript_name( name, is_sconscript_name, dim ):
    """Sconscript/toolchain names are info-coloured; fully selected names are also emphasised."""
    if is_sconscript_name:
        coloured = as_info( name )
        if dim:
            return as_subdued( coloured )
        return as_emphasised( coloured )
    return as_subdued( name ) if dim else name


def _paint_sconscript_mark( mark, is_sconscript_name, dim ):
    """Info-coloured marks; fully selected name-row marks are also emphasised."""
    if is_sconscript_name and mark.strip():
        coloured = as_info( mark )
        if dim:
            return as_subdued( coloured )
        return as_emphasised( coloured )
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


def _selected_folder_label( folder ):
    total = folder['entries']
    selected = folder['selected_entries']
    unit = "entry" if total == 1 else "entries"
    if total and selected == total:
        return "all {} {} selected".format( total, unit )
    return "selected ({} of {} {})".format( selected, total, unit )


def _folder_lines( folder, colour=False ):
    """Folder rows; ``colour`` info-paints the totals row and subdues the hang branch."""
    _tee, elbow, _pipe, _gap = storage.glyphs()
    root = INDENT + "{}  {}  {}".format(
        _size_cell( folder['size_bytes'] ),
        _age_cell( folder['mtime'] ),
        folder['display_path'],
    )
    if colour:
        root = as_info( root )
    branch = as_subdued( elbow ) if colour else elbow
    size = _size_cell( folder['selected_bytes'] )
    age = _age_cell( folder['selected_mtime'] )
    label = _selected_folder_label( folder )
    if (
            colour
        and folder['entries']
        and folder['selected_entries'] == folder['entries']
    ):
        size = as_emphasised( size )
        label = as_emphasised( label )
    selected = INDENT + "{}  {}  {}{}".format( size, age, branch, label )
    return root, selected


def _toolchain_label_parts( node ):
    return (
        storage.selection_triple( node['selection'] ),
        node['name'],
    )


# Width of ``✓✓✓ `` / ``--- `` so variant children hang under the toolchain name.
_TOOLCHAIN_MARK_PAD = '    '


def _toolchain_lines( tree, colour=False ):
    tee, elbow, pipe, gap = storage.glyphs()
    lines = []

    def emit( node, prefix, is_last ):
        branch = elbow if is_last else tee
        size = _size_cell( node['size_bytes'] )
        age = _age_cell( node['mtime'] )
        mark, name = _toolchain_label_parts( node )
        stem = prefix + branch
        if colour:
            dim = node['selection'] != 'full'
            is_toolchain_name = bool( node.get( 'children' ) )
            size = _paint_name_row_size( size, is_toolchain_name, dim )
            age = _paint( age, dim )
            stem = as_subdued( stem )
            # Toolchain parents use the same info colour as sconscript names/marks.
            if is_toolchain_name:
                mark = _paint_sconscript_mark( mark, True, dim )
                name = _paint_sconscript_name( name, True, dim )
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


def _sconscript_rows( tree ):
    """Plain sconscript-tree rows as data, so width and colour can share one walk."""
    tee, elbow, pipe, gap = storage.glyphs()
    rows = []

    def walk( node, prefix ):
        names = _child_names( node )
        for index, name in enumerate( names ):
            child = node.children[name]
            last = index == len( names ) - 1
            branch = elbow if last else tee
            rows.append( {
                'size': _size_cell( child.size_bytes ),
                'mark': _node_selected_cell( child ),
                'stem': prefix + branch,
                'name': child.name,
                'dim': child.selection != 'full',
                'is_sconscript_name': child.is_sconscript_name,
            } )
            walk( child, prefix + ( gap if last else pipe ) )

    walk( tree, '' )
    return rows


def _format_sconscript_line( row, colour=False ):
    size = row['size']
    mark = row['mark']
    stem = row['stem']
    name = row['name']
    if colour:
        size = _paint_name_row_size( size, row['is_sconscript_name'], row['dim'] )
        mark = _paint_sconscript_mark(
            mark, row['is_sconscript_name'], row['dim']
        )
        stem = as_subdued( stem )
        name = _paint_sconscript_name(
            name, row['is_sconscript_name'], row['dim']
        )
    return INDENT + "{}  {}  {}{}".format( size, mark, stem, name )


def _render_folder_section( folder, width ):
    heading = _columns( 'LAST BUILD', 'BUILD FOLDER' )
    root_line, selected_line = _folder_lines( folder, colour=True )
    lines = _ruled_header( heading, width )
    lines.append( root_line )
    lines.append( selected_line )
    lines.append( _closing_rule( width ) )
    return lines


def _render_toolchain_section( tree, width ):
    heading = _columns( 'LAST BUILD', 'BY TOOLCHAIN VARIANT' )
    lines = _ruled_header( heading, width )
    body = _toolchain_lines( tree, colour=True )
    lines.extend( body )
    if body:
        lines.append( _closing_rule( width ) )
    return lines


def _render_sconscript_section( tree, width ):
    heading = _columns( 'SELECTED', 'BY SCONSCRIPT' )
    lines = _ruled_header( heading, width )
    rows = _sconscript_rows( tree )
    for row in rows:
        lines.append( _format_sconscript_line( row, colour=True ) )
    if rows:
        lines.append( _closing_rule( width ) )
    return lines


def _report_width( folder, toolchain_tree, sconscript_tree ):
    """One rule width for every section, based on the widest plain-text line."""
    root_line, selected_line = _folder_lines( folder, colour=False )
    candidates = [
        INDENT + _columns( 'LAST BUILD', 'BUILD FOLDER' ),
        INDENT + _columns( 'LAST BUILD', 'BY TOOLCHAIN VARIANT' ),
        INDENT + _columns( 'SELECTED', 'BY SCONSCRIPT' ),
        root_line,
        selected_line,
    ]
    candidates.extend( _toolchain_lines( toolchain_tree, colour=False ) )
    candidates.extend(
        _format_sconscript_line( row, colour=False )
        for row in _sconscript_rows( sconscript_tree )
    )
    return _section_width( *candidates )


def _effective_selection_settings( construct, cuppa_env, rows=None ):
    """Variant and toolchain flags for the selected builds that exist on disk.

    Defaults and CLI flags can name variants that are not present under the build root. The
    summary command is for ``--remove-build``, so it only includes variants and toolchains that
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
        "Append --remove-build to clear those folders.",
    ]


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

    width = _report_width( folder, toolchain_tree, sconscript_tree )
    for line in _render_folder_section( folder, width ):
        out.write( line + "\n" )
    out.write( "\n" )
    for line in _render_toolchain_section( toolchain_tree, width ):
        out.write( line + "\n" )
    out.write( "\n" )
    for line in _render_sconscript_section( sconscript_tree, width ):
        out.write( line + "\n" )
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


def remove_build( construct, cuppa_env, out=None ):
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

    planning = dry_run( cuppa_env )
    out.write( "{} {} matching variant {} under {}\n".format(
        "Would remove" if planning else "Removing",
        len( candidates ),
        "tree" if len( candidates ) == 1 else "trees",
        abs_build_root,
    ) )
    for path in sorted( candidates ):
        size = storage.human_size( storage.directory_size( path ) )
        out.write( "  {}  {}\n".format( size, path ) )

    failed = 0
    for path in candidates:
        try:
            storage.ensure_contained( path, abs_build_root, what="build path" )
            storage.remove_path( path, dry_run=planning )
            if not planning:
                storage.prune_empty_parents( os.path.dirname( path ), abs_build_root )
        except ( storage.StorageError, OSError ) as error:
            out.write( "failed: {}\n".format( error ) )
            failed += 1

    if planning:
        out.write( "dry run (-n); nothing removed\n" )
    elif failed:
        out.write( "removed with {} failure{}\n".format(
            failed, "" if failed == 1 else "s"
        ) )
    else:
        out.write( "removed {}\n".format(
            "1 tree" if len( candidates ) == 1 else "{} trees".format( len( candidates ) )
        ) )
    return 1 if failed else 0


def remove_all_builds( cuppa_env, out=None ):
    """Remove the entire build root. Returns an exit status."""
    out = out or sys.stdout
    abs_build_root = cuppa_env['abs_build_root']
    _refuse_suspicious_build_root( abs_build_root, cuppa_env['sconstruct_dir'] )

    if not os.path.exists( abs_build_root ):
        out.write( "nothing to remove (build root [{}] does not exist)\n".format(
            abs_build_root
        ) )
        return 0

    if os.path.islink( abs_build_root ):
        raise storage.StorageError(
            "refusing to remove build root through symlink [{}]".format( abs_build_root )
        )

    planning = dry_run( cuppa_env )
    size = storage.human_size( storage.directory_size( abs_build_root ) )
    out.write( "{} build root {} ({})\n".format(
        "Would remove" if planning else "Removing",
        abs_build_root,
        size,
    ) )

    try:
        storage.remove_path( abs_build_root, dry_run=planning )
    except OSError as error:
        out.write( "failed: {}\n".format( error ) )
        return 1

    if planning:
        out.write( "dry run (-n); nothing removed\n" )
    else:
        out.write( "removed {}\n".format( abs_build_root ) )
    return 0


def run( construct, cuppa_env, out=None ):
    """Dispatch the requested storage action. Returns an exit status."""
    out = out or sys.stdout
    try:
        if cuppa_env.get( 'remove_all_builds' ) and (
                cuppa_env.get( 'remove_build' ) or cuppa_env.get( 'list_builds' )
        ):
            logger.warn( "[{}] takes precedence over the other build storage actions".format(
                    as_warning( "--remove-all-builds" )
            ) )

        if cuppa_env.get( 'remove_all_builds' ):
            logger.info( as_info_label(
                    "Running in REMOVE ALL BUILDS mode, no building will be attempted" ) )
            return remove_all_builds( cuppa_env, out=out )

        if cuppa_env.get( 'remove_build' ):
            logger.info( as_info_label(
                    "Running in REMOVE BUILD mode, no building will be attempted" ) )
            return remove_build( construct, cuppa_env, out=out )

        if cuppa_env.get( 'list_builds' ):
            logger.info( as_info_label(
                    "Running in LIST BUILDS mode, no building will be attempted" ) )
            return list_builds( construct, cuppa_env, out=out )

    except storage.StorageError as error:
        logger.error( as_error( str( error ) ) )
        out.write( "error: {}\n".format( error ) )
        return 1

    return 0
