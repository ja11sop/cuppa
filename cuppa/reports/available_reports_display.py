#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Text tree for --list-available-reports
#-------------------------------------------------------------------------------

from collections import defaultdict

from cuppa.colourise import as_emphasised, as_info, as_notice, as_subdued
from cuppa.reports.registry import (
    rel_artefacts_root_from_env,
    supporting_toolchain_rows_for_kind,
)
from cuppa.utility import storage


REPORT_DISPLAY_ORDER = ( 'test', 'coverage', 'cxx-profiles' )

_TOOLCHAIN_WRAP_WIDTH = 72


REPORT_CATALOG = {
    'test': {
        'title': 'Collated Test Report',
        'methods': {
            'heading': 'multi-variant index',
            'method': 'CollateTestReportIndex',
            'details': (
                {
                    'label': 'destination',
                    'prose': 'specify destination, usually',
                    'path': '{artefacts_root}/test/',
                },
            ),
            'next': {
                'heading': 'report generation',
                'method': 'GenerateHtmlTestReport',
                'details': (
                    {
                        'label': 'Destination',
                        'prose': 'under',
                        'path': '_build/',
                        'suffix': ' as normal',
                    },
                ),
                'next': {
                    'heading': 'data capture',
                    'methods': ( 'BuildTest', 'Test' ),
                },
            },
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
            'heading': 'multi-variant index',
            'method': 'CollateCoverageIndex',
            'details': (
                {
                    'label': 'destination',
                    'prose': 'specify destination, usually',
                    'path': '{artefacts_root}/coverage/',
                },
            ),
            'next': {
                'heading': 'report generation',
                'method': 'CollateCoverageFiles',
                'details': (
                    {
                        'label': 'destination',
                        'prose': 'under',
                        'path': '_build/',
                        'suffix': ' as normal',
                    },
                ),
                'next': {
                    'heading': 'data capture',
                    'methods': ( 'BuildTest', 'Test' ),
                },
            },
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
            'heading': 'multi-variant index',
            'method': 'CxxProfilesReport',
            'details': (
                {
                    'label': 'destination',
                    'prose': 'specify destination, usually',
                    'path': '{artefacts_root}/cxx-profiles/',
                },
            ),
        },
        'cli': {
            'enable': ( '--cxx-profiles', '--cxx-profiles-report' ),
            'clean': (
                ( '--cxx-profiles', '--cxx-profiles-report', '--clean' ),
                ( '--cxx-profiles', '--cxx-profiles-report', '--remove-builds' ),
            ),
        },
        'note': (
            'Also requires --cxx-profiles-enforce= with a Profiles-capable Clang when '
            'collecting diagnostics',
        ),
    },
}


def _version_sort_key( version ):
    from cuppa.core.toolchain_actions import _version_sort_key as sort_key

    return sort_key( version )


def _substitute_paths( text, artefacts_root ):
    return text.format( artefacts_root=artefacts_root )


def _env_method( name ):
    return as_info( as_emphasised( 'env.{}()'.format( name ) ) )


def _cli_invocation( flags ):
    return as_emphasised( ' '.join( flags ) )


def _destination_detail( detail, artefacts_root ):
    label = as_notice( '{}:'.format( detail[ 'label' ] ) )
    prose = detail.get( 'prose' ) or ''
    path = as_emphasised( _substitute_paths( detail[ 'path' ], artefacts_root ) )
    suffix = detail.get( 'suffix' ) or ''
    if prose:
        return '{} {} {}{}'.format( label, prose, path, suffix )
    return '{}{}{}'.format( label, path, suffix )


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
    coloured = _colour_toolchain_names( names, preferred )
    plain = ', '.join( names )
    lines = storage.wrapped( plain, _TOOLCHAIN_WRAP_WIDTH ) or [ plain ]
    if len( lines ) == 1:
        return [
            as_subdued( indent_prefix + branch_prefix )
            + coloured,
        ]
    rendered = []
    continuation_prefix = indent_prefix + storage.glyphs()[3] + storage.glyphs()[3]
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


