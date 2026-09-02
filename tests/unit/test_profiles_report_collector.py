#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import threading

import pytest

from cuppa.cpp.cxx_profiles_report import (
    ProfilesScope,
    profiles_scope_from_construction_env,
    unscoped_profiles_scope,
)
from cuppa.cpp.profiles_report_collector import ProfilesDiagnosticCollector
from cuppa.methods.cxx_profiles_report import reset_inventory_report_state_for_tests
from cuppa.progress import NotifyProgress

pytestmark = pytest.mark.unit

_PROFILE_LINE = (
    "/home/user/project/include/widget/table.hpp"
    ":120:5: error: constructor does not initialize member 'Buffer_' "
    "under profile 'std::init'"
)

_SAMPLE_SCOPE = ProfilesScope(
    sconscript='./widget/sconscript',
    variant_dir='_build/widget/clang24_profiles/dbg/x86_64/cxx2c',
    toolchain='clang24_profiles',
    variant_label='dbg',
)


@pytest.fixture(autouse=True)
def _reset_collector():
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()
    yield
    ProfilesDiagnosticCollector.reset()
    reset_inventory_report_state_for_tests()


class _FakeToolchain(object):
    def name( self ):
        return 'clang24_profiles'


def test_profiles_scope_from_construction_env():
    env = {
        'sconscript_file': './widget/sconscript',
        'build_dir': '_build/widget/clang24_profiles/dbg/x86_64/cxx2c/working',
        'toolchain': _FakeToolchain(),
    }
    scope = profiles_scope_from_construction_env( env )
    assert scope == _SAMPLE_SCOPE


def test_profiles_scope_from_construction_env_falls_back_when_incomplete():
    assert profiles_scope_from_construction_env( {} ) == unscoped_profiles_scope()
    assert profiles_scope_from_construction_env( { 'build_dir': '_build/x' } ) == unscoped_profiles_scope()


def test_collector_records_profiles_lines():
    session = ProfilesDiagnosticCollector.activate()
    ProfilesDiagnosticCollector.record_line( _SAMPLE_SCOPE, _PROFILE_LINE )
    assert session.inventory.total_references() == 1
    assert session.inventory.unique_locations() == 1


def test_collector_records_include_stack_lines():
    session = ProfilesDiagnosticCollector.activate()
    suppressed = ProfilesDiagnosticCollector.record_line(
        _SAMPLE_SCOPE,
        '. /tmp/include/widget/table.hpp',
    )
    assert suppressed is True
    assert '/tmp/include/widget/table.hpp' in session.parsed_files()
    assert session.inventory.total_references() == 0


def test_collector_ignores_non_profiles_lines():
    session = ProfilesDiagnosticCollector.activate()
    ProfilesDiagnosticCollector.record_line( _SAMPLE_SCOPE, 'ordinary compiler noise' )
    assert session.inventory.total_references() == 0


