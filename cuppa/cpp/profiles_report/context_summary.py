#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   C++ Profiles report — Overview context (prof-report-context-summary)
#-------------------------------------------------------------------------------

import os
import re

from cuppa.cpp.profiles_report.constants import UNCLASSIFIED_RULE_ID
from cuppa.cpp.profiles_report.profiles import documented_rule_ids_for_profile
from cuppa.cpp.profiles_report.build_catalog import assign_build_display_ids
from cuppa.cpp.profiles_report.report_html import rule_doc_href, variant_display_from_dir

_INCLUDE_STACK_LINE_RE = re.compile( r'^\.+\s+(\S+)\s*$' )

SOURCE_LINES_V1_METHOD = 'source_lines_v1'
PARSED_FILES_METHOD = 'include_stack_h_v1'
COMPILE_UNITS_METHOD = 'notify_progress_hook_v1'

TOP_RULE_LIMIT = 10


def normalize_report_path( path ):
    """Return one stable absolute path for session set membership."""
    if not path:
        return None
    text = str( path ).strip()
    if not text:
        return None
    return os.path.normpath( os.path.realpath( os.path.expanduser( text ) ) )


def parse_include_stack_line( line ):
    """Parse one ``-H`` include-stack line, or return ``None`` if it does not match."""
    if not line:
        return None
    match = _INCLUDE_STACK_LINE_RE.match( line.rstrip( '\r\n' ) )
    if not match:
        return None
    return normalize_report_path( match.group( 1 ) )


def _classify_source_line_v1( stripped, in_block_comment ):
    """Return ``(counts_as_source_line, new_in_block_comment)`` for one physical line."""
    index = 0
    length = len( stripped )
    saw_code = False

    while index < length:
        if in_block_comment:
            end = stripped.find( '*/', index )
            if end < 0:
                return False, True
            index = end + 2
            in_block_comment = False
            continue

        if stripped.startswith( '//', index ):
            break

        if stripped.startswith( '/*', index ):
            end = stripped.find( '*/', index + 2 )
            if end < 0:
                in_block_comment = True
                break
            index = end + 2
            continue

        char = stripped[ index ]
        if char in ( '"', "'" ):
            quote = char
            index += 1
            while index < length:
                if stripped[ index ] == '\\' and index + 1 < length:
                    index += 2
                    continue
                if stripped[ index ] == quote:
                    index += 1
                    break
                index += 1
            continue

        if not stripped[ index ].isspace():
            saw_code = True
        index += 1

    if in_block_comment:
        return False, True

    if not saw_code:
        return False, False

    for char in stripped:
        if not char.isspace():
            if char == '#':
                return False, False
            break
    return True, False


def count_source_lines_v1( lines ):
    """Count lexical source lines across an iterable of physical lines."""
    total = 0
    in_block_comment = False
    for line in lines:
        stripped = line.rstrip( '\r\n' )
        if not stripped.strip():
            if in_block_comment:
                continue
            continue
        counts, in_block_comment = _classify_source_line_v1(
            stripped.lstrip(),
            in_block_comment,
        )
        if counts:
            total += 1
    return total


def source_line_count( path, method=SOURCE_LINES_V1_METHOD ):
    """Return the source line count for ``path``, or ``None`` when unreadable."""
    if method != SOURCE_LINES_V1_METHOD:
        raise ValueError(
            'Unsupported source line method: {!r}'.format( method ),
        )
    try:
        with open( path, encoding='utf-8', errors='replace' ) as handle:
            return count_source_lines_v1( handle )
    except OSError:
        return None


def _rollup_rule_map( model ):
    rules = {}
    for rule in model.get( 'rollup', {} ).get( 'rules', [] ):
        key = ( rule.get( 'profile' ), rule[ 'rule_id' ] )
        rules[ key ] = rule
    return rules


def _rollup_file_paths( model ):
    return {
        file_entry[ 'path' ]
        for file_entry in model.get( 'rollup', {} ).get( 'files', [] )
        if file_entry.get( 'path' )
    }


def _pct( numerator, denominator, places=1 ):
    if not denominator:
        return None
    return round( 100.0 * float( numerator ) / float( denominator ), places )


def _pct_of_total( numerator, denominator, places=1 ):
    value = _pct( numerator, denominator, places )
    return value if value is not None else 0.0


def _build_rule_matrix_row(
    profile_name,
    rule_id,
    rule,
    files_with_violations,
    unique_violation_count,
    total_references,
    *,
    rule_label=None,
    catalog=None,
    session_peak_refs=0,
):
    from cuppa.cpp.profiles_report.variant_roll_up_display import (
        peak_refs_total_for_row,
    )

    refs = rule.get( 'total_references', 0 )
    unique_files = rule.get( 'unique_files', 0 )
    unique_lines = rule.get( 'unique_line_count', 0 )
    peak_refs = peak_refs_total_for_row(
        rule.get( 'variant_counts' ),
        catalog or [],
    )
    return {
        'profile': profile_name,
        'rule_id': rule_id,
        'rule_label': rule_label or rule_id,
        'total_references': refs,
        'peak_references': peak_refs,
        'unique_files': unique_files,
        'unique_lines': unique_lines,
        'observed': refs > 0,
        'pct_of_session_files': _pct_of_total(
            unique_files,
            files_with_violations,
        ),
        'pct_of_session_lines': _pct_of_total(
            unique_lines,
            unique_violation_count,
        ),
        'pct_of_session_refs': _pct_of_total( refs, total_references ),
        'pct_of_session_peak_refs': _pct_of_total(
            peak_refs,
            session_peak_refs,
        ),
        'doc_href': rule_doc_href( profile_name, rule_id ),
    }


