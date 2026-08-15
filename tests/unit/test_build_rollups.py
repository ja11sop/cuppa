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
from cuppa.cpp.profiles_report.build_rollups import build_views_from_model
from cuppa.cpp.profiles_report.report_html import enrich_model_for_html

pytestmark = pytest.mark.unit

_LINE = (
    "/home/user/project/src/widget.cpp:10:12: error: pointer to uninitialized "
    "memory must be marked '[[ref_to_uninit]]' under profile 'std::init'"
)


def _enriched_model( inventory ):
    model = inventory.as_report_model()
    enrich_model_for_html(
        model,
        {},
        'raw',
        '',
        '/tmp/project',
        '/tmp/project',
    )
    return model


def test_build_views_single_build():
    inventory = ProfilesInventory()
    inventory.record(
        ProfilesScope(
            sconscript='./widget/sconscript',
            variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
            toolchain='clang24_profiles',
            variant_label='dbg',
        ),
        parse_profiles_diagnostic( _LINE ),
    )
    model = _enriched_model( inventory )
    build_views = model[ 'build_views' ]
    assert len( build_views ) == 1
    build = build_views[ 0 ]
    assert build[ 'build_id' ] == 'dbg1'
    assert build[ 'variant_label' ] == 'dbg'
    assert build[ 'variant_display_tail' ] == 'x86_64/cxx2c'
    assert build[ 'toolchain' ] == 'clang24_profiles'
    assert len( build[ 'profiles' ] ) == 1
    assert len( build[ 'rules' ] ) == 1
    assert len( build[ 'files' ] ) == 1
    profile = build[ 'profiles' ][ 0 ]
    assert profile[ 'profile' ] == 'std::init'
    assert len( profile[ 'rules' ] ) == 1
    assert profile[ 'rules' ][ 0 ][ 'rule_id' ] == 'ref_to_uninit'
    assert profile[ 'rules' ][ 0 ][ 'variant_counts' ][ 0 ][ 'variant_label' ] == 'dbg'
    assert 'variant_display' not in profile[ 'rules' ][ 0 ]
    assert len( profile[ 'files' ] ) == 1


def test_build_views_filter_multi_build_rollup():
    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic( _LINE )
    inventory.record(
        ProfilesScope(
            sconscript='./widget/sconscript',
            variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
            toolchain='clang24_profiles',
            variant_label='dbg',
        ),
        diagnostic,
    )
    inventory.record(
        ProfilesScope(
            sconscript='./widget/sconscript',
            variant_dir='_build/widget/clang24_profiles/rel/x86_64/cxx2c',
            toolchain='clang24_profiles',
            variant_label='rel',
        ),
        diagnostic,
    )
    model = _enriched_model( inventory )
    build_views = build_views_from_model( model )
    assert len( build_views ) == 2
    assert [ item[ 'build_id' ] for item in build_views ] == [ 'dbg1', 'rel1' ]
    dbg_rule = build_views[ 0 ][ 'profiles' ][ 0 ][ 'rules' ][ 0 ]
    rel_rule = build_views[ 1 ][ 'profiles' ][ 0 ][ 'rules' ][ 0 ]
    assert dbg_rule[ 'variant_counts' ][ 0 ][ 'variant_label' ] == 'dbg'
    assert rel_rule[ 'variant_counts' ][ 0 ][ 'variant_label' ] == 'rel'
    assert dbg_rule[ 'unique_line_count' ] == 1
    assert rel_rule[ 'unique_line_count' ] == 1


def test_scope_detail_tables_merges_profiles():
    from cuppa.cpp.profiles_report.build_rollups import scope_detail_tables

    scope = {
        'profiles': [
            {
                'profile': 'std::init',
                'rules': [
                    {
                        'rule_id': 'uninit_decl',
                        'unique_line_count': 1,
                        'total_references': 1,
                    },
                ],
                'files': [
                    {
                        'profile': 'std::init',
                        'path': 'a.cpp',
                        'unique_line_count': 1,
                        'total_references': 1,
                    },
                ],
            },
            {
                'profile': 'std::future',
                'rules': [
                    {
                        'rule_id': 'other_rule',
                        'unique_line_count': 2,
                        'total_references': 2,
                    },
                ],
                'files': [
                    {
                        'profile': 'std::future',
                        'path': 'b.cpp',
                        'unique_line_count': 2,
                        'total_references': 2,
                    },
                ],
            },
        ],
    }
    rules, files = scope_detail_tables( scope )
    assert len( rules ) == 2
    assert { rule[ 'profile' ] for rule in rules } == { 'std::init', 'std::future' }
    assert len( files ) == 2


def test_build_views_aggregate_across_sconscripts():
    inventory = ProfilesInventory()
    inventory.record(
        ProfilesScope(
            sconscript='./alpha/sconscript',
            variant_dir='_build/alpha/clang24_profiles/dbg/x86_64/cxx2c',
            toolchain='clang24_profiles',
            variant_label='dbg',
        ),
        parse_profiles_diagnostic( _LINE ),
    )
    inventory.record(
        ProfilesScope(
            sconscript='./beta/sconscript',
            variant_dir='_build/beta/clang24_profiles/dbg/x86_64/cxx2c',
            toolchain='clang24_profiles',
            variant_label='dbg',
        ),
        parse_profiles_diagnostic(
            "/home/user/project/src/other.cpp:3:4: error: uninitialized memory "
            "accessed under profile 'std::init'"
        ),
    )
    model = _enriched_model( inventory )
    build = model[ 'build_views' ][ 0 ]
    profile = build[ 'profiles' ][ 0 ]
    assert len( profile[ 'rules' ] ) >= 1
    assert len( profile[ 'files' ] ) == 2
