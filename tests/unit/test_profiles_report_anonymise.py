#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json

import pytest

from cuppa.cpp.cxx_profiles_report import ProfilesInventory, ProfilesScope, parse_profiles_diagnostic
from cuppa.cpp.profiles_report.anonymise import (
    ANON_PLACEHOLDER_ROOT,
    DEPS_ROOT,
    PROJECT_ROOT,
    anonymise_report_payload,
    collect_forbidden_tokens,
    load_thematic_names,
    verify_anonymised_output,
)
from cuppa.cpp.profiles_report.report_json import wrap_report_payload

pytestmark = pytest.mark.unit

_ENCODED_DEP_FOLDER = (
    'git_ssh_git@git.example.com__org_common_types@master'
)


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
        / _ENCODED_DEP_FOLDER
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
    download_line = (
        "{path}:5:6: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'"
    ).format( path=download )
    inventory = ProfilesInventory()
    inventory.record( scope, parse_profiles_diagnostic( line ) )
    inventory.record( scope, parse_profiles_diagnostic( download_line ) )

    env = {
        'sconstruct_dir': str( project ),
        'cxx_profiles_report_root': str( project ),
        'cxx_profiles_report_link_style': 'gitlab',
        'report_uri': 'https://git.example.com/org/acme_matcher.git',
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    metadata_env = dict( env )
    payload = wrap_report_payload(
        inventory.as_report_model(),
        env,
        inventory=inventory,
    )
    payload[ 'metadata' ][ 'report_uri' ] = metadata_env[ 'report_uri' ]
    payload[ 'metadata' ][ 'report_project' ] = 'acme_matcher'
    return payload, {
        'project': str( project ),
        'source': str( source ),
        'download': str( download ),
        'encoded_folder': _ENCODED_DEP_FOLDER,
    }


def test_collect_forbidden_tokens_from_input_paths( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    forbidden = collect_forbidden_tokens( payload )
    assert originals[ 'encoded_folder' ] in forbidden
    assert 'common_types' in forbidden
    assert 'git.example.com' in forbidden
    assert 'acme_matcher' in forbidden


def test_anonymise_report_payload_scrubs_identity_and_paths( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    forbidden = collect_forbidden_tokens( payload )
    original_summary = dict( payload[ 'summary' ] )
    original_context = json.loads( json.dumps( payload[ 'context' ] ) )

    anonymised = anonymise_report_payload( payload )
    serialized = json.dumps( anonymised )

    assert anonymised[ 'metadata' ][ 'anonymised' ] is True
    assert anonymised[ 'metadata' ][ 'sconstruct_dir' ] == ANON_PLACEHOLDER_ROOT
    assert anonymised[ 'metadata' ][ 'report_uri' ] == ''
    assert anonymised[ 'metadata' ][ 'link_style' ] == 'local'

    verify_anonymised_output( anonymised, forbidden )

    assert '@' not in serialized
    assert 'git_ssh_' not in serialized
    assert originals[ 'project' ] not in serialized

    assert anonymised[ 'summary' ] == original_summary
    assert anonymised[ 'context' ] == original_context

    location_paths = [ row[ 'path' ] for row in anonymised[ 'locations' ] ]
    assert any( path.startswith( '{}/'.format( PROJECT_ROOT ) ) for path in location_paths )
    assert any( path.startswith( '{}/lib-'.format( DEPS_ROOT ) ) for path in location_paths )


def test_anonymise_strips_scope_path_suffix_and_placeholder_metadata( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    payload[ 'report' ][ 'scopes' ][ 0 ][ 'scope_path_suffix' ] = 'test/orders/sconscript'
    payload[ 'report' ][ 'scopes' ][ 0 ][ 'sconscript' ] = './test/orders/sconscript'
    forbidden = collect_forbidden_tokens( payload )

    anonymised = anonymise_report_payload( payload )

    assert anonymised[ 'metadata' ][ 'sconstruct_dir' ] == ANON_PLACEHOLDER_ROOT
    assert 'scope_path_suffix' not in json.dumps( anonymised )
    assert 'test/orders/sconscript' not in json.dumps( anonymised )
    assert 'orders' not in json.dumps( anonymised[ 'report' ] )
    verify_anonymised_output( anonymised, forbidden )


def test_anonymise_strips_html_enrichment_path_copies( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    real_path = originals[ 'download' ]
    payload[ 'report' ][ 'rollup' ][ 'files' ][ 0 ][ 'display_path' ] = str( real_path )
    payload[ 'report' ][ 'rollup' ][ 'files' ][ 0 ][ 'path_tooltip' ] = str( real_path )
    payload[ 'report' ][ 'rollup' ][ 'rules' ][ 0 ][ 'violating_files_display' ] = {
        'multi_build': False,
        'items': [ { 'path': str( real_path ), 'refs': 1 } ],
    }

    anonymised = anonymise_report_payload( payload )
    serialized = json.dumps( anonymised )

    assert str( real_path ) not in serialized
    assert 'display_path' not in serialized
    assert 'violating_files_display' not in serialized
    verify_anonymised_output( anonymised, collect_forbidden_tokens( payload ) )


def test_path_anonymiser_collapses_encoded_download_folder( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    from cuppa.cpp.profiles_report.anonymise import PathAnonymiser

    anonymiser = PathAnonymiser(
        payload[ 'metadata' ],
        forbidden=collect_forbidden_tokens( payload ),
    )
    rewritten = anonymiser.anonymise_path( originals[ 'download' ] )
    assert rewritten.startswith( '{}/lib-'.format( DEPS_ROOT ) )
    assert originals[ 'encoded_folder' ] not in rewritten
    assert 'git.example.com' not in rewritten
    assert '@' not in rewritten


def test_anonymise_is_deterministic( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    first = anonymise_report_payload( payload )
    second = anonymise_report_payload( payload )
    assert first == second


def test_anonymise_requires_force_when_already_anonymised( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    anonymised = anonymise_report_payload( payload )
    with pytest.raises( ValueError, match='metadata.anonymised' ):
        anonymise_report_payload( anonymised )
    again = anonymise_report_payload( anonymised, force=True )
    assert again[ 'metadata' ][ 'anonymised' ] is True


def test_anonymised_json_regen_uses_json_paths_in_html( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    anonymised = anonymise_report_payload( payload )

    json_path = tmp_path / 'anonymised.json'
    json_path.write_text( json.dumps( anonymised ), encoding='utf-8' )

    from scripts import regenerate_profiles_report

    argv = [
        str( json_path ),
        '--from-json',
    ]
    assert regenerate_profiles_report.main( argv ) == 0
    html = ( tmp_path / 'cxx-profiles-index.html' ).read_text( encoding='utf-8' )
    assert originals[ 'encoded_folder' ] not in html
    assert 'git.example.com' not in html
    assert 'vendor' not in html
    assert 'file://' not in html
    assert 'by-source/' not in html
    assert 'acme_matcher' not in html
    assert 'example-project' in html


def test_anonymised_json_regen_ignores_live_vcs_and_cwd( tmp_path, monkeypatch ):
    payload, originals = _sample_payload( tmp_path )
    anonymised = anonymise_report_payload( payload )

    json_path = tmp_path / 'anonymised.json'
    json_path.write_text( json.dumps( anonymised ), encoding='utf-8' )

    def _fake_test_linking( env, link_style='raw' ):
        return (
            'git@git.example.com:org/matching_facility.git',
            'git@git.example.com:org/matching_facility.git',
            'master',
            'origin',
            'cplx_dex_r1.15-167-gb39732e',
        )

    monkeypatch.setattr(
        'cuppa.cpp.profiles_report.report_html.initialise_test_linking',
        _fake_test_linking,
    )

    from scripts import regenerate_profiles_report

    assert regenerate_profiles_report.main( [ str( json_path ), '--from-json' ] ) == 0
    index_html = ( tmp_path / 'cxx-profiles-index.html' ).read_text( encoding='utf-8' )
    assert 'matching_facility' not in index_html
    assert 'clearpool' not in index_html
    assert 'cplx_dex_r1.15' not in index_html
    assert 'b39732e' not in index_html
    assert 'example-project' in index_html

    scope_files = list( tmp_path.glob( 'cxx-profiles--*.html' ) )
    assert scope_files
    scope_html = scope_files[ 0 ].read_text( encoding='utf-8' )
    assert 'matching_facility' not in scope_html
    assert 'example-project' in scope_html
    assert originals[ 'encoded_folder' ] not in scope_html


def test_anonymised_json_regen_defaults_output_next_to_json( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    anonymised = anonymise_report_payload( payload )

    json_dir = tmp_path / 'shared'
    json_dir.mkdir()
    json_path = json_dir / 'index.anonymised.json'
    json_path.write_text( json.dumps( anonymised ), encoding='utf-8' )

    from scripts import regenerate_profiles_report

    argv = [
        str( json_path ),
        '--from-json',
    ]
    assert regenerate_profiles_report.main( argv ) == 0
    assert ( json_dir / 'cxx-profiles-index.html' ).is_file()


def test_anonymise_profiles_report_cli( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    input_path = tmp_path / 'index.json'
    output_path = tmp_path / 'index.anonymised.json'
    mapping_path = tmp_path / 'mapping.local.json'
    input_path.write_text( json.dumps( payload ), encoding='utf-8' )

    from scripts import anonymise_profiles_report

    argv = [
        '--in',
        str( input_path ),
        '--out',
        str( output_path ),
        '--mapping-out',
        str( mapping_path ),
    ]
    assert anonymise_profiles_report.main( argv ) == 0
    assert output_path.is_file()
    assert mapping_path.is_file()
    data = json.loads( output_path.read_text( encoding='utf-8' ) )
    assert data[ 'metadata' ][ 'anonymised' ] is True
    verify_anonymised_output( data, collect_forbidden_tokens( payload ) )


def test_load_thematic_names_has_required_pools():
    names = load_thematic_names()
    assert names[ 'dependency_slugs' ]
    assert names[ 'project_slugs' ]
    assert names[ 'path_names' ]
    assert names[ 'path_compounds' ]


def test_snake_case_stem_prefers_path_compounds( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    from cuppa.cpp.profiles_report.anonymise import PathAnonymiser

    names = load_thematic_names()
    anonymiser = PathAnonymiser(
        payload[ 'metadata' ],
        thematic_names=names,
        forbidden=collect_forbidden_tokens( payload ),
    )
    rewritten = anonymiser._thematic_stem( 'common_types' )
    forbidden = collect_forbidden_tokens( payload )
    from cuppa.cpp.profiles_report.anonymise import _thematic_name_is_safe

    assert rewritten != 'common_types'
    assert 'common' not in rewritten
    assert _thematic_name_is_safe( rewritten, forbidden )


def test_us_metadata_key_still_triggers_anonymised_regen( tmp_path ):
    payload, originals = _sample_payload( tmp_path )
    anonymised = anonymise_report_payload( payload )
    anonymised[ 'metadata' ][ 'anonymized' ] = anonymised[ 'metadata' ].pop( 'anonymised' )
    anonymised[ 'metadata' ][ 'anonymization_version' ] = anonymised[ 'metadata' ].pop(
        'anonymisation_version',
    )

    json_path = tmp_path / 'legacy.anonymized.json'
    json_path.write_text( json.dumps( anonymised ), encoding='utf-8' )

    from scripts import regenerate_profiles_report

    assert regenerate_profiles_report.main( [ str( json_path ), '--from-json' ] ) == 0
    html = ( tmp_path / 'cxx-profiles-index.html' ).read_text( encoding='utf-8' )
    assert originals[ 'encoded_folder' ] not in html
    assert 'by-source/' not in html


def test_us_regen_cli_flag_still_works( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    anonymised = anonymise_report_payload( payload )
    json_path = tmp_path / 'index.anonymised.json'
    json_path.write_text( json.dumps( anonymised ), encoding='utf-8' )

    from scripts import regenerate_profiles_report

    assert regenerate_profiles_report.main(
        [ str( json_path ), '--from-json', '--anonymized' ],
    ) == 0
    assert ( tmp_path / 'cxx-profiles-index.html' ).is_file()


def test_us_anonymize_module_and_script_aliases( tmp_path ):
    payload, _originals = _sample_payload( tmp_path )
    from cuppa.cpp.profiles_report.anonymize import anonymize_report_payload as us_payload
    from scripts import anonymize_profiles_report

    assert us_payload( payload )[ 'metadata' ][ 'anonymised' ] is True

    input_path = tmp_path / 'index.json'
    output_path = tmp_path / 'index.anonymized.json'
    input_path.write_text( json.dumps( payload ), encoding='utf-8' )
    assert anonymize_profiles_report.main(
        [ '--in', str( input_path ), '--out', str( output_path ) ],
    ) == 0
    assert output_path.is_file()


def test_pick_unique_synthesises_when_curated_pool_exhausted():
    from cuppa.cpp.profiles_report.anonymise import _pick_unique

    pool = [ 'alpha', 'beta', 'gamma' ]
    used = set( pool )
    forbidden = set()

    first = _pick_unique( 'orders', pool, used, forbidden )
    second = _pick_unique( 'orders', pool, set( pool ), forbidden )

    assert first.startswith( 'slot-' )
    assert first == second
    assert first not in pool

    many_used = set( pool )
    for index in range( 100 ):
        many_used.add(
            _pick_unique( 'stem-{}'.format( index ), pool, many_used, forbidden ),
        )
    assert len( many_used ) == len( pool ) + 100


def test_repeated_stem_is_stable_when_pool_exhausted():
    from cuppa.cpp.profiles_report.anonymise import PathAnonymiser, load_thematic_names

    names = load_thematic_names()
    anonymiser = PathAnonymiser(
        {},
        thematic_names=names,
        forbidden={ 'orders', 'order', 'matching', 'facility' },
    )
    anonymiser._used_stems = set( names[ 'path_names' ] ) | set( names[ 'path_compounds' ] )

    results = [ anonymiser._thematic_stem( 'orders' ) for _ in range( 100 ) ]
    assert len( set( results ) ) == 1
    assert results[ 0 ].startswith( 'slot-' )
