#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import shlex

import pytest

import cuppa.progress
from cuppa.buildsys import cmake
from cuppa.methods.cmake import (
        CMakeBuildMethod,
        CMakeConfigureMethod,
        CMakeInstallMethod,
)
from cuppa.methods.acquire import RemoveEmptyDirsMethod


pytestmark = pytest.mark.unit


@pytest.fixture
def silence_progress( monkeypatch ):
    monkeypatch.setattr(
            cuppa.progress.NotifyProgress,
            'add',
            classmethod( lambda cls, env, target: None ),
    )


class _FakeToolchain(object):
    def binary( self ):
        return '/opt/gcc/bin/g++'


class _FakeVariant(object):
    def __init__( self, name ):
        self._name = name

    def name( self ):
        return self._name


def _env( variant='dbg', parallel=False, job_count=1, stdcpp=None ):
    return {
            'toolchain': _FakeToolchain(),
            'variant': _FakeVariant( variant ),
            'stdcpp': stdcpp,
            'parallel': parallel,
            'job_count': job_count,
            'CC': '/opt/gcc/bin/gcc',
    }


class _RecordingEnv(dict):
    """Minimal env that records ``Command`` / ``Clean`` and accepts NotifyProgress.add."""

    def __init__( self, *args, **kwargs ):
        dict.__init__( self, *args, **kwargs )
        self.commands = []
        self.cleans = []
        self._options = {}

    def get_option( self, name, default=None ):
        return self._options.get( name, default )

    def Command( self, target, source, action ):
        self.commands.append( {
                'target': target,
                'source': source,
                'action': action,
        } )
        return [ 'node:{}'.format( target ) ]

    def Clean( self, target, files ):
        self.cleans.append( ( target, files ) )


def test_cmake_build_jobs_default_is_one_without_parallel():
    assert cmake.cmake_build_jobs( _env() ) == 1
    assert cmake.cmake_build_jobs( _env( parallel=True, job_count=1 ) ) == 1


def test_cmake_build_jobs_honours_parallel():
    assert cmake.cmake_build_jobs( _env( parallel=True, job_count=8 ) ) == 8


def test_cmake_build_jobs_explicit_and_omit():
    env = _env( parallel=True, job_count=8 )
    assert cmake.cmake_build_jobs( env, jobs=4 ) == 4
    assert cmake.cmake_build_jobs( env, jobs=False ) is None
    assert cmake.cmake_build_jobs( env, jobs=0 ) is None


def test_cmake_build_args_and_command():
    assert cmake.cmake_build_args( '_build/rel', jobs=4 ) == [
            '--build', '_build/rel',
            '--parallel', '4',
    ]
    assert cmake.cmake_build_args( '_build/rel', target='install' ) == [
            '--build', '_build/rel',
            '--target', 'install',
    ]
    command = cmake.cmake_build_command( 'out', jobs=2, target='install' )
    assert shlex.split( command ) == [
            'cmake', '--build', 'out', '--target', 'install', '--parallel', '2',
    ]


def test_cmake_build_args_never_emits_bare_parallel():
    """Bare --parallel lets Ninja use cpu_count(), not Cuppa's restricted job_count."""
    for jobs in ( 1, 14 ):
        tokens = cmake.cmake_build_args( '_build/x', jobs=jobs )
        assert '--parallel' in tokens
        assert tokens[ tokens.index( '--parallel' ) + 1 ] == str( jobs )
    assert cmake.cmake_build_args( '_build/x', jobs=None ) == [ '--build', '_build/x' ]


def test_cmake_build_jobs_parallel_matches_affinity_sized_job_count():
    # Construct sets job_count from effective_cpu_count() after restrict_cpus
    # (e.g. 14 on a 16-core host). CMake must get that same integer.
    assert cmake.cmake_build_jobs( _env( parallel=True, job_count=14 ) ) == 14
    tokens = cmake.cmake_build_args(
            '_build/x',
            jobs=cmake.cmake_build_jobs( _env( parallel=True, job_count=14 ) ),
    )
    assert tokens == [ '--build', '_build/x', '--parallel', '14' ]


