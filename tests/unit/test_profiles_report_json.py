#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json

import pytest

from cuppa.cpp.cxx_profiles_report import ProfilesInventory, ProfilesScope, parse_profiles_diagnostic
from cuppa.cpp.profiles_report.report_json import (
    REPORT_JSON_SCHEMA_VERSION,
    inventory_from_report_model,
    load_report_model,
    unwrap_report_payload,
    wrap_report_payload,
)

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


def _sample_model():
    inventory = ProfilesInventory()
    inventory.record( _SAMPLE_SCOPE, parse_profiles_diagnostic( _LINE ) )
    return inventory.as_report_model()


def test_wrap_report_payload_includes_schema_and_metadata( tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path / 'project' ),
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path / 'project' ),
    }
    ( tmp_path / 'project' ).mkdir()
    model = _sample_model()
    payload = wrap_report_payload( model, env )
    assert payload[ 'schema_version' ] == REPORT_JSON_SCHEMA_VERSION
    assert payload[ 'generated_at' ]
    assert payload[ 'metadata' ][ 'sconstruct_dir' ] == str( ( tmp_path / 'project' ).resolve() )
    assert payload[ 'metadata' ][ 'report_project' ] == 'project'
    assert payload[ 'report' ][ 'rollup' ][ 'total_references' ] == 1


def test_unwrap_report_payload_reads_versioned_document():
    model = _sample_model()
    payload = {
        'schema_version': REPORT_JSON_SCHEMA_VERSION,
        'metadata': { 'sconstruct_dir': '/tmp/project' },
        'report': model,
    }
    unwrapped, metadata = unwrap_report_payload( payload )
    assert unwrapped[ 'rollup' ][ 'total_references' ] == 1
    assert metadata[ 'sconstruct_dir' ] == '/tmp/project'


def test_unwrap_report_payload_reads_legacy_document():
    model = _sample_model()
    unwrapped, metadata = unwrap_report_payload( model )
    assert unwrapped[ 'rollup' ][ 'total_references' ] == 1
    assert metadata == {}


def test_inventory_from_report_model_round_trips_counts():
    model = _sample_model()
    rebuilt = inventory_from_report_model( model )
    assert rebuilt.total_references() == 1
    assert rebuilt.unique_violation_count() == 1
    assert rebuilt.as_report_model()[ 'rollup' ][ 'total_references' ] == 1


def test_load_report_model_from_file( tmp_path ):
    model = _sample_model()
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report_link_style': 'gitlab',
    }
    json_path = tmp_path / 'cxx-profiles-index.json'
    with open( json_path, 'w', encoding='utf-8' ) as handle:
        json.dump( wrap_report_payload( model, env ), handle )

    loaded_model, metadata = load_report_model( str( json_path ) )
    assert loaded_model[ 'rollup' ][ 'total_references' ] == 1
    assert metadata[ 'link_style' ] == 'gitlab'
