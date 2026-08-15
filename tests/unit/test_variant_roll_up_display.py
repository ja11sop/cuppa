#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.profiles_report.variant_roll_up_display import (
    compute_file_build_refs_display,
    compute_rule_build_refs_display,
    compute_violation_metric_display,
)


def _catalog_entry( build_id, variant_label, toolchain ):
    return {
        'build_key': [ variant_label, 'x86_64/cxx2c', toolchain ],
        'build_id': build_id,
        'build_label': '{}/x86_64/cxx2c — {}'.format( variant_label, toolchain ),
    }


@pytest.mark.unit
def test_build_refs_totals_sum_per_build_lines():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    rule = {
        'variant_counts': [
            {
                'build_key': catalog[ 0 ][ 'build_key' ],
                'files': [ { 'file_index': 1, 'total_references': 1436 } ],
            },
            {
                'build_key': catalog[ 1 ][ 'build_key' ],
                'files': [ { 'file_index': 1, 'total_references': 1727 } ],
            },
        ],
    }
    display = compute_file_build_refs_display(
        { 'file_index': 1 },
        rule,
        catalog,
    )
    assert display[ 'common' ][ 'refs' ] == 0
    assert display[ 'totals' ][ 'refs' ] == 3163
    assert len( display[ 'deltas' ] ) == 2


@pytest.mark.unit
def test_build_refs_single_build_delta_is_explicit():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    rule = {
        'variant_counts': [
            {
                'build_key': catalog[ 0 ][ 'build_key' ],
                'files': [ { 'file_index': 1, 'total_references': 1436 } ],
            },
            {
                'build_key': catalog[ 1 ][ 'build_key' ],
                'files': [],
            },
        ],
    }
    display = compute_file_build_refs_display(
        { 'file_index': 1 },
        rule,
        catalog,
    )
    assert display[ 'totals' ][ 'refs' ] == 1436
    assert len( display[ 'deltas' ] ) == 1
    assert display[ 'deltas' ][ 0 ][ 'refs' ] == 1436
    assert display[ 'deltas' ][ 0 ][ 'build_id' ] == 'dbg1'


@pytest.mark.unit
def test_file_build_refs_matches_violating_files_partition():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    rule = {
        'variant_counts': [
            {
                'build_key': catalog[ 0 ][ 'build_key' ],
                'files': [
                    { 'file_index': 21, 'total_references': 1 },
                    { 'file_index': 1, 'total_references': 1436 },
                ],
            },
            {
                'build_key': catalog[ 1 ][ 'build_key' ],
                'files': [
                    { 'file_index': 21, 'total_references': 1 },
                    { 'file_index': 1, 'total_references': 1727 },
                ],
            },
        ],
    }
    file_common = { 'file_index': 21 }
    file_delta = { 'file_index': 1 }

    common_display = compute_file_build_refs_display( file_common, rule, catalog )
    assert common_display[ 'common' ][ 'refs' ] == 1
    assert common_display[ 'deltas' ] == []

    delta_display = compute_file_build_refs_display( file_delta, rule, catalog )
    assert delta_display[ 'common' ][ 'refs' ] == 0
    assert [ item[ 'build_id' ] for item in delta_display[ 'deltas' ] ] == [ 'dbg1', 'rel1' ]
    assert delta_display[ 'deltas' ][ 0 ][ 'refs' ] == 1436
    assert delta_display[ 'deltas' ][ 1 ][ 'refs' ] == 1727


@pytest.mark.unit
def test_rule_build_refs_matches_violated_rules_partition():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    file_entry = {
        'rule_variant_counts': [
            {
                'build_key': catalog[ 0 ][ 'build_key' ],
                'rules': [
                    { 'rule_index': 3, 'total_references': 9 },
                ],
            },
            {
                'build_key': catalog[ 1 ][ 'build_key' ],
                'rules': [
                    { 'rule_index': 3, 'total_references': 9 },
                ],
            },
        ],
    }
    rule = { 'rule_index': 3 }
    display = compute_rule_build_refs_display( file_entry, rule, catalog )
    assert display[ 'common' ][ 'refs' ] == 9
    assert display[ 'deltas' ] == []