def test_collector_merge_is_thread_safe():
    session = ProfilesDiagnosticCollector.activate()
    barrier = threading.Barrier( 4 )

    def worker():
        barrier.wait()
        ProfilesDiagnosticCollector.record_line( _SAMPLE_SCOPE, _PROFILE_LINE )

    threads = [ threading.Thread( target=worker ) for _ in range( 4 ) ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert session.inventory.total_references() == 4
    assert session.inventory.unique_locations() == 1


def test_index_inventory_is_stable_under_parallel_record():
    """Snapshot the index while other threads keep recording (``--parallel`` compiles)."""
    from cuppa.methods.cxx_profiles_report import CollateCxxProfilesIndexCallable

    env = {
        'cxx_profiles': True,
        'sconscript_file': './widget/sconscript',
    }
    CollateCxxProfilesIndexCallable()( env )
    session = ProfilesDiagnosticCollector._session
    other = _SAMPLE_SCOPE._replace( sconscript='./other/sconscript' )
    start = threading.Barrier( 5 )
    errors = []

    def recorder( scope ):
        try:
            start.wait()
            for _ in range( 40 ):
                ProfilesDiagnosticCollector.record_line( scope, _PROFILE_LINE )
        except Exception as exc:  # pylint: disable=broad-except
            errors.append( exc )

    def indexer():
        try:
            start.wait()
            for _ in range( 40 ):
                filtered, metadata = session.index_inventory()
                assert metadata[ 'omitted_scope_count' ] in ( 0, 1 )
                assert filtered.unique_locations() <= 1
        except Exception as exc:  # pylint: disable=broad-except
            errors.append( exc )

    threads = [
        threading.Thread( target=recorder, args=( _SAMPLE_SCOPE, ) ),
        threading.Thread( target=recorder, args=( _SAMPLE_SCOPE, ) ),
        threading.Thread( target=recorder, args=( other, ) ),
        threading.Thread( target=recorder, args=( other, ) ),
        threading.Thread( target=indexer ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    filtered, metadata = session.index_inventory()
    assert metadata[ 'omitted_scope_count' ] == 1
    assert filtered.locations()[ 0 ].scope.sconscript == './widget/sconscript'


def test_collector_progress_tracks_variant_completion():
    session = ProfilesDiagnosticCollector.activate()
    variant = _SAMPLE_SCOPE.variant_dir

    session.on_progress( 'started', './widget/sconscript', variant, None, None, None )
    assert variant in session._variant_completion.incomplete_variants()

    session.on_progress( 'finished', './widget/sconscript', variant, None, None, None )
    assert variant not in session._variant_completion.incomplete_variants()


def test_flush_pending_writes_once_when_not_emitted( monkeypatch, tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report': True,
        'artefacts_root': '_artefacts',
    }
    session = ProfilesDiagnosticCollector.activate( report_env=env )
    ProfilesDiagnosticCollector.record_line( _SAMPLE_SCOPE, _PROFILE_LINE )

    writes = []

    def fake_write( inventory, write_env, **kwargs ):
        writes.append( ( inventory.total_references(), write_env, kwargs ) )
        return {
            'model': {},
            'session_paths': [ 'index.html' ],
            'scope_paths': [],
        }

    monkeypatch.setattr(
        'cuppa.cpp.profiles_report.report_html.write_profiles_reports',
        fake_write,
    )
    monkeypatch.setattr(
        'cuppa.reports.manifest.append_cxx_profiles_entry',
        lambda *args, **kwargs: None,
    )

    assert session.flush_pending( env, fallback_flush=True ) is True
    assert session.flush_pending( env, fallback_flush=True ) is False
    assert len( writes ) == 1
    assert writes[ 0 ][ 2 ].get( 'incomplete_scopes' ) is not None or writes[ 0 ][ 1 ] == env


def test_diagnostic_collector_flush_pending_uses_report_env( monkeypatch, tmp_path ):
    env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report': True,
    }
    ProfilesDiagnosticCollector.activate( report_env=env )
    ProfilesDiagnosticCollector.record_line( _SAMPLE_SCOPE, _PROFILE_LINE )

    calls = []

    def fake_flush( write_env, fallback_flush=False ):
        calls.append( ( write_env, fallback_flush ) )
        return True

    monkeypatch.setattr(
        ProfilesDiagnosticCollector._session,
        'flush_pending',
        fake_flush,
    )

    assert ProfilesDiagnosticCollector.flush_pending() is True
    assert calls == [ ( env, True ) ]


def test_sconstruct_end_uses_report_env_for_session_write( monkeypatch, tmp_path ):
    report_env = {
        'sconstruct_dir': str( tmp_path ),
        'cxx_profiles_report': True,
        'reports_link_style': 'github',
        'artefacts_root': '_artefacts',
    }
    progress_env = { 'sconstruct_dir': str( tmp_path ) }
    session = ProfilesDiagnosticCollector.activate( report_env=report_env )
    ProfilesDiagnosticCollector.record_line( _SAMPLE_SCOPE, _PROFILE_LINE )

    writes = []

    def fake_write( inventory, write_env, **kwargs ):
        writes.append( write_env )
        return {
            'model': {},
            'session_paths': [ 'index.html' ],
            'scope_paths': [],
        }

    monkeypatch.setattr(
        'cuppa.cpp.profiles_report.report_html.write_profiles_reports',
        fake_write,
    )
    monkeypatch.setattr(
        'cuppa.reports.manifest.append_cxx_profiles_entry',
        lambda *args, **kwargs: None,
    )

    session.on_progress( 'sconstruct_end', None, None, progress_env, None, None )

    assert len( writes ) == 1
    assert writes[ 0 ] is report_env
    assert writes[ 0 ][ 'reports_link_style' ] == 'github'


def test_inventory_process_exit_status_after_non_profile_tally():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()
    ProfilesDiagnosticCollector.record_non_profile_error()
    assert ProfilesDiagnosticCollector.inventory_process_exit_status() == 1


def test_inventory_process_exit_status_none_when_no_non_profile_errors():
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()
    assert ProfilesDiagnosticCollector.inventory_process_exit_status() is None


def test_finalize_inventory_session_exits_after_non_profile_tally( monkeypatch ):
    NotifyProgress.set_inventory_report_mode( True )
    ProfilesDiagnosticCollector.activate()
    ProfilesDiagnosticCollector.record_non_profile_error()
    exits = []
    monkeypatch.setattr(
        'SCons.Script.Exit',
        lambda status: exits.append( status ),
    )
    monkeypatch.setattr(
        ProfilesDiagnosticCollector,
        'flush_pending',
        classmethod( lambda cls: False ),
    )
    ProfilesDiagnosticCollector.finalize_inventory_session()
    assert exits == [ 1 ]


def test_cxx_profiles_report_requires_profiles_active():
    from cuppa.methods.cxx_profiles_report import CollateCxxProfilesIndexMethod
    import SCons.Errors

    class FakeEnv(dict):
        def __init__( self, options ):
            super().__init__()
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

    env = FakeEnv( { 'cxx_profiles_report': True } )
    with pytest.raises( SCons.Errors.StopError ):
        CollateCxxProfilesIndexMethod.get_options( env )

    env = FakeEnv( { 'cxx_profiles_report': True } )
    env['cxx_profiles'] = True
    CollateCxxProfilesIndexMethod.get_options( env )
    assert env['cxx_profiles_report'] is True
    assert ProfilesDiagnosticCollector.active() is not None


def test_collector_registers_spawn_processor_rebind_hook():
    ProfilesDiagnosticCollector.activate()
    assert ProfilesDiagnosticCollector._rebind_spawn_processor in NotifyProgress._sconscript_env_hooks


def test_compile_wrapper_accepts_scons_env_first_argument():
    ProfilesDiagnosticCollector.activate()
    session = ProfilesDiagnosticCollector.active()
    recorded = []

    class FakeSource(object):
        path = '/tmp/widget.cpp'

    class FakeEnv(dict):
        sconscript_file = './widget/sconscript'
        build_dir = '_build/widget/clang24_profiles/dbg/x86_64/cxx2c/working'
        toolchain = _FakeToolchain()

        def get( self, key, default=None ):
            return super().get( key, default )

        def AddMethod( self, method, name ):
            def bound( *args, **kwargs ):
                return method( self, *args, **kwargs )
            setattr( self, name, bound )

    def original_compile( source, **kwargs ):
        recorded.append( ( 'compile', source ) )
        return [ 'object-node' ]

    env = FakeEnv( { 'cxx_profiles_report': True } )
    env.Compile = original_compile
    ProfilesDiagnosticCollector._wrap_compile_method( env, 'Compile' )
    result = env.Compile( FakeSource() )
    assert result == [ 'object-node' ]
    assert '/tmp/widget.cpp' in session.translation_units()


def test_spawn_processor_hook_skips_raw_output(monkeypatch):
    ProfilesDiagnosticCollector.activate()
    calls = []

    class FakeProcessor(object):
        @classmethod
        def install(cls, env):
            calls.append(env)

    monkeypatch.setattr('cuppa.output_processor.Processor', FakeProcessor)

    class FakeEnv(dict):
        def get_option(self, name):
            return name == 'raw_output'

    ProfilesDiagnosticCollector._rebind_spawn_processor(FakeEnv())
    assert calls == []

    class NormalEnv(dict):
        def get_option(self, name):
            return False

    env = NormalEnv()
    ProfilesDiagnosticCollector._rebind_spawn_processor(env)
    assert calls == [env]


def test_cxx_profiles_report_disabled_does_not_activate():
    from cuppa.methods.cxx_profiles_report import CollateCxxProfilesIndexMethod

    class FakeEnv(dict):
        def get_option( self, name ):
            return None

    env = FakeEnv()
    CollateCxxProfilesIndexMethod.get_options( env )
    assert env['cxx_profiles_report'] is False
    assert ProfilesDiagnosticCollector.active() is None
