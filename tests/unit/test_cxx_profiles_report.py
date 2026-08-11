#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from pathlib import Path

from cuppa.cpp.cxx_profiles_report import (
    ProfilesInventory,
    ProfilesScope,
    UNCLASSIFIED_RULE_ID,
    classify_rule,
    format_capture_summary,
    location_dedupe_key,
    normalise_message,
    parse_progress_line,
    parse_profiles_diagnostic,
    parse_variant_scope_fields,
    replay_profiles_capture,
    unscoped_profiles_scope,
)

pytestmark = pytest.mark.unit

_FIXTURE_CAPTURE = (
    Path( __file__ ).resolve().parents[ 1 ]
    / 'fixtures'
    / 'profiles_capture'
    / 'sample_capture.txt'
)


_SAMPLE_SCOPE = ProfilesScope(
    sconscript='./widget/sconscript',
    variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    toolchain='clang24_profiles',
    variant_label='dbg',
)

_UNINIT_LINE = (
    "/home/user/_cuppa/_download/example.org/common_types/include/widget/nonce.hpp"
    ":35:39: error: variable 'RandomValues' must be initialized or marked "
    "'[[uninit]]' under profile 'std::init'"
)

_STATIC_INIT_LINE = (
    "/home/user/_cuppa/_download/example.org/common_types/include/widget/number.hpp"
    ":79:25: error: non-local variable 'decimal_places_1' requires constant "
    "initialization under profile 'std::init'"
)

_CTOR_MEMBER_LINE = (
    "/home/user/project/include/widget/table.hpp"
    ":120:5: error: constructor does not initialize member 'Buffer_' "
    "under profile 'std::init'"
)

_CTOR_BASE_LINE = (
    "/home/user/project/include/widget/string.hpp"
    ":44:5: error: constructor does not initialize base class "
    "'std::array<char, 11>' under profile 'std::init'"
)

_REF_LINE = (
    "/home/user/project/src/widget.cpp"
    ":10:12: error: pointer to uninitialized memory must be marked "
    "'[[ref_to_uninit]]' under profile 'std::init'"
)

_UNKNOWN_LINE = (
    "/home/user/project/src/widget.cpp"
    ":99:1: error: something unexpected happened under profile 'std::init'"
)


def test_normalise_message_collapses_quoted_identifiers():
    message = (
        "constructor does not initialize member 'AssetMetrics_'"
    )
    assert normalise_message( message ) == (
        "constructor does not initialize member '…'"
    )


@pytest.mark.parametrize(
    'message, rule_id',
    [
        (
            "variable '…' must be initialized or marked '…'",
            'uninit_decl',
        ),
        (
            "non-local variable '…' requires constant initialization",
            'static_runtime_init',
        ),
        (
            "constructor does not initialize member '…'",
            'ctor_uninit_member',
        ),
        (
            "constructor does not initialize base class '…'",
            'ctor_uninit_member',
        ),
        (
            "pointer to uninitialized memory must be marked '…'",
            'ref_to_uninit',
        ),
        (
            "something unexpected happened",
            UNCLASSIFIED_RULE_ID,
        ),
    ],
)
def test_classify_rule( message, rule_id ):
    assert classify_rule( message ) == rule_id


def test_parse_profiles_diagnostic_extracts_fields():
    diagnostic = parse_profiles_diagnostic( _UNINIT_LINE )
    assert diagnostic is not None
    assert diagnostic.line == 35
    assert diagnostic.column == 39
    assert diagnostic.profile == 'std::init'
    assert diagnostic.rule_id == 'uninit_decl'
    assert diagnostic.normalised_message == (
        "variable '…' must be initialized or marked '…'"
    )


def test_parse_profiles_diagnostic_ignores_non_profiles_lines():
    assert parse_profiles_diagnostic( "note: unrelated compiler output" ) is None
    assert parse_profiles_diagnostic(
        "/tmp/foo.cpp:1:1: error: plain error without profile suffix"
    ) is None


def test_location_dedupe_key_includes_scope():
    first = parse_profiles_diagnostic( _STATIC_INIT_LINE )
    second_scope = _SAMPLE_SCOPE._replace( variant_dir='_build/widget/rel/x86_64/cxx2c' )
    assert location_dedupe_key( _SAMPLE_SCOPE, first ) != location_dedupe_key(
        second_scope,
        first,
    )


def test_inventory_dedupes_within_scope():
    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic( _STATIC_INIT_LINE )
    inventory.record( _SAMPLE_SCOPE, diagnostic )
    inventory.record( _SAMPLE_SCOPE, diagnostic )

    assert inventory.total_references() == 2
    assert inventory.unique_locations() == 1
    location = inventory.locations()[ 0 ]
    assert location.reference_count == 2