def test_cmake_configure_method_wires_command( silence_progress ):
    env = _RecordingEnv( _env( 'rel' ) )
    nodes = CMakeConfigureMethod()(
            env,
            'src',
            working_dir='/tmp/src',
            build_dir='_build/gcc_rel',
            generator='Ninja',
            extra_defines={ 'WIDGET_BUILD_TESTS': False },
    )
    assert nodes == [ 'node:cmake.configure.complete' ]
    assert len( env.commands ) == 1
    recorded = env.commands[0]
    assert recorded['target'] == 'cmake.configure.complete'
    assert recorded['source'] == 'src'
    action = recorded['action']
    assert action._working_dir == '/tmp/src'
    tokens = shlex.split( action._command )
    assert tokens[0] == 'cmake'
    assert '-B' in tokens and '_build/gcc_rel' in tokens
    assert '-G' in tokens and 'Ninja' in tokens
    assert '-DCMAKE_BUILD_TYPE=Release' in tokens
    assert '-DWIDGET_BUILD_TESTS=OFF' in tokens
    assert env.cleans == [
            ( [ 'node:cmake.configure.complete' ], '/tmp/src/_build/gcc_rel' ),
    ]


def test_cmake_build_method_honours_parallel_jobs( silence_progress ):
    env = _RecordingEnv( _env( parallel=True, job_count=6 ) )
    CMakeBuildMethod()(
            env,
            'configure',
            build_dir='_build/x',
            working_dir='/tmp/src',
    )
    action = env.commands[0]['action']
    assert shlex.split( action._command ) == [
            'cmake', '--build', '_build/x', '--parallel', '6',
    ]


def test_cmake_build_method_defaults_to_parallel_one( silence_progress ):
    env = _RecordingEnv( _env() )
    CMakeBuildMethod()(
            env,
            'configure',
            build_dir='_build/x',
            working_dir='/tmp/src',
    )
    assert shlex.split( env.commands[0]['action']._command ) == [
            'cmake', '--build', '_build/x', '--parallel', '1',
    ]


def test_cmake_build_method_jobs_false_omits_parallel( silence_progress ):
    env = _RecordingEnv( _env( parallel=True, job_count=6 ) )
    CMakeBuildMethod()(
            env,
            'configure',
            build_dir='_build/x',
            working_dir='/tmp/src',
            jobs=False,
    )
    assert shlex.split( env.commands[0]['action']._command ) == [
            'cmake', '--build', '_build/x',
    ]


def test_cmake_install_method_default_omits_parallel( silence_progress ):
    env = _RecordingEnv( _env( parallel=True, job_count=6 ) )
    nodes = CMakeInstallMethod()(
            env,
            'built',
            build_dir='_build/x',
            working_dir='/tmp/src',
            target='/tmp/final/installed',
    )
    assert nodes == [ 'node:/tmp/final/installed' ]
    assert shlex.split( env.commands[0]['action']._command ) == [
            'cmake', '--build', '_build/x', '--target', 'install',
    ]


def test_remove_empty_dirs_method_registers_command( silence_progress, tmp_path ):
    env = _RecordingEnv( _env() )
    parent = tmp_path / 'third_party'
    parent.mkdir()
    nodes = RemoveEmptyDirsMethod()(
            env,
            'extracted',
            parent=str( parent ),
            gitmodules=True,
            target='clear.stamp',
    )
    assert nodes == [ 'node:clear.stamp' ]
    assert len( env.commands ) == 1
    assert env.commands[0]['target'] == 'clear.stamp'
    assert env.commands[0]['source'] == 'extracted'
    assert callable( env.commands[0]['action'] ) or hasattr(
            env.commands[0]['action'], '__call__'
    )


def test_cmake_methods_skip_when_amend_package_manifest( silence_progress ):
    env = _RecordingEnv( _env( 'rel' ) )
    env._options['amend-package-manifest'] = True
    nodes = CMakeConfigureMethod()(
            env,
            'src',
            working_dir='/tmp/src',
            build_dir='_build/gcc_rel',
    )
    assert nodes == [ 'node:cmake.configure.complete' ]
    assert env.commands[0]['source'] == []
    assert env.cleans == []

    env.commands.clear()
    CMakeBuildMethod()(
            env,
            'configure',
            build_dir='_build/x',
            working_dir='/tmp/src',
    )
    assert env.commands[0]['source'] == []

    env.commands.clear()
    CMakeInstallMethod()(
            env,
            'built',
            build_dir='_build/x',
            working_dir='/tmp/src',
    )
    assert env.commands[0]['source'] == []
