#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.core import storage_actions
from cuppa.core import storage_options
from cuppa.core.storage_options import default
from cuppa.reports.list_reports import list_reports
from cuppa.reports.registry import (
    REPORT_KINDS,
    abs_artefacts_root_from_env,
    default_report_dir_for_kind,
    report_kind_by_id,
    serialise_report_kinds,
)
from tests.helpers.fakes import FakeEnv

pytestmark = pytest.mark.unit


def test_report_registry_includes_cxx_profiles():
    kind = report_kind_by_id( 'cxx-profiles' )
    assert kind is not None
    assert kind.env_method == 'CxxProfilesReport'
    assert kind.manifest_kind == 'cxx-profiles'
    assert kind.default_subdir == 'cxx-profiles'


def test_abs_artefacts_root_prefers_british_env_keys( tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path ),
        'artefacts_root': 'out/artefacts',
        'abs_artefacts_root': str( tmp_path / 'out' / 'artefacts' ),
        'artifacts_root': '_artifacts',
        'abs_artifacts_root': str( tmp_path / '_artifacts' ),
    }
    assert abs_artefacts_root_from_env( env ) == str( tmp_path / 'out' / 'artefacts' )


def test_default_report_dir_for_cxx_profiles( tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path ),
        'artefacts_root': '_artifacts',
        'abs_artefacts_root': str( tmp_path / '_artifacts' ),
    }
    kind = report_kind_by_id( 'cxx-profiles' )
    assert default_report_dir_for_kind( env, kind ) == str(
        tmp_path / '_artifacts' / 'cxx-profiles',
    )


def test_list_reports_text_mentions_profiles_and_artefacts_root( tmp_path ):
    env = FakeEnv( {} )
    env[ 'sconstruct_dir' ] = str( tmp_path )
    env[ 'list_format' ] = 'text'
    storage_options.process_storage_options( env )
    storage_actions.process_storage_action_options( env )

    from io import StringIO
    out = StringIO()
    assert list_reports( env, out ) == 0
    text = out.getvalue()
    assert 'Artefacts root:' in text
    assert 'cxx-profiles/' in text
    assert 'env.CxxProfilesReport()' in text
    assert '--remove-artefacts' in text


def test_list_reports_json_includes_us_spelling_aliases( tmp_path ):
    env = FakeEnv( {} )
    env[ 'sconstruct_dir' ] = str( tmp_path )
    storage_options.process_storage_options( env )
    payload = serialise_report_kinds( env )
    assert payload[ 'artefacts_root' ] == default.artefacts_root
    assert payload[ 'artifacts_root' ] == payload[ 'artefacts_root' ]
    assert payload[ 'abs_artifacts_root' ] == payload[ 'abs_artefacts_root' ]
    kinds = { row[ 'kind' ] for row in payload[ 'report_kinds' ] }
    assert kinds == { kind.kind for kind in REPORT_KINDS }


def test_artefacts_root_cli_sets_british_and_us_env_keys( tmp_path, monkeypatch ):
    monkeypatch.chdir( tmp_path )
    env = FakeEnv( { 'artefacts_root': 'out/reports' } )
    env[ 'sconstruct_dir' ] = str( tmp_path )
    storage_options.process_storage_options( env )
    assert env[ 'artefacts_root' ] == os.path.join( 'out', 'reports' )
    assert env[ 'artifacts_root' ] == env[ 'artefacts_root' ]
    assert env[ 'abs_artefacts_root' ] == str( tmp_path / 'out' / 'reports' )
    assert env[ 'abs_artifacts_root' ] == env[ 'abs_artefacts_root' ]


def test_artifacts_root_us_spelling_alias_still_works( tmp_path, monkeypatch ):
    monkeypatch.chdir( tmp_path )
    env = FakeEnv( { 'artifacts_root': 'out/reports' } )
    env[ 'sconstruct_dir' ] = str( tmp_path )
    storage_options.process_storage_options( env )
    assert env[ 'artefacts_root' ] == os.path.join( 'out', 'reports' )
