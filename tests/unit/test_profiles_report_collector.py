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
    yield
    ProfilesDiagnosticCollector.reset()


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


def test_collector_progress_tracks_variant_completion():
    session = ProfilesDiagnosticCollector.activate()
    variant = _SAMPLE_SCOPE.variant_dir

    session.on_progress( 'started', './widget/sconscript', variant, None, None, None )
    assert variant in session._variant_completion.incomplete_variants()

    session.on_progress( 'finished', './widget/sconscript', variant, None, None, None )
    assert variant not in session._variant_completion.incomplete_variants()


def test_cxx_profiles_report_requires_profiles_active():
    from cuppa.methods.cxx_profiles_report import CxxProfilesReportMethod
    import SCons.Errors

    class FakeEnv(dict):
        def __init__( self, options ):
            super().__init__()
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

    env = FakeEnv( { 'cxx_profiles_report': True } )
    with pytest.raises( SCons.Errors.StopError ):
        CxxProfilesReportMethod.get_options( env )

    env = FakeEnv( { 'cxx_profiles_report': True } )
    env['cxx_profiles'] = True
    CxxProfilesReportMethod.get_options( env )
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
    from cuppa.methods.cxx_profiles_report import CxxProfilesReportMethod

    class FakeEnv(dict):
        def get_option( self, name ):
            return None

    env = FakeEnv()
    CxxProfilesReportMethod.get_options( env )
    assert env['cxx_profiles_report'] is False
    assert ProfilesDiagnosticCollector.active() is None
