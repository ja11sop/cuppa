#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.cpp.cxx_profiles_report import (
    ProfilesInventory,
    ProfilesScope,
    parse_profiles_diagnostic,
)
from cuppa.cpp.profiles_report.report_html import write_profiles_reports
from cuppa.reports.manifest import (
    KIND_CXX_PROFILES,
    append_cxx_profiles_entry,
    append_entry,
    build_cxx_profiles_entry,
    compute_invocation_key,
    cxx_profiles_report_options,
    manifest_path,
    maybe_remove_cxx_profiles_on_clean,
    paths_from_entry,
    read_entries,
    remove_matching_entries,
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


def test_compute_invocation_key_is_stable():
    options = {
        'destination': '_artifacts/cxx-profiles',
        'link_style': 'local',
        'report_root': None,
        'enforce': [ 'std::init' ],
        'cxx_profiles': True,
    }
    key_a = compute_invocation_key( '/tmp/project', [ 'cuppa', '-D' ], options )
    key_b = compute_invocation_key( '/tmp/project', [ 'cuppa', '-D' ], options )
    assert key_a == key_b
    assert key_a.startswith( 'sha256:' )


def test_paths_from_entry_unions_session_and_scope_paths():
    entry = {
        'session_paths': [ 'a.html', 'a.json' ],
        'scopes': [
            { 'paths': [ 'scope.html' ] },
        ],
    }
    assert paths_from_entry( entry ) == [ 'a.html', 'a.json', 'scope.html' ]


def test_remove_matching_entries_deletes_files( tmp_path, monkeypatch ):
    monkeypatch.chdir( tmp_path )
    report_dir = tmp_path / '_artifacts' / 'cxx-profiles'
    report_dir.mkdir( parents=True )
    index = report_dir / 'cxx-profiles-index.html'
    index.write_text( '<html></html>', encoding='utf-8' )

    options = {
        'destination': '_artifacts/cxx-profiles',
        'link_style': 'local',
        'report_root': None,
        'enforce': [],
        'cxx_profiles': True,
    }
    key = compute_invocation_key( str( tmp_path ), [ 'cuppa' ], options )
    append_entry(
        str( tmp_path ),
        {
            'kind': KIND_CXX_PROFILES,
            'schema': 1,
            'invocation_key': key,
            'session_paths': [ '_artifacts/cxx-profiles/cxx-profiles-index.html' ],
            'scopes': [],
        },
    )

    removed, deleted = remove_matching_entries( str( tmp_path ), key )
    assert removed == 1
    assert '_artifacts/cxx-profiles/cxx-profiles-index.html' in deleted
    assert not index.is_file()
    assert not os.path.isfile( manifest_path( str( tmp_path ) ) )


def test_build_cxx_profiles_entry_marks_incomplete_scope( tmp_path, monkeypatch ):
    monkeypatch.chdir( tmp_path )
    model = _sample_model()
    scope_stem = model[ 'scopes' ][ 0 ][ 'report_stem' ]
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_enforce': [ 'std::init' ],
        'cxx_profiles': True,
    }
    entry = build_cxx_profiles_entry(
        env,
        model,
        session_paths=[
            str( tmp_path / '_artifacts/cxx-profiles/index.html' ),
        ],
        scope_paths={
            scope_stem: [
                str( tmp_path / '_artifacts/cxx-profiles/scope.html' ),
            ],
        },
        incomplete_scopes=[ _SAMPLE_SCOPE.variant_dir ],
        partial=True,
    )
    assert entry[ 'partial' ] is True
    assert entry[ 'scopes' ][ 0 ][ 'complete' ] is False
    assert entry[ 'options' ][ 'enforce' ] == [ 'std::init' ]


def test_maybe_remove_on_clean_requires_report_flag( tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path ),
        'clean': True,
        'cxx_profiles_report': False,
    }
    removed, deleted = maybe_remove_cxx_profiles_on_clean( env )
    assert removed == 0
    assert deleted == []


def test_write_profiles_reports_appends_manifest_via_helper( tmp_path, monkeypatch ):
    monkeypatch.chdir( tmp_path )
    inventory = ProfilesInventory()
    inventory.record( _SAMPLE_SCOPE, parse_profiles_diagnostic( _LINE ) )
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'local',
        'cxx_profiles_report_root': str( tmp_path ),
        'cxx_profiles_enforce': [ 'std::init' ],
        'cxx_profiles': True,
    }
    result = write_profiles_reports( inventory, env )
    model = result[ 'model' ]
    append_cxx_profiles_entry(
        env,
        model,
        result[ 'session_paths' ],
        result[ 'scope_paths' ],
    )

    entries = read_entries( str( tmp_path ) )
    assert len( entries ) == 1
    assert entries[ 0 ][ 'kind' ] == KIND_CXX_PROFILES
    assert paths_from_entry( entries[ 0 ] )


def test_cxx_profiles_report_options_normalises_destination( tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': 'gitlab',
        'cxx_profiles_enforce': [ 'std::init', 'std::type' ],
        'cxx_profiles': True,
    }
    options = cxx_profiles_report_options( env )
    assert options[ 'destination' ] == '_artifacts/cxx-profiles'
    assert options[ 'link_style' ] == 'gitlab'
    assert options[ 'enforce' ] == [ 'std::init', 'std::type' ]