def test_inventory_keeps_same_file_in_two_scopes_separate():
    inventory = ProfilesInventory()
    diagnostic = parse_profiles_diagnostic( _STATIC_INIT_LINE )
    rel_scope = _SAMPLE_SCOPE._replace(
        variant_dir='_build/widget/rel/x86_64/cxx2c',
        variant_label='rel',
    )
    inventory.record( _SAMPLE_SCOPE, diagnostic )
    inventory.record( rel_scope, diagnostic )

    assert inventory.total_references() == 2
    assert inventory.unique_locations() == 2


def test_inventory_report_model_shape():
    inventory = ProfilesInventory()
    for line in (
        _UNINIT_LINE,
        _STATIC_INIT_LINE,
        _CTOR_MEMBER_LINE,
        _CTOR_BASE_LINE,
        _REF_LINE,
        _UNKNOWN_LINE,
    ):
        inventory.record( _SAMPLE_SCOPE, parse_profiles_diagnostic( line ) )

    model = inventory.as_report_model()
    assert model[ 'rollup' ][ 'total_references' ] == 6
    assert model[ 'rollup' ][ 'unique_locations' ] == 6
    assert len( model[ 'scopes' ] ) == 1
    scope = model[ 'scopes' ][ 0 ]
    assert scope[ 'sconscript' ] == _SAMPLE_SCOPE.sconscript
    profile = scope[ 'profiles' ][ 0 ]
    assert profile[ 'profile' ] == 'std::init'
    rule_ids = { rule[ 'rule_id' ] for rule in profile[ 'rules' ] }
    assert rule_ids == {
        'uninit_decl',
        'static_runtime_init',
        'ctor_uninit_member',
        'ref_to_uninit',
        UNCLASSIFIED_RULE_ID,
    }


def test_unscoped_profiles_scope_is_stable():
    assert unscoped_profiles_scope().sconscript == '_unscoped'


def test_parse_variant_scope_fields():
    assert parse_variant_scope_fields(
        '_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    ) == ( 'clang24_profiles', 'dbg' )
    assert parse_variant_scope_fields(
        '_build/test/matching_engine/clang24_profiles_2026_08_07_27/dbg/x86_64/cxx2c',
    ) == ( 'clang24_profiles_2026_08_07_27', 'dbg' )


@pytest.mark.parametrize(
    'line, expected',
    [
        (
            'Progress( SconstructBegin )',
            ( 'sconstruct_begin', None, None ),
        ),
        (
            'Progress( Begin sconscript: [./widget/sconscript] )',
            ( 'begin', './widget/sconscript', None ),
        ),
        (
            'Progress( Starting variant: [_build/widget/clang24_profiles/dbg/x86_64/cxx2c] )',
            ( 'started', None, '_build/widget/clang24_profiles/dbg/x86_64/cxx2c' ),
        ),
        (
            'Progress( Finished variant: [_build/widget/clang24_profiles/dbg/x86_64/cxx2c] )',
            ( 'finished', None, '_build/widget/clang24_profiles/dbg/x86_64/cxx2c' ),
        ),
    ],
)
def test_parse_progress_line( line, expected ):
    assert parse_progress_line( line ) == expected


def test_replay_profiles_capture_builds_scope_from_progress_markers():
    inventory, unscoped = replay_profiles_capture( _FIXTURE_CAPTURE.read_text().splitlines() )
    assert unscoped == 0
    assert inventory.total_references() == 3
    assert inventory.unique_locations() == 3
    scope = inventory.locations()[ 0 ].scope
    assert scope.sconscript == './widget/sconscript'
    assert scope.variant_dir == '_build/widget/clang24_profiles/dbg/x86_64/cxx2c'
    assert scope.toolchain == 'clang24_profiles'
    assert scope.variant_label == 'dbg'


def test_replay_profiles_capture_records_unscoped_without_progress():
    inventory, unscoped = replay_profiles_capture( [ _UNINIT_LINE ] )
    assert unscoped == 1
    assert inventory.locations()[ 0 ].scope.sconscript == '_unscoped'


def test_format_capture_summary_lists_rules():
    inventory, _unscoped = replay_profiles_capture( _FIXTURE_CAPTURE.read_text().splitlines() )
    summary = format_capture_summary( inventory )
    assert 'total_references: 3' in summary
    assert 'static_runtime_init' in summary
    assert './widget/sconscript' in summary