@pytest.mark.unit
def test_file_build_refs_differs_from_key_based_refs_display():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    shared_key = [
        './widget/sconscript',
        'runtime_table.cpp',
        10,
        1,
        'std::init',
        'static_runtime_init',
    ]
    dbg_only_key = [
        './widget/sconscript',
        'runtime_table.cpp',
        20,
        1,
        'std::init',
        'static_runtime_init',
    ]
    file_entry = {
        'file_index': 1,
        'variant_counts': [
            {
                'build_key': catalog[ 0 ][ 'build_key' ],
                'violation_identity_keys': [ shared_key, dbg_only_key ],
                'violation_refs': [
                    { 'key': shared_key, 'refs': 1312 },
                    { 'key': dbg_only_key, 'refs': 188 },
                ],
            },
            {
                'build_key': catalog[ 1 ][ 'build_key' ],
                'violation_identity_keys': [ shared_key ],
                'violation_refs': [
                    { 'key': shared_key, 'refs': 1500 },
                ],
            },
        ],
    }
    rule = {
        'variant_counts': [
            {
                'build_key': catalog[ 0 ][ 'build_key' ],
                'files': [ { 'file_index': 1, 'total_references': 1500 } ],
            },
            {
                'build_key': catalog[ 1 ][ 'build_key' ],
                'files': [ { 'file_index': 1, 'total_references': 1500 } ],
            },
        ],
    }
    key_display = compute_violation_metric_display(
        file_entry[ 'variant_counts' ],
        catalog,
    )
    build_refs = compute_file_build_refs_display( file_entry, rule, catalog )

    assert key_display[ 'common' ][ 'refs' ] == 1500
    assert key_display[ 'deltas' ][ 0 ][ 'refs' ] == 188
    assert build_refs[ 'common' ][ 'refs' ] == 1500
    assert build_refs[ 'deltas' ] == []


def _variant_counts( build_key, keys, refs, row_peaks=None ):
    return {
        'build_key': list( build_key ),
        'violation_identity_keys': [ list( key ) for key in keys ],
        'violation_refs': [
            {
                'key': list( key ),
                'refs': ref_count,
                'row_peak': ( row_peaks or {} ).get( key, ref_count ),
            }
            for key, ref_count in refs.items()
        ],
    }


@pytest.mark.unit
def test_variant_metric_omits_equals_line_without_deltas():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    shared = ( './widget/sconscript', 'shared.cpp', 1, 1, 'std::init', 'uninit_decl' )
    counts = [
        _variant_counts(
            catalog[ 0 ][ 'build_key' ],
            [ shared ],
            { shared: 3 },
        ),
        _variant_counts(
            catalog[ 1 ][ 'build_key' ],
            [ shared ],
            { shared: 3 },
        ),
    ]
    display = compute_violation_metric_display( counts, catalog )
    assert display[ 'totals' ][ 'violations' ] == 1
    assert display[ 'common' ][ 'violations' ] == 1
    assert display[ 'deltas' ] == []


@pytest.mark.unit
def test_partition_index_ref_items_preserves_rule_metadata():
    catalog = [
        {
            'build_id': 'dbg1',
            'build_label': 'dbg — clang24',
        },
        {
            'build_id': 'rel1',
            'build_label': 'rel — clang24',
        },
    ]
    per_build = {
        'dbg1': [
            {
                'index': 3,
                'refs': 9,
                'doc_href': 'https://example.com/rule',
                'rule_tooltip': 'tooltip',
            },
        ],
        'rel1': [
            {
                'index': 3,
                'refs': 9,
                'doc_href': 'https://example.com/rule',
                'rule_tooltip': 'tooltip',
            },
        ],
    }
    from cuppa.cpp.profiles_report.variant_roll_up_display import _partition_index_ref_items

    common_items, deltas = _partition_index_ref_items( catalog, per_build )
    assert len( common_items ) == 1
    assert common_items[ 0 ][ 'doc_href' ] == 'https://example.com/rule'
    assert deltas == []


