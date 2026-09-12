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

    def Command( self, target, source, action ):
        self.commands.append( {
                'target': target,
                'source': source,
                'action': action,
        } )
        return [ 'node:{}'.format( target ) ]

    def Clean( self, target, files ):
        self.cleans.append( ( target, files ) )


def test_cmake_build_jobs_default_omits_without_parallel():
    assert cmake.cmake_build_jobs( _env() ) is None
    assert cmake.cmake_build_jobs( _env( parallel=True, job_count=1 ) ) is None


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
