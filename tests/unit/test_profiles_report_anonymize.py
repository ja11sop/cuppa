#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json

import pytest

from cuppa.cpp.cxx_profiles_report import ProfilesInventory, ProfilesScope, parse_profiles_diagnostic
from cuppa.cpp.profiles_report.anonymize import (
    ANON_PLACEHOLDER_ROOT,
    anonymize_report_payload,
    anonymize_stem,
    forbidden_identity_patterns,
    load_synonym_dictionary,
)
from cuppa.cpp.profiles_report.report_json import wrap_report_payload

pytestmark = pytest.mark.unit


def _sample_payload( tmp_path ):
    project = tmp_path / 'acme_matcher'
    project.mkdir()
    source = project / 'include' / 'matcher' / 'common_types' / 'number.hpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int x;\n', encoding='utf-8' )
    download = (
        project
        / '_cuppa'
        / '_download'
        / 'git_example_com_acme_matcher'
        / 'include'
        / 'matcher'
        / 'common_types'
        / 'number.hpp'
    )
    download.parent.mkdir( parents=True, exist_ok=True )
    download.write_text( 'int y;\n', encoding='utf-8' )

    scope = ProfilesScope(
        sconscript='./matcher/sconscript',
        variant_dir='_build/matcher/clang24/dbg/x86_64/cxx2c',
        toolchain='clang24',
        variant_label='dbg',
    )
    line = (
        "{path}:3:4: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'"
    ).format( path=source )
    inventory = ProfilesInventory()
    inventory.record( scope, parse_profiles_diagnostic( line ) )
    inventory.record(
        scope,
        parse_profiles_diagnostic( line.format( path=download ) ),
    )

    env = {
        'sconstruct_dir': str( project ),
        'cxx_profiles_report_root': str( project ),
        'cxx_profiles_report_link_style': 'gitlab',
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    return wrap_report_payload(
        inventory.as_report_model(),
        env,
        inventory=inventory,
    ), {
        'project': str( project ),
        'source': str( source ),
        'download': str( download ),
    }


def test_anonymize_stem_replaces_multi_part_names():
    dictionary = load_synonym_dictionary()
    assert anonymize_stem( 'common_types', dictionary ) == 'core_elements'
    assert 'common' not in anonymize_stem( 'order_manager', dictionary ).split( '_' )


def test_anonymize_report_payload_scrubs_identity_and_paths( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    original_metadata = dict( payload[ 'metadata' ] )
    original_summary = dict( payload[ 'summary' ] )
    original_context = json.loads( json.dumps( payload[ 'context' ] ) )

    anonymized = anonymize_report_payload( payload )
    serialized = json.dumps( anonymized )

    assert anonymized[ 'metadata' ][ 'anonymized' ] is True
    assert anonymized[ 'metadata' ][ 'anonymization_version' ] == 1
    assert anonymized[ 'metadata' ][ 'sconstruct_dir' ] == ANON_PLACEHOLDER_ROOT
    assert anonymized[ 'metadata' ][ 'report_uri' ] == ''
    assert anonymized[ 'metadata' ][ 'link_style' ] == 'local'

    for pattern in forbidden_identity_patterns( original_metadata ):
        assert pattern not in serialized

    assert 'common_types' not in serialized
    assert 'gitlab' not in serialized
    assert originals[ 'project' ] not in serialized

    assert anonymized[ 'summary' ] == original_summary
    assert anonymized[ 'context' ] == original_context

    location = anonymized[ 'locations' ][ 0 ]
    assert 'message' not in location
    assert location[ 'location_key' ]
    assert location[ 'variant_dir' ].endswith( 'dbg/x86_64/cxx2c' )
    assert location[ 'sconscript' ] != './matcher/sconscript'
    assert location[ 'sconscript' ].endswith( '/sconscript' )


def test_path_anonymizer_rewrites_download_tree( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    from cuppa.cpp.profiles_report.anonymize import PathAnonymizer

    anonymizer = PathAnonymizer( payload[ 'metadata' ] )
    rewritten = anonymizer.anonymize_path( originals[ 'download' ] )
    assert rewritten.startswith( '_cuppa/_download/vendor/' )
    assert originals[ 'download' ] not in rewritten


def test_anonymize_is_deterministic( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    first = anonymize_report_payload( payload )
    second = anonymize_report_payload( payload )
    assert first == second


def test_anonymize_requires_force_when_already_anonymized( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    anonymized = anonymize_report_payload( payload )
    with pytest.raises( ValueError, match='metadata.anonymized' ):
        anonymize_report_payload( anonymized )
    again = anonymize_report_payload( anonymized, force=True )
    assert again[ 'metadata' ][ 'anonymized' ] is True


def test_anonymized_json_regen_omits_source_pages_and_file_hrefs( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    anonymized = anonymize_report_payload( payload )

    json_path = tmp_path / 'anonymized.json'
    json_path.write_text( json.dumps( anonymized ), encoding='utf-8' )

    from scripts import regenerate_profiles_report

    argv = [
        str( json_path ),
        '--from-json',
        '--anonymized',
    ]
    assert regenerate_profiles_report.main( argv ) == 0
    assert ( tmp_path / 'cxx-profiles-index.html' ).is_file()
    assert not ( tmp_path / 'by-source' ).exists()

    html = ( tmp_path / 'cxx-profiles-index.html' ).read_text( encoding='utf-8' )
    assert 'file://' not in html
    assert 'by-source/' not in html


def test_anonymized_json_regen_defaults_output_next_to_json( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    anonymized = anonymize_report_payload( payload )

    json_dir = tmp_path / 'shared'
    json_dir.mkdir()
    json_path = json_dir / 'index.anonymized.json'
    json_path.write_text( json.dumps( anonymized ), encoding='utf-8' )

    from scripts import regenerate_profiles_report

    argv = [
        str( json_path ),
        '--from-json',
    ]
    assert regenerate_profiles_report.main( argv ) == 0
    assert ( json_dir / 'cxx-profiles-index.html' ).is_file()


def test_anonymize_profiles_report_cli( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    input_path = tmp_path / 'index.json'
    output_path = tmp_path / 'index.anonymized.json'
    mapping_path = tmp_path / 'mapping.local.json'
    input_path.write_text( json.dumps( payload ), encoding='utf-8' )

    from scripts import anonymize_profiles_report

    argv = [
        '--in',
        str( input_path ),
        '--out',
        str( output_path ),
        '--mapping-out',
        str( mapping_path ),
    ]
    assert anonymize_profiles_report.main( argv ) == 0
    assert output_path.is_file()
    assert mapping_path.is_file()
    data = json.loads( output_path.read_text( encoding='utf-8' ) )
    assert data[ 'metadata' ][ 'anonymized' ] is True
