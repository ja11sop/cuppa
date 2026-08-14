#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json

import pytest

from cuppa.cpp.cxx_profiles_report import ProfilesInventory, ProfilesScope, parse_profiles_diagnostic
from cuppa.cpp.profiles_report.report_json import (
    REPORT_JSON_SCHEMA_VERSION,
    build_flat_locations,
    env_from_report_metadata,
    inventory_from_flat_locations,
    inventory_from_report_model,
    load_report_model,
    location_key_from_dedupe,
    location_key_from_location,
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


def _sample_inventory():
    inventory = ProfilesInventory()
    inventory.record( _SAMPLE_SCOPE, parse_profiles_diagnostic( _LINE ) )
    return inventory


def _sample_model():
    return _sample_inventory().as_report_model()


def test_wrap_report_payload_includes_schema_summary_and_locations( tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path / 'project' ),
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path / 'project' ),
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    ( tmp_path / 'project' ).mkdir()
    inventory = _sample_inventory()
    model = inventory.as_report_model()
    payload = wrap_report_payload(
        model,
        env,
        inventory=inventory,
        incomplete_scopes=[ 'missing/sconscript' ],
    )
    assert payload[ 'schema_version' ] == REPORT_JSON_SCHEMA_VERSION
    assert payload[ 'generated_at' ]
    assert payload[ 'metadata' ][ 'sconstruct_dir' ] == str( ( tmp_path / 'project' ).resolve() )
    assert payload[ 'metadata' ][ 'report_project' ] == 'project'
    assert payload[ 'metadata' ][ 'profiles_enforce' ] == [ 'std::init' ]
    assert payload[ 'metadata' ][ 'variant_labels' ] == [ 'dbg' ]
    assert payload[ 'metadata' ][ 'incomplete_scopes' ] == [ 'missing/sconscript' ]
    assert payload[ 'metadata' ][ 'partial' ] is True
    assert payload[ 'summary' ][ 'total_references' ] == 1
    assert payload[ 'summary' ][ 'by_rule' ]
    assert len( payload[ 'locations' ] ) == 1
    assert payload[ 'locations' ][ 0 ][ 'location_key' ]
    assert payload[ 'locations' ][ 0 ][ 'rule_id' ] == 'ref_to_uninit'
    assert payload[ 'report' ][ 'rollup' ][ 'total_references' ] == 1
    scope_rule = payload[ 'report' ][ 'scopes' ][ 0 ][ 'profiles' ][ 0 ][ 'rules' ][ 0 ]
    assert scope_rule[ 'doc_href' ]
    rollup_rule = payload[ 'report' ][ 'rollup' ][ 'rules' ][ 0 ]
    assert rollup_rule[ 'doc_href' ]
    scope_file_rule = payload[ 'report' ][ 'scopes' ][ 0 ][ 'profiles' ][ 0 ][ 'files' ][ 0 ][ 'rules' ][ 0 ]
    assert scope_file_rule[ 'doc_href' ]
    rollup_file_rule = payload[ 'report' ][ 'rollup' ][ 'files' ][ 0 ][ 'rules' ][ 0 ]
    assert rollup_file_rule[ 'doc_href' ]


def test_unwrap_report_payload_reads_versioned_document():
    model = _sample_model()
    payload = {
        'schema_version': REPORT_JSON_SCHEMA_VERSION,
        'metadata': { 'sconstruct_dir': '/tmp/project' },
        'summary': { 'total_references': 1 },
        'locations': [],
        'report': model,
    }
    unwrapped, metadata, extras = unwrap_report_payload( payload )
    assert unwrapped[ 'rollup' ][ 'total_references' ] == 1
    assert metadata[ 'sconstruct_dir' ] == '/tmp/project'
    assert extras[ 'summary' ][ 'total_references' ] == 1


def test_unwrap_report_payload_reads_legacy_document():
    model = _sample_model()
    unwrapped, metadata, extras = unwrap_report_payload( model )
    assert unwrapped[ 'rollup' ][ 'total_references' ] == 1
    assert metadata == {}
    assert extras[ 'locations' ] == []


def test_unwrap_report_payload_reads_minimal_envelope():
    """Older envelopes may omit summary and locations; loaders tolerate that."""
    model = _sample_model()
    payload = {
        'schema_version': 1,
        'metadata': { 'sconstruct_dir': '/tmp/project' },
        'report': model,
    }
    unwrapped, metadata, extras = unwrap_report_payload( payload )
    assert unwrapped[ 'rollup' ][ 'total_references' ] == 1
    assert metadata[ 'sconstruct_dir' ] == '/tmp/project'
    assert extras[ 'summary' ] == {}


def test_inventory_from_report_model_round_trips_counts():
    model = _sample_model()
    rebuilt = inventory_from_report_model( model )
    assert rebuilt.total_references() == 1
    assert rebuilt.unique_violation_count() == 1
    assert rebuilt.as_report_model()[ 'rollup' ][ 'total_references' ] == 1


def test_inventory_from_flat_locations_round_trips_counts():
    inventory = _sample_inventory()
    flat = build_flat_locations( inventory )
    rebuilt = inventory_from_flat_locations( flat )
    assert rebuilt.total_references() == 1
    assert rebuilt.unique_violation_count() == 1


def test_location_key_is_stable_for_same_diagnostic():
    inventory = _sample_inventory()
    location = inventory.locations()[ 0 ]
    diagnostic = parse_profiles_diagnostic( _LINE )
    assert location_key_from_location( location ) == location_key_from_dedupe(
        _SAMPLE_SCOPE,
        diagnostic,
    )


def test_env_from_report_metadata_prefers_saved_sconstruct_dir():
    metadata = {
        'sconstruct_dir': '/saved/project',
        'link_style': 'gitlab',
        'cxx_profiles_report_root': '/saved/project',
        'profiles_enforce': [ 'std::init' ],
    }
    arguments = type(
        'Arguments',
        (),
        {
            'sconstruct_dir': None,
            'artifacts_root': '_artifacts',
            'report_dir': '',
            'reports_link_style': 'gitlab',
            'link_style': None,
            'cxx_profiles_report_link_style': None,
        },
    )()
    env = env_from_report_metadata( metadata, arguments )
    assert env[ 'sconstruct_dir' ] == '/saved/project'
    assert env[ 'reports_link_style' ] == 'gitlab'
    assert env[ 'cxx_profiles_enforce' ] == [ 'std::init' ]


def test_load_report_model_from_file( tmp_path ):
    model = _sample_model()
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report_link_style': 'gitlab',
    }
    json_path = tmp_path / 'cxx-profiles-index.json'
    with open( json_path, 'w', encoding='utf-8' ) as handle:
        json.dump( wrap_report_payload( model, env, inventory=_sample_inventory() ), handle )

    loaded_model, metadata, extras = load_report_model( str( json_path ) )
    assert loaded_model[ 'rollup' ][ 'total_references' ] == 1
    assert metadata[ 'link_style' ] == 'gitlab'
    assert len( extras[ 'locations' ] ) == 1