def _session_peak_refs( rollup_rules, catalog ):
    from cuppa.cpp.profiles_report.variant_roll_up_display import (
        peak_refs_total_for_row,
    )

    total = 0
    for rule in rollup_rules:
        total += peak_refs_total_for_row(
            rule.get( 'variant_counts' ),
            catalog,
        )
    return total


def _build_concentration(
    rollup_rules,
    total_references,
    unique_violation_count,
    files_with_violations,
    catalog,
    session_peak_refs,
):
    rows = []
    for rule in rollup_rules:
        refs = rule.get( 'total_references', 0 )
        if not refs:
            continue
        profile_name = rule.get( 'profile' )
        rule_id = rule[ 'rule_id' ]
        rows.append(
            _build_rule_matrix_row(
                profile_name,
                rule_id,
                rule,
                files_with_violations,
                unique_violation_count,
                total_references,
                rule_label='{}::{}'.format( profile_name, rule_id ),
                catalog=catalog,
                session_peak_refs=session_peak_refs,
            ),
        )
    rows.sort(
        key=lambda entry: (
            -entry[ 'total_references' ],
            entry.get( 'profile' ) or '',
            entry[ 'rule_id' ],
        ),
    )
    return { 'top_rules': rows[ :TOP_RULE_LIMIT ] }


def _build_profile_matrix(
    profiles_enforce,
    rule_map,
    total_references,
    files_with_violations,
    unique_violation_count,
    catalog,
    session_peak_refs,
):
    profiles = []
    for profile_name in profiles_enforce:
        documented = documented_rule_ids_for_profile( profile_name )
        observed_ids = {
            rule_id
            for ( profile, rule_id ) in rule_map.keys()
            if profile == profile_name
        }
        rule_ids = list( documented )
        for rule_id in sorted( observed_ids ):
            if rule_id not in rule_ids:
                rule_ids.append( rule_id )

        rows = []
        observed_count = 0
        for rule_id in rule_ids:
            rule = rule_map.get( ( profile_name, rule_id ), {} )
            refs = rule.get( 'total_references', 0 )
            if refs > 0:
                observed_count += 1
            rows.append(
                _build_rule_matrix_row(
                    profile_name,
                    rule_id,
                    rule,
                    files_with_violations,
                    unique_violation_count,
                    total_references,
                    catalog=catalog,
                    session_peak_refs=session_peak_refs,
                ),
            )
        rows.sort(
            key=lambda entry: (
                -entry[ 'total_references' ],
                entry[ 'rule_id' ],
            ),
        )
        profiles.append(
            {
                'profile': profile_name,
                'documented_rule_count': len( documented ),
                'observed_rule_count': observed_count,
                'rules': rows,
            },
        )
    return profiles


def _build_scope_breakdown( model, rollup ):
    """Per variant/toolchain totals (across sconscripts) plus aggregate and union rows."""
    groups = {}
    for scope in model.get( 'scopes', [] ):
        variant_display = variant_display_from_dir( scope.get( 'variant_dir', '' ) )
        display_parts = variant_display.split( '/', 1 )
        variant_label = scope.get( 'variant_label', display_parts[ 0 ] )
        variant_display_tail = display_parts[ 1 ] if len( display_parts ) > 1 else ''
        toolchain = scope.get( 'toolchain', '' )
        key = ( variant_label, variant_display_tail, toolchain )
        entry = groups.setdefault(
            key,
            {
                'build_key': list( key ),
                'variant_label': variant_label,
                'variant_display_tail': variant_display_tail,
                'toolchain': toolchain,
                'violations': 0,
                'rules': 0,
                'files': 0,
                'references': 0,
            },
        )
        entry[ 'violations' ] += scope.get( 'unique_line_count', 0 )
        entry[ 'rules' ] += scope.get( 'unique_rule_count', 0 )
        entry[ 'files' ] += scope.get( 'unique_file_count', 0 )
        entry[ 'references' ] += scope.get(
            'build_references',
            scope.get( 'total_references', 0 ),
        )

    rows = sorted(
        groups.values(),
        key=lambda entry: (
            entry[ 'variant_label' ],
            entry[ 'variant_display_tail' ],
            entry[ 'toolchain' ],
        ),
    )
    assign_build_display_ids( rows )
    session_files = len( rollup.get( 'files', [] ) )
    aggregate_references = sum( row[ 'references' ] for row in rows )
    scope_references = sum(
        scope.get( 'build_references', scope.get( 'total_references', 0 ) )
        for scope in model.get( 'scopes', [] )
    )
    return {
        'rows': rows,
        'aggregate': {
            'violations': sum( row[ 'violations' ] for row in rows ),
            'rules': sum( row[ 'rules' ] for row in rows ),
            'files': sum( row[ 'files' ] for row in rows ),
            'references': aggregate_references,
        },
        'session': {
            'violations': rollup.get( 'unique_violation_count', 0 ),
            'rules': rollup.get( 'unique_rule_count', 0 ),
            'files': session_files,
            'references': rollup.get( 'total_references', 0 ),
            'raw_references': rollup.get(
                'raw_total_references',
                scope_references,
            ),
            'build_count': len( rows ),
        },
    }


