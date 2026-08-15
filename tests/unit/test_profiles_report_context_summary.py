#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.cxx_profiles_report import (
    ProfilesInventory,
    ProfilesScope,
    parse_profiles_diagnostic,
)
from cuppa.cpp.profiles_report.context_summary import (
    build_report_context,
    count_source_lines_v1,
    parse_include_stack_line,
    source_line_count,
)
from cuppa.cpp.profiles_report.profiles.std_init import documented_rule_ids

pytestmark = pytest.mark.unit

_SAMPLE_SCOPE = ProfilesScope(
    sconscript='./widget/sconscript',
    variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    toolchain='clang24_profiles',
    variant_label='dbg',
)

_LINE = (
    "/home/user/project/src/widget.cpp:10:12: error: pointer to uninitialized "
    "memory must be marked '[[ref_to_uninit]]' under profile 'std::init'"
)


def _sample_inventory():
    inventory = ProfilesInventory()
    inventory.record( _SAMPLE_SCOPE, parse_profiles_diagnostic( _LINE ) )
    return inventory


def test_parse_include_stack_line_accepts_dot_prefixes():
    assert parse_include_stack_line( '. /tmp/widget/header.hpp' ) == '/tmp/widget/header.hpp'
    assert parse_include_stack_line( '.. /tmp/widget/header.hpp' ) == '/tmp/widget/header.hpp'
    assert parse_include_stack_line( 'ordinary compiler noise' ) is None


def test_count_source_lines_v1_excludes_comments_blanks_and_preprocessor():
    lines = [
        '\n',
        '// whole line comment\n',
        '#include <vector>\n',
        'int Value = 0;\n',
        'const char* Url = "http://example.com"; // not a comment marker\n',
        '/* block start\n',
        'still comment\n',
        '*/\n',
        'return Value;\n',
    ]
    assert count_source_lines_v1( lines ) == 3


def test_source_line_count_reads_file( tmp_path ):
    source = tmp_path / 'widget.cpp'
    source.write_text(
        '#include "widget.hpp"\n\n'
        'int main() { return 0; }\n',
        encoding='utf-8',
    )
    assert source_line_count( str( source ) ) == 1


def test_build_report_context_includes_zero_filled_profile_matrix():
    inventory = _sample_inventory()
    model = inventory.as_report_model()
    env = {
        'cxx_profiles_enforce': [ 'std::init' ],
        'cxx_profiles_report_context': 'rules-only',
    }
    context = build_report_context(
        model,
        env,
        context_mode='rules-only',
    )
    assert context[ 'profiles' ][ 0 ][ 'profile' ] == 'std::init'
    assert context[ 'builds' ][ 'rows' ]
    assert context[ 'builds' ][ 'session' ][ 'violations' ] == 1
    rule_ids = [ rule[ 'rule_id' ] for rule in context[ 'profiles' ][ 0 ][ 'rules' ] ]
    assert 'ref_to_uninit' in rule_ids
    assert 'uninit_read' in rule_ids
    assert set( documented_rule_ids() ).issubset( set( rule_ids ) )
    zero_rule = next(
        rule for rule in context[ 'profiles' ][ 0 ][ 'rules' ]
        if rule[ 'rule_id' ] == 'uninit_read'
    )
    assert zero_rule[ 'observed' ] is False
    assert zero_rule[ 'total_references' ] == 0


def test_build_report_context_matrix_includes_peak_refs():
    inventory = _sample_inventory()
    model = inventory.as_report_model()
    from cuppa.cpp.profiles_report.report_html import enrich_model_for_html

    enrich_model_for_html( model, {}, 'local', '', '', '' )
    context = build_report_context(
        model,
        { 'cxx_profiles_enforce': [ 'std::init' ] },
        context_mode='rules-only',
    )
    observed = next(
        rule for rule in context[ 'concentration' ][ 'top_rules' ]
        if rule[ 'rule_id' ] == 'ref_to_uninit'
    )
    assert observed[ 'peak_references' ] == 1
    assert observed[ 'pct_of_session_peak_refs' ] == 100.0


