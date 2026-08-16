#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.profiles_report_collector import ProfilesDiagnosticCollector
from cuppa.methods.cxx_profiles_report import (
    CollateCxxProfilesIndexCallable,
    CollateCxxProfilesIndexMethod,
    activate_cxx_profiles_report,
    reset_inventory_report_state_for_tests,
)
from cuppa.progress import NotifyProgress

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_collector():
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()
    yield
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()


class FakeEnv(dict):
    def __init__( self, options=None ):
        super().__init__()
        self._options = options or {}

    def get_option( self, name ):
        return self._options.get( name )


def test_collate_cxx_profiles_index_method_registers_callable():
    class CuppaEnv(object):
        def __init__( self ):
            self.methods = {}

        def add_method( self, name, method ):
            self.methods[ name ] = method

    cuppa_env = CuppaEnv()
    CollateCxxProfilesIndexMethod.add_to_env( cuppa_env )
    assert isinstance(
        cuppa_env.methods[ 'CollateCxxProfilesIndex' ],
        CollateCxxProfilesIndexCallable,
    )


def test_activate_cxx_profiles_report_sets_env_and_enables_collector():
    env = {
        'cxx_profiles': True,
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    activate_cxx_profiles_report( env, link_style='gitlab' )
    assert env[ 'cxx_profiles_report' ] is True
    assert env[ 'cxx_profiles_report_link_style' ] == 'gitlab'
    assert ProfilesDiagnosticCollector._session is not None


def test_collate_cxx_profiles_index_callable_accepts_explicit_destination():
    env = {
        'cxx_profiles': True,
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    callable_method = CollateCxxProfilesIndexCallable()
    result = callable_method( env, destination='#_artefacts/cxx-profiles/custom/' )
    assert result == '#_artefacts/cxx-profiles/custom/'
    assert env[ 'cxx_profiles_report' ] == '#_artefacts/cxx-profiles/custom/'


def test_cxx_profiles_report_requires_profiles_active():
    import SCons.Errors

    env = {}
    with pytest.raises( SCons.Errors.StopError ):
        activate_cxx_profiles_report( env )


def test_cli_get_options_still_activates_collector():
    env = FakeEnv( {
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': None,
        'cxx_profiles_report_context': 'full',
        'cxx_profiles_report_root': None,
    } )
    env[ 'cxx_profiles' ] = True
    CollateCxxProfilesIndexMethod.get_options( env )
    assert env[ 'cxx_profiles_report' ] is True
    assert ProfilesDiagnosticCollector._session is not None


def test_activate_cxx_profiles_report_enables_inventory_report_mode( monkeypatch ):
    def fake_get_option( name ):
        assert name == 'ignore_errors'
        return False

    monkeypatch.setattr( 'SCons.Script.GetOption', fake_get_option )

    env = {
        'cxx_profiles': True,
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    activate_cxx_profiles_report( env )
    assert NotifyProgress.inventory_report_mode() is True


def test_activate_cxx_profiles_report_skips_keep_going_when_user_passed_ignore_errors( monkeypatch ):
    def fake_get_option( name ):
        return name == 'ignore_errors'

    monkeypatch.setattr( 'SCons.Script.GetOption', fake_get_option )

    env = {
        'cxx_profiles': True,
        'cxx_profiles_enforce': [ 'std::init' ],
    }
    activate_cxx_profiles_report( env )
    assert NotifyProgress.inventory_report_mode() is True