def _render_methods_node( out, prefix, branch, node, artefacts_root ):
    """Render one nested Methods node and optional ``next`` sibling."""
    tee, elbow, pipe, gap = storage.glyphs()
    has_next = bool( node.get( 'next' ) )

    _write_line(
        out,
        prefix,
        branch,
        as_subdued( '{}:'.format( node[ 'heading' ] ) ),
    )
    content_prefix = prefix + gap

    if node.get( 'method' ):
        out.write( as_subdued( content_prefix ) + _env_method( node[ 'method' ] ) + '\n' )
        details = node.get( 'details' ) or ()
        for detail_index, detail in enumerate( details ):
            detail_last = detail_index == len( details ) - 1 and not has_next
            detail_branch = elbow if detail_last else tee
            _write_line(
                out,
                content_prefix,
                detail_branch,
                _destination_detail( detail, artefacts_root ),
            )
    else:
        capture_methods = node.get( 'methods' ) or ()
        for capture_index, method_name in enumerate( capture_methods ):
            capture_last = capture_index == len( capture_methods ) - 1 and not has_next
            capture_branch = elbow if capture_last else tee
            _write_line(
                out,
                content_prefix,
                capture_branch,
                as_emphasised( 'env.{}()'.format( method_name ) ),
            )

    if has_next:
        _render_methods_node(
            out,
            prefix,
            elbow,
            node[ 'next' ],
            artefacts_root,
        )


def _render_methods_tree( out, prefix, methods_root, artefacts_root ):
    tee, elbow, pipe, gap = storage.glyphs()
    _write_line( out, prefix, tee, as_emphasised( 'Methods:' ) )
    _render_methods_node(
        out,
        prefix + pipe,
        elbow,
        methods_root,
        artefacts_root,
    )


def _render_cli_tree( out, prefix, cli ):
    tee, elbow, pipe, gap = storage.glyphs()
    _write_line( out, prefix, tee, as_emphasised( 'CLI:' ) )
    cli_prefix = prefix + pipe

    _write_line( out, cli_prefix, tee, as_subdued( 'enable:' ) )
    enable_prefix = cli_prefix + pipe
    _write_line( out, enable_prefix, elbow, _cli_invocation( cli[ 'enable' ] ) )

    clean_lines = cli.get( 'clean' ) or ()
    _write_line( out, cli_prefix, elbow, as_subdued( 'clean:' ) )
    clean_prefix = cli_prefix + gap
    for clean_index, flags in enumerate( clean_lines ):
        clean_last = clean_index == len( clean_lines ) - 1
        clean_branch = elbow if clean_last else tee
        _write_line( out, clean_prefix, clean_branch, _cli_invocation( flags ) )


def _render_toolchains_tree( out, prefix, toolchain_groups ):
    tee, elbow, pipe, gap = storage.glyphs()
    _write_line( out, prefix, elbow, as_emphasised( 'Toolchains:' ) )
    toolchains_prefix = prefix + gap

    if not toolchain_groups:
        _write_line(
            out,
            toolchains_prefix,
            elbow,
            as_subdued( '(none on this system)' ),
        )
        return

    for group_index, group in enumerate( toolchain_groups ):
        group_last = group_index == len( toolchain_groups ) - 1
        group_branch = elbow if group_last else tee
        group_under = gap if group_last else pipe
        family_label = as_info( as_emphasised( '{}:'.format( group[ 'family' ] ) ) )
        _write_line( out, toolchains_prefix, group_branch, family_label )

        names_prefix = toolchains_prefix + group_under
        for line in _wrapped_toolchain_names(
            group[ 'names' ],
            group[ 'preferred' ],
            names_prefix,
            elbow,
        ):
            out.write( line + '\n' )


def _render_report_kind( out, prefix, top_branch, kind_id, cuppa_env, artefacts_root ):
    tee, elbow, pipe, gap = storage.glyphs()
    catalog = REPORT_CATALOG[ kind_id ]

    _write_line( out, prefix, top_branch, as_emphasised( catalog[ 'title' ] ) )
    section_prefix = prefix + ( gap if top_branch == elbow else pipe )

    _render_methods_tree( out, section_prefix, catalog[ 'methods' ], artefacts_root )
    _render_cli_tree( out, section_prefix, catalog[ 'cli' ] )
    _render_toolchains_tree(
        out,
        section_prefix,
        group_supporting_toolchains_by_family( cuppa_env, kind_id ),
    )

    note = catalog.get( 'note' )
    if note:
        _write_line( out, section_prefix, tee, as_subdued( 'Note: {}'.format( note ) ) )


def render_available_reports_text( cuppa_env, out, abs_artefacts_root, rel_artefacts_root ):
    """Write the judgement-tree style report for ``--list-available-reports``."""
    tee, elbow, pipe, _gap = storage.glyphs()
    display_root = storage.display_path( abs_artefacts_root )

    out.write(
        'Artefacts root: {} ({})\n\n'.format(
            as_info( display_root ),
            as_subdued( rel_artefacts_root ),
        ),
    )
    out.write( 'Report kinds available with current toolchains\n' )
    out.write( as_subdued( pipe ) + '\n' )

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
            rel_artefacts_root,
        )

    out.write(
        '\nFull artefact-tree removal (--remove-artefacts) is not implemented yet.\n',
    )