def test_build_report_context_concentration_percentages():
    inventory = _sample_inventory()
    model = inventory.as_report_model()
    env = { 'cxx_profiles_enforce': [ 'std::init' ] }
    context = build_report_context( model, env, context_mode='rules-only' )
    top_rules = context[ 'concentration' ][ 'top_rules' ]
    assert top_rules
    assert top_rules[ 0 ][ 'unique_lines' ] == 1
    assert top_rules[ 0 ][ 'pct_of_session_lines' ] == 100.0
    assert top_rules[ 0 ][ 'pct_of_session_refs' ] == 100.0
    assert top_rules[ 0 ][ 'pct_of_session_files' ] == 100.0
    assert top_rules[ 0 ][ 'rule_label' ] == 'std::init::ref_to_uninit'
    assert top_rules[ 0 ][ 'doc_href' ]
    matrix_rule = context[ 'profiles' ][ 0 ][ 'rules' ][ 0 ]
    assert matrix_rule[ 'pct_of_session_files' ] == 100.0
    assert matrix_rule[ 'pct_of_session_lines' ] == 100.0


def test_build_scope_breakdown_groups_variant_across_sconscripts():
    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic( _LINE )
    orders_scope = ProfilesScope(
        sconscript='./orders/sconscript',
        variant_dir='_build/orders/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    trades_scope = ProfilesScope(
        sconscript='./trades/sconscript',
        variant_dir='_build/trades/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    inventory.record( orders_scope, diagnostic )
    inventory.record( trades_scope, diagnostic )
    model = inventory.as_report_model()
    context = build_report_context(
        model,
        { 'cxx_profiles_enforce': [ 'std::init' ] },
        context_mode='rules-only',
    )
    builds = context[ 'builds' ]
    assert len( builds[ 'rows' ] ) == 1
    row = builds[ 'rows' ][ 0 ]
    assert row[ 'variant_label' ] == 'dbg'
    assert row[ 'variant_display_tail' ] == 'x86_64/cxx2c'
    assert row[ 'violations' ] == 2
    assert row[ 'references' ] == 2
    assert row[ 'build_id' ] == 'dbg1'
    assert row[ 'files' ] == 2
    assert 'sconscript' not in row


def test_build_scope_breakdown_aggregate_sums_rows():
    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic( _LINE )
    dbg_scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    rel_scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/rel/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='rel',
    )
    inventory.record( dbg_scope, diagnostic )
    inventory.record( rel_scope, diagnostic )
    model = inventory.as_report_model()
    context = build_report_context(
        model,
        { 'cxx_profiles_enforce': [ 'std::init' ] },
        context_mode='rules-only',
    )
    builds = context[ 'builds' ]
    assert len( builds[ 'rows' ] ) == 2
    assert builds[ 'rows' ][ 0 ][ 'build_id' ] == 'dbg1'
    assert builds[ 'rows' ][ 1 ][ 'build_id' ] == 'rel1'
    assert builds[ 'aggregate' ][ 'violations' ] == sum(
        row[ 'violations' ] for row in builds[ 'rows' ]
    )
    assert builds[ 'aggregate' ][ 'references' ] == builds[ 'session' ][ 'raw_references' ]
    assert builds[ 'session' ][ 'files' ] == 1


def test_build_report_context_tier_metrics_with_parsed_files( tmp_path ):
    source = tmp_path / 'widget.cpp'
    source.write_text( 'int Value;\n' * 10 + '\n', encoding='utf-8' )
    inventory = ProfilesInventory()
    line = (
        "{}:10:12: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'".format( source )
    )
    inventory.record( _SAMPLE_SCOPE, parse_profiles_diagnostic( line ) )
    model = inventory.as_report_model()
    parsed_files = frozenset( [ str( source ), str( tmp_path / 'extra.hpp' ) ] )
    env = { 'cxx_profiles_enforce': [ 'std::init' ] }
    context = build_report_context(
        model,
        env,
        parsed_files=parsed_files,
        translation_units=frozenset( [ str( source ) ] ),
        context_mode='full',
    )
    codebase = context[ 'codebase' ]
    assert codebase[ 'files_parsed' ] == 2
    assert codebase[ 'files_with_violations' ] == 1
    assert codebase[ 'files_with_violations_pct' ] == 50.0
    assert codebase[ 'translation_units_compiled' ] == 1
    assert codebase[ 'source_lines_in_violating_files' ] == 10
    assert codebase[ 'violation_line_pct_in_affected_files' ] == 10.0


def test_build_report_context_off_returns_none():
    model = _sample_inventory().as_report_model()
    assert build_report_context( model, {}, context_mode='off' ) is None