@pytest.mark.unit
def test_strict_intersection_common_zero_with_build_deltas():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'gcc15_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'gcc15_profiles' ),
        _catalog_entry( 'dbg2', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel2', 'rel', 'clang24_profiles' ),
    ]
    dbg_keys = [
        (
            './widget/sconscript',
            'dbg{}.cpp'.format( index ),
            index,
            1,
            'std::init',
            'uninit_decl',
        )
        for index in range( 1, 8 )
    ]
    rel_keys = [
        (
            './widget/sconscript',
            'rel{}.cpp'.format( index ),
            index,
            1,
            'std::init',
            'uninit_decl',
        )
        for index in range( 1, 9 )
    ]
    rel2_keys = [
        (
            './widget/sconscript',
            'rel2-{}.cpp'.format( index ),
            index,
            1,
            'std::init',
            'uninit_decl',
        )
        for index in range( 1, 3 )
    ]
    counts = [
        _variant_counts(
            catalog[ 0 ][ 'build_key' ],
            dbg_keys,
            { key: 1 for key in dbg_keys },
        ),
        _variant_counts(
            catalog[ 1 ][ 'build_key' ],
            rel_keys,
            { key: 1 for key in rel_keys },
        ),
        _variant_counts( catalog[ 2 ][ 'build_key' ], [], {} ),
        _variant_counts(
            catalog[ 3 ][ 'build_key' ],
            rel2_keys,
            { key: 1 for key in rel2_keys },
        ),
    ]
    display = compute_violation_metric_display( counts, catalog )
    assert display[ 'multi_build' ] is True
    assert display[ 'common' ][ 'violations' ] == 0
    assert display[ 'common' ][ 'refs' ] == 0
    assert [ item[ 'build_id' ] for item in display[ 'deltas' ] ] == [
        'dbg1',
        'rel1',
        'rel2',
    ]
    assert display[ 'deltas' ][ 0 ][ 'violations' ] == 7
    assert display[ 'deltas' ][ 0 ][ 'refs' ] == 7
    assert display[ 'deltas' ][ 1 ][ 'violations' ] == 8
    assert display[ 'deltas' ][ 1 ][ 'refs' ] == 8
    assert display[ 'deltas' ][ 2 ][ 'violations' ] == 2
    assert display[ 'deltas' ][ 2 ][ 'refs' ] == 2


@pytest.mark.unit
def test_shared_violation_in_common_with_exclusive_delta():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    shared = ( './widget/sconscript', 'shared.cpp', 1, 1, 'std::init', 'uninit_decl' )
    dbg_only = ( './widget/sconscript', 'dbg.cpp', 2, 2, 'std::init', 'uninit_decl' )
    counts = [
        _variant_counts(
            catalog[ 0 ][ 'build_key' ],
            [ shared, dbg_only ],
            { shared: 3, dbg_only: 4 },
        ),
        _variant_counts(
            catalog[ 1 ][ 'build_key' ],
            [ shared ],
            { shared: 3 },
        ),
    ]
    display = compute_violation_metric_display( counts, catalog )
    assert display[ 'common' ][ 'violations' ] == 1
    assert display[ 'common' ][ 'refs' ] == 3
    assert display[ 'common' ][ 'peak_refs' ] == 3
    assert display[ 'totals' ][ 'violations' ] == 2
    assert display[ 'totals' ][ 'refs' ] == 7
    assert display[ 'totals' ][ 'peak_refs' ] == 7
    assert len( display[ 'deltas' ] ) == 1
    assert display[ 'deltas' ][ 0 ][ 'build_id' ] == 'dbg1'
    assert display[ 'deltas' ][ 0 ][ 'violations' ] == 1
    assert display[ 'deltas' ][ 0 ][ 'refs' ] == 4


@pytest.mark.unit
def test_union_refs_use_row_peak_not_build_sum():
    catalog = [
        _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ),
        _catalog_entry( 'rel1', 'rel', 'clang24_profiles' ),
    ]
    shared = ( './widget/sconscript', 'shared.cpp', 1, 1, 'std::init', 'static_runtime_init' )
    counts = [
        _variant_counts(
            catalog[ 0 ][ 'build_key' ],
            [ shared ],
            { shared: 5 },
            row_peaks={ shared: 3 },
        ),
        _variant_counts(
            catalog[ 1 ][ 'build_key' ],
            [ shared ],
            { shared: 4 },
            row_peaks={ shared: 4 },
        ),
    ]
    display = compute_violation_metric_display( counts, catalog )
    assert display[ 'common' ][ 'refs' ] == 4
    assert display[ 'common' ][ 'peak_refs' ] == 5
    assert display[ 'totals' ][ 'refs' ] == 4
    assert display[ 'totals' ][ 'peak_refs' ] == 5


@pytest.mark.unit
def test_single_build_session_returns_plain_flag():
    catalog = [ _catalog_entry( 'dbg1', 'dbg', 'clang24_profiles' ) ]
    key = ( './widget/sconscript', 'a.cpp', 1, 1, 'std::init', 'uninit_decl' )
    counts = [
        _variant_counts(
            catalog[ 0 ][ 'build_key' ],
            [ key ],
            { key: 1 },
        ),
    ]
    display = compute_violation_metric_display( counts, catalog )
    assert display == { 'multi_build': False }
