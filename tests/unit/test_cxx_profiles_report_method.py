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
from cuppa.methods.cxx_error_limit import reset_error_limit_state_for_tests
from cuppa.progress import NotifyProgress

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_collector():
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()
    reset_error_limit_state_for_tests()
    yield
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()
    reset_error_limit_state_for_tests()


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
    assert ProfilesDiagnosticCollector._session.activation_via_cli is True


def test_collate_registers_declaring_sconscript():
    env = {
        'cxx_profiles': True,
        'cxx_profiles_enforce': [ 'std::init' ],
        'sconscript_file': 'orders/sconscript',
    }
    callable_method = CollateCxxProfilesIndexCallable()
    callable_method( env )
    session = ProfilesDiagnosticCollector._session
    assert 'orders/sconscript' in session.declaring_sconscripts()
    assert session.activation_via_cli is False


def test_cli_activation_disables_scope_filter_even_with_declaring_sconscript():
    env = FakeEnv( {
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': None,
        'cxx_profiles_report_context': 'full',
        'cxx_profiles_report_root': None,
    } )
    env[ 'cxx_profiles' ] = True
    CollateCxxProfilesIndexMethod.get_options( env )
    env[ 'sconscript_file' ] = 'orders/sconscript'
    CollateCxxProfilesIndexCallable()( env )
    session = ProfilesDiagnosticCollector._session
    assert session.activation_via_cli is True
    assert 'orders/sconscript' in session.declaring_sconscripts()
    filtered, metadata = session.index_inventory()
    assert metadata is None
    assert filtered.unique_locations() == session.inventory.unique_locations()


def test_method_only_index_inventory_filters_undeclared_sconscript():
    from cuppa.cpp.cxx_profiles_report import (
        ProfilesScope,
        parse_profiles_diagnostic,
    )

    env = {
        'cxx_profiles': True,
        'sconscript_file': 'orders/sconscript',
    }
    CollateCxxProfilesIndexCallable()( env )
    session = ProfilesDiagnosticCollector._session
    line = (
        "/tmp/a.cpp:1:1: error: variable 'Value' must be initialized or marked "
        "'[[uninit]]' under profile 'std::init'"
    )
    diagnostic = parse_profiles_diagnostic( line )
    declared = ProfilesScope(
        sconscript='orders/sconscript',
        variant_dir='_build/orders/clang/dbg/x86_64/cxx2c',
        toolchain='clang',
        variant_label='dbg',
    )
    other = declared._replace( sconscript='trades/sconscript' )
    session.record( declared, diagnostic )
    session.record( other, diagnostic )
    filtered, metadata = session.index_inventory()
    assert metadata[ 'omitted_scope_count' ] == 1
    assert metadata[ 'declaring_sconscripts' ] == [ 'orders/sconscript' ]
    assert filtered.unique_locations() == 1


def test_filter_keeps_union_of_declaring_sconscripts():
    from cuppa.cpp.cxx_profiles_report import (
        ProfilesScope,
        parse_profiles_diagnostic,
    )

    CollateCxxProfilesIndexCallable()( {
        'cxx_profiles': True,
        'sconscript_file': 'orders/sconscript',
    } )
    CollateCxxProfilesIndexCallable()( {
        'cxx_profiles': True,
        'sconscript_file': 'trades/sconscript',
    } )
    session = ProfilesDiagnosticCollector._session
    line = (
        "/tmp/a.cpp:1:1: error: variable 'Value' must be initialized or marked "
        "'[[uninit]]' under profile 'std::init'"
    )
    diagnostic = parse_profiles_diagnostic( line )
    base = ProfilesScope(
        sconscript='orders/sconscript',
        variant_dir='_build/orders/clang/dbg/x86_64/cxx2c',
        toolchain='clang',
        variant_label='dbg',
    )
    session.record( base, diagnostic )
    session.record( base._replace( sconscript='trades/sconscript' ), diagnostic )
    session.record( base._replace( sconscript='other/sconscript' ), diagnostic )
    filtered, metadata = session.index_inventory()
    assert metadata[ 'omitted_scope_count' ] == 1
    scripts = { loc.scope.sconscript for loc in filtered.locations() }
    assert scripts == { 'orders/sconscript', 'trades/sconscript' }


def test_filter_does_not_include_child_sconscript_from_parent_declaration():
    from cuppa.cpp.cxx_profiles_report import (
        ProfilesScope,
        parse_profiles_diagnostic,
    )

    CollateCxxProfilesIndexCallable()( {
        'cxx_profiles': True,
        'sconscript_file': 'lib/sconscript',
    } )
    session = ProfilesDiagnosticCollector._session
    diagnostic = parse_profiles_diagnostic(
        "/tmp/a.cpp:1:1: error: variable 'Value' must be initialized or marked "
        "'[[uninit]]' under profile 'std::init'"
    )
    parent = ProfilesScope(
        sconscript='lib/sconscript',
        variant_dir='_build/lib/clang/dbg/x86_64/cxx2c',
        toolchain='clang',
        variant_label='dbg',
    )
    child = parent._replace( sconscript='lib/nested/sconscript' )
    session.record( parent, diagnostic )
    session.record( child, diagnostic )
    filtered, metadata = session.index_inventory()
    assert metadata[ 'omitted_scope_count' ] == 1
    assert filtered.locations()[ 0 ].scope.sconscript == 'lib/sconscript'


def test_filter_keeps_every_variant_of_a_declaring_sconscript():
    from cuppa.cpp.cxx_profiles_report import (
        ProfilesScope,
        parse_profiles_diagnostic,
    )

    CollateCxxProfilesIndexCallable()( {
        'cxx_profiles': True,
        'sconscript_file': 'orders/sconscript',
    } )
    session = ProfilesDiagnosticCollector._session
    diagnostic = parse_profiles_diagnostic(
        "/tmp/a.cpp:1:1: error: variable 'Value' must be initialized or marked "
        "'[[uninit]]' under profile 'std::init'"
    )
    dbg = ProfilesScope(
        sconscript='orders/sconscript',
        variant_dir='_build/orders/clang/dbg/x86_64/cxx2c',
        toolchain='clang',
        variant_label='dbg',
    )
    rel = dbg._replace(
        variant_dir='_build/orders/clang/rel/x86_64/cxx2c',
        variant_label='rel',
    )
    session.record( dbg, diagnostic )
    session.record( rel, diagnostic )
    filtered, metadata = session.index_inventory()
    assert metadata[ 'omitted_scope_count' ] == 0
    assert filtered.unique_locations() == 2


def test_later_collate_destination_conflict_warns( caplog ):
    import logging

    caplog.set_level( logging.WARNING )
    first = {
        'cxx_profiles': True,
        'sconscript_file': 'orders/sconscript',
    }
    CollateCxxProfilesIndexCallable()( first )
    second = {
        'cxx_profiles': True,
        'sconscript_file': 'trades/sconscript',
    }
    CollateCxxProfilesIndexCallable()(
        second,
        destination='#_artefacts/cxx-profiles/other/',
    )
    assert any( 'ignoring later' in rec.message for rec in caplog.records )


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
