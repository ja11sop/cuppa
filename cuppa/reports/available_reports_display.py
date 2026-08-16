#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Text tree for --list-available-reports
#-------------------------------------------------------------------------------

import os
from collections import defaultdict

from cuppa.colourise import as_emphasised, as_info, as_notice, as_subdued
from cuppa.reports.registry import supporting_toolchain_rows_for_kind
from cuppa.utility import storage


REPORT_DISPLAY_ORDER = ( 'test', 'coverage', 'cxx-profiles' )

_TOOLCHAIN_WRAP_WIDTH = 72


REPORT_CATALOG = {
    'test': {
        'title': 'Collated Test Report',
        'methods': {
            'method': 'CollateTestReportIndex',
            'params': (
                {
                    'kind': 'destination',
                    'prose': 'specify destination, usually',
                    'path': '{artefacts_root}/test/',
                },
                {
                    'kind': 'sources',
                    'child': {
                        'method': 'GenerateHtmlTestReport',
                        'params': (
                            {
                                'kind': 'destination',
                                'prose': 'under',
                                'path': '{build_root}/',
                                'suffix': ' as normal',
                            },
                            {
                                'kind': 'sources',
                                'methods': ( 'BuildTest', 'Test' ),
                            },
                        ),
                    },
                },
            ),
        },
        'cli': {
            'enable': ( '--test', ),
            'clean': (
                ( '--test', '--clean' ),
            ),
        },
    },
    'coverage': {
        'title': 'Collated Coverage Report',
        'methods': {
            'method': 'CollateCoverageIndex',
            'params': (
                {
                    'kind': 'destination',
                    'prose': 'specify destination, usually',
                    'path': '{artefacts_root}/coverage/',
                },
                {
                    'kind': 'sources',
                    'child': {
                        'method': 'CollateCoverageFiles',
                        'params': (
                            {
                                'kind': 'destination',
                                'prose': 'under',
                                'path': '{build_root}/',
                                'suffix': ' as normal',
                            },
                            {
                                'kind': 'sources',
                                'methods': ( 'BuildTest', 'Test' ),
                            },
                        ),
                    },
                },
            ),
        },
        'cli': {
            'enable': ( '--test', '--cov' ),
            'clean': (
                ( '--test', '--cov', '--clean' ),
            ),
        },
    },
    'cxx-profiles': {
        'title': 'Collated C++ Profiles Report',
        'methods': {
            'method': 'CollateCxxProfilesIndex',
            'params': (
                {
                    'kind': 'destination',
                    'prose': 'specify destination, default',
                    'path': '{artefacts_root}/cxx-profiles/',
                },
            ),
        },
        'cli': {
            'note': {
                'text': 'Often used with',
                'emphasis': '--cxx-profiles-enforce=<profile1>,<profile2>',
            },
            'enable': ( '--cxx-profiles', '--cxx-profiles-report' ),
            'clean': (
                ( '--cxx-profiles', '--cxx-profiles-report', '--clean' ),
                ( '--cxx-profiles', '--cxx-profiles-report', '--remove-builds' ),
            ),
        },
    },
}


def _version_sort_key( version ):
    from cuppa.core.toolchain_actions import _version_sort_key as sort_key

    return sort_key( version )


def _format_path_template( path ):
    return as_emphasised( path )


def _param_label( name ):
    return as_notice( '{}:'.format( name ) )


def _format_destination_param( param ):
    label = _param_label( 'destination' )
    prose = param.get( 'prose' ) or ''
    path = _format_path_template( param[ 'path' ] )
    suffix = param.get( 'suffix' ) or ''
    if prose:
        return '{} {} {}{}'.format( label, prose, path, suffix )
    return '{}{}{}'.format( label, path, suffix )


def _env_method( name ):
    return as_info( as_emphasised( 'env.{}()'.format( name ) ) )


def _plain_env_method( name ):
    return as_emphasised( 'env.{}()'.format( name ) )


def _cli_invocation( flags ):
    return as_emphasised( ' '.join( flags ) )


def _format_cli_note( note ):
    if isinstance( note, dict ):
        return (
            as_subdued( 'Note: {} '.format( note.get( 'text', '' ) ) )
            + as_subdued( as_emphasised( note[ 'emphasis' ] ) )
        )
    return as_subdued( 'Note: {}'.format( note ) )


def _colour_toolchain_names( names, preferred ):
    if not names:
        return as_subdued( '(none on this system)' )
    parts = []
    for index, name in enumerate( names ):
        if index:
            parts.append( as_subdued( ', ' ) )
        if name == preferred:
            parts.append( as_info( as_emphasised( name ) ) )
        else:
            parts.append( name )
    return ''.join( parts )


