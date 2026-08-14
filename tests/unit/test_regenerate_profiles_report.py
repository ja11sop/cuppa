#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from pathlib import Path

import pytest

from cuppa.cpp.profiles_report.report_html import INDEX_BASENAME, JSON_BASENAME

pytestmark = pytest.mark.unit

_FIXTURE_CAPTURE = (
    Path( __file__ ).resolve().parents[ 1 ]
    / 'fixtures'
    / 'profiles_capture'
    / 'sample_capture.txt'
)


def test_regenerate_profiles_report_writes_html_and_json( tmp_path, monkeypatch ):
    source = tmp_path / 'home' / 'user' / 'include' / 'widget' / 'nonce.hpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int x;\n', encoding='utf-8' )

    from scripts import regenerate_profiles_report

    argv = [
        str( _FIXTURE_CAPTURE ),
        '--sconstruct-dir',
        str( tmp_path ),
        '--artifacts-root',
        '_artifacts',
    ]
    assert regenerate_profiles_report.main( argv ) == 0

    report_dir = tmp_path / '_artifacts' / 'cxx-profiles'
    assert ( report_dir / INDEX_BASENAME ).is_file()
    assert ( report_dir / JSON_BASENAME ).is_file()
    index_html = ( report_dir / INDEX_BASENAME ).read_text( encoding='utf-8' )
    assert 'Violations By-Rule' in index_html
    assert 'table-layout: fixed' not in index_html


def test_regenerate_profiles_report_from_json( tmp_path ):
    source = tmp_path / 'src' / 'widget.cpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int* p;\n', encoding='utf-8' )

    from cuppa.cpp.cxx_profiles_report import ProfilesInventory, ProfilesScope, parse_profiles_diagnostic
    from cuppa.cpp.profiles_report.report_html import write_profiles_reports
    from scripts import regenerate_profiles_report

    scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    line = (
        "{path}:1:6: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'"
    ).format( path=source )
    inventory = ProfilesInventory()
    inventory.record( scope, parse_profiles_diagnostic( line ) )

    env = {
        'sconstruct_dir': str( tmp_path ),
        'artifacts_root': '_artifacts',
        'abs_artifacts_root': str( tmp_path / '_artifacts' ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path ),
    }
    first = write_profiles_reports( inventory, env )
    json_path = tmp_path / '_artifacts' / 'cxx-profiles' / JSON_BASENAME
    assert json_path.is_file()

    out_dir = tmp_path / 'regen'
    argv = [
        str( json_path ),
        '--from-json',
        '--sconstruct-dir',
        str( tmp_path ),
        '--report-dir',
        str( out_dir ),
    ]
    assert regenerate_profiles_report.main( argv ) == 0
    assert ( out_dir / INDEX_BASENAME ).is_file()
    html = ( out_dir / INDEX_BASENAME ).read_text( encoding='utf-8' )
    assert 'violation of' in html
    assert 'prof-index-project' in html
    assert len( first[ 'source_paths' ] ) == 1
    assert len( list( ( out_dir / 'by-source' ).glob( '*.html' ) ) ) == 1


def test_regenerate_profiles_report_from_json_uses_metadata_sconstruct_dir( tmp_path ):
    source = tmp_path / 'src' / 'widget.cpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int* p;\n', encoding='utf-8' )

    from cuppa.cpp.cxx_profiles_report import ProfilesInventory, ProfilesScope, parse_profiles_diagnostic
    from cuppa.cpp.profiles_report.report_html import write_profiles_reports
    from scripts import regenerate_profiles_report

    scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    line = (
        "{path}:1:6: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'"
    ).format( path=source )
    inventory = ProfilesInventory()
    inventory.record( scope, parse_profiles_diagnostic( line ) )
    env = {
        'sconstruct_dir': str( tmp_path ),
        'artifacts_root': '_artifacts',
        'abs_artifacts_root': str( tmp_path / '_artifacts' ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path ),
    }
    write_profiles_reports( inventory, env )
    json_path = tmp_path / '_artifacts' / 'cxx-profiles' / JSON_BASENAME

    out_dir = tmp_path / 'metadata-regen'
    argv = [
        str( json_path ),
        '--from-json',
        '--report-dir',
        str( out_dir ),
    ]
    assert regenerate_profiles_report.main( argv ) == 0
    assert ( out_dir / INDEX_BASENAME ).is_file()
    assert ( out_dir / 'by-source' ).is_dir()


def test_regenerate_profiles_report_from_json_skip_source_pages( tmp_path ):
    source = tmp_path / 'src' / 'widget.cpp'
    source.parent.mkdir( parents=True )
    source.write_text( 'int* p;\n', encoding='utf-8' )

    from cuppa.cpp.cxx_profiles_report import ProfilesInventory, ProfilesScope, parse_profiles_diagnostic
    from cuppa.cpp.profiles_report.report_html import write_profiles_reports
    from scripts import regenerate_profiles_report

    scope = ProfilesScope(
        sconscript='./widget/sconscript',
        variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
        toolchain='clang24_profiles',
        variant_label='dbg',
    )
    line = (
        "{path}:1:6: error: pointer to uninitialized memory must be marked "
        "'[[ref_to_uninit]]' under profile 'std::init'"
    ).format( path=source )
    inventory = ProfilesInventory()
    inventory.record( scope, parse_profiles_diagnostic( line ) )
    env = {
        'sconstruct_dir': str( tmp_path ),
        'artifacts_root': '_artifacts',
        'abs_artifacts_root': str( tmp_path / '_artifacts' ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path ),
    }
    write_profiles_reports( inventory, env )
    json_path = tmp_path / '_artifacts' / 'cxx-profiles' / JSON_BASENAME

    out_dir = tmp_path / 'tables-only'
    argv = [
        str( json_path ),
        '--from-json',
        '--skip-source-pages',
        '--sconstruct-dir',
        str( tmp_path ),
        '--report-dir',
        str( out_dir ),
    ]
    assert regenerate_profiles_report.main( argv ) == 0
    assert ( out_dir / INDEX_BASENAME ).is_file()
    assert not ( out_dir / 'by-source' ).exists()
