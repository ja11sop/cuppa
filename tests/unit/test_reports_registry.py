#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.core import storage_actions
from cuppa.core import storage_options
from cuppa.core.storage_options import default
from cuppa.reports.list_available_reports import (
    list_available_reports,
    serialise_available_reports,
)
from cuppa.reports.registry import (
    REPORT_KINDS,
    abs_artefacts_root_from_env,
    default_report_dir_for_kind,
    report_kind_by_id,
    supporting_toolchain_rows_for_kind,
    toolchain_supports_report_kind,
)
from tests.helpers.fakes import FakeEnv

pytestmark = pytest.mark.unit


class FakeToolchain( object ):

    def __init__(
            self,
            name,
            family,
            version='1.0',
            coverage=False,
            profiles=False,
            test=True,
    ):
        self._name = name
        self._family = family
        self._version = version
        self._coverage = coverage
        self._profiles = profiles
        self._test = test
        self.values = { 'CXX': '/usr/bin/{}'.format( name ) }

    def family( self ):
        return self._family

    def version( self ):
        return self._version

    def binary( self ):
        return self.values[ 'CXX' ]

    def supports_coverage( self ):
        return self._coverage

    def profiles_supported( self, env ):
        return self._profiles

    def test_runners( self ):
        return [ 'process' ] if self._test else []


def _env_with_toolchains( tmp_path, toolchains ):
    env = FakeEnv( {} )
    env[ 'sconstruct_dir' ] = str( tmp_path )
    env[ 'toolchains' ] = toolchains
    storage_options.process_storage_options( env )
    return env


def test_report_registry_includes_cxx_profiles():
    kind = report_kind_by_id( 'cxx-profiles' )
    assert kind is not None
    assert kind.env_method == 'CollateCxxProfilesIndex'
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
        'artefacts_root': '_artefacts',
        'abs_artefacts_root': str( tmp_path / '_artefacts' ),
    }
    kind = report_kind_by_id( 'cxx-profiles' )
    assert default_report_dir_for_kind( env, kind ) == str(
        tmp_path / '_artefacts' / 'cxx-profiles',
    )


def test_toolchain_supports_report_kind_matrix():
    gcc = FakeToolchain( 'gcc', 'gcc', coverage=True, profiles=False )
    clang_profiles = FakeToolchain( 'clang24_profiles', 'clang', coverage=True, profiles=True )
    msvc = FakeToolchain( 'vc', 'msvc', coverage=False, profiles=False )

    assert toolchain_supports_report_kind( gcc, 'test' )
    assert toolchain_supports_report_kind( gcc, 'coverage' )
    assert not toolchain_supports_report_kind( gcc, 'cxx-profiles' )

    assert toolchain_supports_report_kind( clang_profiles, 'cxx-profiles' )

    assert toolchain_supports_report_kind( msvc, 'test' )
    assert not toolchain_supports_report_kind( msvc, 'coverage' )
    assert not toolchain_supports_report_kind( msvc, 'cxx-profiles' )


def test_supporting_toolchain_rows_for_coverage_excludes_msvc( tmp_path ):
    toolchains = {
        'gcc': FakeToolchain( 'gcc', 'gcc', coverage=True ),
        'vc': FakeToolchain( 'vc', 'msvc', coverage=False ),
        'clang24_profiles_2026_08_07_27': FakeToolchain(
            'clang24_profiles_2026_08_07_27', 'clang', coverage=True, profiles=True,
        ),
    }
    env = _env_with_toolchains( tmp_path, toolchains )
    names = [ row[ 'name' ] for row in supporting_toolchain_rows_for_kind( env, 'coverage' ) ]
    assert names == [ 'clang24_profiles_2026_08_07_27', 'gcc' ]

    profile_names = [
        row[ 'name' ] for row in supporting_toolchain_rows_for_kind( env, 'cxx-profiles' )
    ]
    assert profile_names == [ 'clang24_profiles_2026_08_07_27' ]


def test_list_available_reports_text_mentions_toolchains_and_artefacts_root( tmp_path ):
    env = _env_with_toolchains(
        tmp_path,
        {
            'gcc': FakeToolchain( 'gcc', 'gcc', coverage=True ),
            'clang24_profiles_2026_08_07_27': FakeToolchain(
                'clang24_profiles_2026_08_07_27', 'clang', coverage=True, profiles=True,
            ),
        },
    )
    env[ 'list_format' ] = 'text'
    storage_actions.process_storage_action_options( env )

    from io import StringIO
    out = StringIO()
    assert list_available_reports( env, out ) == 0
    text = out.getvalue()
    header_pos = text.index( 'Report kinds available with current toolchains' )
    artefacts_pos = text.index( '{artefacts_root}:' )
    build_pos = text.index( '{build_root}:' )
    test_pos = text.index( 'Collated Test Report' )
    assert header_pos < artefacts_pos < build_pos < test_pos
    assert '{artefacts_root}:' in text
    assert '{build_root}:' in text
    assert 'Report kinds available with current toolchains' in text
    assert 'Collated Test Report' in text
    assert 'Collated Coverage Report' in text
    assert 'Collated C++ Profiles Report' in text
    assert 'env.CollateTestReportIndex()' in text
    assert 'env.CollateCoverageIndex()' in text
    assert 'env.CollateCxxProfilesIndex()' in text
    assert '{artefacts_root}/test/' in text
    assert 'specify destination, usually {artefacts_root}/test/' in text
    assert 'specify destination, default {artefacts_root}/cxx-profiles/' in text
    assert '{build_root}/' in text
    assert 'sources:' in text
    assert 'destination:' in text
    assert 'Note: Often used with --cxx-profiles-enforce=' in text
    assert 'Toolchains:' in text
    assert 'clang24_profiles_2026_08_07_27' in text
    assert '--remove-artefacts' in text


def test_list_available_reports_json_includes_supporting_toolchains( tmp_path ):
    env = _env_with_toolchains(
        tmp_path,
        { 'gcc': FakeToolchain( 'gcc', 'gcc', coverage=True ) },
    )
    payload = serialise_available_reports( env )
    assert payload[ 'artefacts_root' ] == default.artefacts_root
    assert payload[ 'artifacts_root' ] == payload[ 'artefacts_root' ]
    kinds = { row[ 'kind' ]: row for row in payload[ 'report_kinds' ] }
    assert kinds.keys() == { kind.kind for kind in REPORT_KINDS }
    assert kinds[ 'test' ][ 'title' ] == 'Collated Test Report'
    assert kinds[ 'coverage' ][ 'toolchains_by_family' ][ 0 ][ 'preferred' ] == 'gcc'
    assert kinds[ 'coverage' ][ 'supporting_toolchains' ] == [ 'gcc' ]
    assert kinds[ 'cxx-profiles' ][ 'supporting_toolchains' ] == []


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