def _wrapped_toolchain_names( names, preferred, indent_prefix, branch_prefix ):
    gap = storage.glyphs()[3]
    plain = ', '.join( names )
    lines = storage.wrapped( plain, _TOOLCHAIN_WRAP_WIDTH ) or [ plain ]
    if len( lines ) == 1:
        return [
            as_subdued( indent_prefix + branch_prefix )
            + _colour_toolchain_names( names, preferred ),
        ]
    rendered = []
    continuation_prefix = indent_prefix + gap
    for line_index, line in enumerate( lines ):
        names_on_line = [ piece.strip() for piece in line.split( ',' ) if piece.strip() ]
        if line_index == 0:
            prefix = indent_prefix + branch_prefix
        else:
            prefix = continuation_prefix
        rendered.append(
            as_subdued( prefix )
            + _colour_toolchain_names( names_on_line, preferred ),
        )
    return rendered


def group_supporting_toolchains_by_family( cuppa_env, kind_id ):
    """Group supporting toolchain rows by family, newest first within each family."""
    rows = supporting_toolchain_rows_for_kind( cuppa_env, kind_id )
    by_family = defaultdict( list )
    for row in rows:
        by_family[ row[ 'family' ] ].append( row )

    groups = []
    for family in sorted( by_family.keys() ):
        family_rows = sorted(
            by_family[ family ],
            key=lambda row: ( _version_sort_key( row[ 'version' ] ), row[ 'name' ] ),
            reverse=True,
        )
        names = [ row[ 'name' ] for row in family_rows ]
        preferred = family if family in names else names[0]
        groups.append(
            {
                'family': family,
                'names': names,
                'preferred': preferred,
                'rows': family_rows,
            },
        )
    return groups


def serialise_toolchains_by_family( cuppa_env, kind_id ):
    """JSON-friendly toolchain groups for one report kind."""
    return [
        {
            'family': group[ 'family' ],
            'preferred': group[ 'preferred' ],
            'toolchains': list( group[ 'names' ] ),
        }
        for group in group_supporting_toolchains_by_family( cuppa_env, kind_id )
    ]


def _write_line( out, prefix, branch, label ):
    out.write( as_subdued( prefix + branch ) + label + '\n' )


def _write_blank_row( out, prefix ):
    _write_line( out, prefix, storage.glyphs()[2], '' )


def _write_trunk_continuation( out ):
    """Single vertical line continuing the root tree branch between report kinds."""
    out.write( as_subdued( storage.glyphs()[2] ) + '\n' )


def _child_prefix( prefix, branch ):
    tee, elbow, pipe, gap = storage.glyphs()
    return prefix + ( gap if branch == elbow else pipe )


def _render_method_params( out, prefix, params ):
    tee, elbow, pipe, gap = storage.glyphs()
    for param_index, param in enumerate( params ):
        param_last = param_index == len( params ) - 1
        branch = elbow if param_last else tee
        child_prefix = _child_prefix( prefix, branch )

        if param[ 'kind' ] == 'destination':
            _write_line(
                out,
                prefix,
                branch,
                _format_destination_param( param ),
            )
            continue

        _write_line( out, prefix, branch, _param_label( 'sources' ) )
        _write_blank_row( out, child_prefix )

        nested_method = param.get( 'child' )
        if nested_method:
            _render_method_tree(
                out,
                child_prefix,
                elbow,
                nested_method,
            )
            continue

        capture_methods = param.get( 'methods' ) or ()
        for method_index, method_name in enumerate( capture_methods ):
            method_last = method_index == len( capture_methods ) - 1
            method_branch = elbow if method_last else tee
            _write_line(
                out,
                child_prefix,
                method_branch,
                _plain_env_method( method_name ),
            )


def _render_method_tree( out, prefix, branch, node ):
    _write_line( out, prefix, branch, _env_method( node[ 'method' ] ) )
    params = node.get( 'params' ) or ()
    if not params:
        return
    child_prefix = _child_prefix( prefix, branch )
    _write_blank_row( out, child_prefix )
    _render_method_params( out, child_prefix, params )


def _render_methods_tree( out, prefix, method_root ):
    tee, elbow, pipe, gap = storage.glyphs()
    _write_line( out, prefix, tee, 'Methods:' )
    content_prefix = prefix + pipe
    _write_blank_row( out, content_prefix )
    _render_method_tree( out, content_prefix, elbow, method_root )


def _render_cli_tree( out, prefix, cli ):
    tee, elbow, pipe, gap = storage.glyphs()
    _write_line( out, prefix, tee, 'CLI:' )
    content_prefix = prefix + pipe
    _write_blank_row( out, content_prefix )

    note = cli.get( 'note' )
    if note:
        _write_line( out, content_prefix, tee, _format_cli_note( note ) )
        _write_blank_row( out, content_prefix )

    _write_line( out, content_prefix, tee, _param_label( 'enable' ) )
    _write_line( out, content_prefix + pipe, elbow, _cli_invocation( cli[ 'enable' ] ) )

    clean_lines = cli.get( 'clean' ) or ()
    _write_line( out, content_prefix, elbow, _param_label( 'clean' ) )
    clean_prefix = content_prefix + gap
    for clean_index, flags in enumerate( clean_lines ):
        clean_last = clean_index == len( clean_lines ) - 1
        clean_branch = elbow if clean_last else tee
        _write_line( out, clean_prefix, clean_branch, _cli_invocation( flags ) )