def _build_codebase_metrics(
    model,
    parsed_files,
    translation_units,
    include_tier_metrics,
):
    rollup = model.get( 'rollup', {} )
    violating_paths = _rollup_file_paths( model )
    files_with_violations = len( violating_paths )
    unique_violation_lines = rollup.get( 'unique_violation_count', 0 )

    codebase = {
        'files_with_violations': files_with_violations,
        'unique_violation_lines': unique_violation_lines,
    }

    methodology = {
        'loc_count': SOURCE_LINES_V1_METHOD,
        'loc_count_note': (
            'Non-blank C++ lines; excludes //, block comments, and # directives '
            '(lexical; see plan)'
        ),
    }

    if parsed_files is not None:
        files_parsed = len( parsed_files )
        codebase[ 'files_parsed' ] = files_parsed
        pct = _pct( files_with_violations, files_parsed, places=4 )
        if pct is not None:
            codebase[ 'files_with_violations_pct' ] = pct
        methodology[ 'parsed_files' ] = PARSED_FILES_METHOD

    if translation_units is not None:
        codebase[ 'translation_units_compiled' ] = len( translation_units )
        methodology[ 'compile_units' ] = COMPILE_UNITS_METHOD

    if not include_tier_metrics:
        return codebase, methodology

    source_lines_total = 0
    missing_source_paths = 0
    for path in sorted( violating_paths ):
        line_count = source_line_count( path )
        if line_count is None:
            missing_source_paths += 1
            continue
        source_lines_total += line_count

    if source_lines_total:
        codebase[ 'source_lines_in_violating_files' ] = source_lines_total
        line_pct = _pct( unique_violation_lines, source_lines_total, places=2 )
        if line_pct is not None:
            codebase[ 'violation_line_pct_in_affected_files' ] = line_pct
        per_thousand = round(
            1000.0 * float( unique_violation_lines ) / float( source_lines_total ),
            1,
        )
        codebase[ 'violation_lines_per_1000_source_lines_affected' ] = per_thousand

    if missing_source_paths:
        methodology[ 'missing_violating_source_paths' ] = missing_source_paths

    return codebase, methodology


def resolve_context_mode( env ):
    """Return ``full``, ``rules-only``, or ``off`` for Overview context emission."""
    mode = env.get( 'cxx_profiles_report_context' )
    if mode in ( 'off', 'rules-only', 'full' ):
        return mode
    return 'full'


def build_report_context(
    model,
    env,
    *,
    parsed_files=None,
    translation_units=None,
    context_mode='full',
):
    """Build the optional top-level ``context`` object for JSON and Overview HTML."""
    if context_mode == 'off':
        return None

    rollup = model.get( 'rollup', {} )
    total_references = rollup.get( 'total_references', 0 )
    rollup_rules = rollup.get( 'rules', [] )
    catalog = model.get( 'build_catalog' ) or []
    session_peak_refs = _session_peak_refs( rollup_rules, catalog )
    rule_map = _rollup_rule_map( model )

    profiles_enforce = list( env.get( 'cxx_profiles_enforce' ) or [] )
    if not profiles_enforce:
        profiles_enforce = sorted(
            {
                profile
                for profile, _rule_id in rule_map.keys()
                if profile
            },
        )
    if not profiles_enforce and UNCLASSIFIED_RULE_ID in {
        rule_id for _profile, rule_id in rule_map.keys()
    }:
        profiles_enforce = []

    files_with_violations = len( _rollup_file_paths( model ) )
    unique_violation_count = rollup.get( 'unique_violation_count', 0 )

    include_tier_metrics = context_mode == 'full'
    codebase, methodology = _build_codebase_metrics(
        model,
        parsed_files if include_tier_metrics else None,
        translation_units if include_tier_metrics else None,
        include_tier_metrics=include_tier_metrics,
    )

    context = {
        'methodology': methodology,
        'codebase': codebase,
        'concentration': _build_concentration(
            rollup_rules,
            total_references,
            unique_violation_count,
            files_with_violations,
            catalog,
            session_peak_refs,
        ),
        'profiles': _build_profile_matrix(
            profiles_enforce,
            rule_map,
            total_references,
            files_with_violations,
            unique_violation_count,
            catalog,
            session_peak_refs,
        ),
        'builds': _build_scope_breakdown( model, rollup ),
    }
    return context