def _render_toolchains_tree( out, prefix, toolchain_groups ):
    tee, elbow, pipe, gap = storage.glyphs()
    _write_line( out, prefix, elbow, 'Toolchains:' )
    toolchains_prefix = prefix + gap

    if not toolchain_groups:
        _write_blank_row( out, toolchains_prefix )
        _write_line(
            out,
            toolchains_prefix,
            elbow,
            as_subdued( '(none on this system)' ),
        )
        return

    _write_blank_row( out, toolchains_prefix )

    for group_index, group in enumerate( toolchain_groups ):
        if group_index:
            _write_blank_row( out, toolchains_prefix )

        group_last = group_index == len( toolchain_groups ) - 1
        group_branch = elbow if group_last else tee
        group_under = gap if group_last else pipe
        family_label = as_emphasised( '{}:'.format( group[ 'family' ] ) )
        _write_line( out, toolchains_prefix, group_branch, family_label )

        names_prefix = toolchains_prefix + group_under
        for line in _wrapped_toolchain_names(
            group[ 'names' ],
            group[ 'preferred' ],
            names_prefix,
            elbow,
        ):
            out.write( line + '\n' )


def _render_report_kind( out, prefix, top_branch, kind_id, cuppa_env ):
    tee, elbow, pipe, gap = storage.glyphs()
    catalog = REPORT_CATALOG[ kind_id ]

    _write_line( out, prefix, top_branch, as_emphasised( catalog[ 'title' ] ) )
    section_prefix = prefix + ( gap if top_branch == elbow else pipe )

    _write_blank_row( out, section_prefix )
    _render_methods_tree( out, section_prefix, catalog[ 'methods' ] )
    _write_blank_row( out, section_prefix )
    _render_cli_tree( out, section_prefix, catalog[ 'cli' ] )
    _write_blank_row( out, section_prefix )
    _render_toolchains_tree(
        out,
        section_prefix,
        group_supporting_toolchains_by_family( cuppa_env, kind_id ),
    )


def _format_root_legend_label( placeholder, rel_root, abs_root ):
    return '{}: {} ({})'.format(
        as_notice( placeholder ),
        as_info( rel_root ),
        as_subdued( storage.display_path( abs_root ) ),
    )


def _render_root_legend_tree(
        out,
        abs_artefacts_root,
        rel_artefacts_root,
        abs_build_root,
        rel_build_root,
):
    """Show resolved roots as the first branches in the report tree."""
    tee, elbow, pipe, gap = storage.glyphs()
    _write_line(
        out,
        '',
        tee,
        _format_root_legend_label(
            '{artefacts_root}',
            rel_artefacts_root,
            abs_artefacts_root,
        ),
    )
    _write_line(
        out,
        '',
        tee,
        _format_root_legend_label(
            '{build_root}',
            rel_build_root,
            abs_build_root,
        ),
    )
    _write_blank_row( out, '' )


def _abs_build_root_from_env( cuppa_env ):
    rel_build_root = cuppa_env.get( 'build_root' ) or '_build'
    if os.path.isabs( rel_build_root ):
        return os.path.abspath( rel_build_root )
    sconstruct_dir = cuppa_env.get( 'sconstruct_dir' ) or os.getcwd()
    return os.path.abspath( os.path.join( sconstruct_dir, rel_build_root ) )


def render_available_reports_text( cuppa_env, out, abs_artefacts_root, rel_artefacts_root ):
    """Write the judgement-tree style report for ``--list-available-reports``."""
    tee, elbow, pipe, _gap = storage.glyphs()
    rel_build_root = cuppa_env.get( 'build_root' ) or '_build'
    abs_build_root = _abs_build_root_from_env( cuppa_env )

    out.write( 'Report kinds available with current toolchains\n' )
    out.write( as_subdued( pipe ) + '\n' )

    _render_root_legend_tree(
        out,
        abs_artefacts_root,
        rel_artefacts_root,
        abs_build_root,
        rel_build_root,
    )

    kinds = REPORT_DISPLAY_ORDER
    for kind_index, kind_id in enumerate( kinds ):
        kind_last = kind_index == len( kinds ) - 1
        top_branch = elbow if kind_last else tee
        _render_report_kind(
            out,
            '',
            top_branch,
            kind_id,
            cuppa_env,
        )
        if not kind_last:
            _write_trunk_continuation( out )

    out.write(
        '\n'
        + as_subdued(
            'Full artefact-tree removal (--remove-artefacts) is not implemented yet.',
        )
        + '\n',
    )
