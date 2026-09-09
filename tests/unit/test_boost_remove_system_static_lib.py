#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.dependencies.boost.boost_library_methods import remove_system_static_lib
from cuppa.packages import boost_package as boost_package_module

pytestmark = pytest.mark.unit


class _FakeEnv( dict ):
    def __init__( self ):
        super().__init__()
        self.boost_factory_called = False


def test_remove_system_static_lib_uses_explicit_version_without_boost_factory():
    env = _FakeEnv()

    def boost_factory( ignored ):
        env.boost_factory_called = True
        raise AssertionError( 'built-in boost factory must not run for package use_libs' )

    env[ 'dependencies' ] = { 'boost': boost_factory }
    libraries = [ 'filesystem', 'system', 'thread' ]

    result = remove_system_static_lib( env, list( libraries ), boost_version='1.92' )

    assert env.boost_factory_called is False
    assert result == [ 'filesystem', 'thread' ]


def test_remove_system_static_lib_keeps_system_below_1_89():
    env = _FakeEnv()

    def boost_factory( ignored ):
        env.boost_factory_called = True
        raise AssertionError( 'built-in boost factory must not run for package use_libs' )

    env[ 'dependencies' ] = { 'boost': boost_factory }

    result = remove_system_static_lib( env, [ 'filesystem', 'system' ], boost_version='1.88' )

    assert env.boost_factory_called is False
    assert result == [ 'filesystem', 'system' ]


def test_boost_package_use_libs_passes_package_version( monkeypatch ):
    calls = []

    def fake_remove( env, libraries, boost_version=None ):
        calls.append( boost_version )
        return list( libraries )

    monkeypatch.setattr(
        boost_package_module,
        'remove_system_static_lib',
        fake_remove,
    )
    monkeypatch.setattr(
        boost_package_module,
        'add_dependent_libraries',
        lambda version, linktype, libraries: libraries,
    )
    monkeypatch.setattr(
        boost_package_module,
        'static_library_name',
        lambda env, lib, toolchain, version, variant, static: 'libboost_{}.a'.format( lib ),
    )

    class FakePackage( object ):
        _env = {
            'toolchain': 'gcc153',
        }
        _version = '1.92'
        _variant = 'rel'

        def lib_dir( self ):
            return '/tmp/boost/lib'

    class FakeEnv( dict ):
        def __init__( self, **kwargs ):
            super().__init__( **kwargs )
            self.staticlibs = []
            self.append_calls = 0
            self.append_unique_calls = 0

        def File( self, path ):
            return path

        def Append( self, **kwargs ):
            self.append_calls += 1
            self.staticlibs.extend( kwargs.get( 'STATICLIBS' ) or [] )

        def AppendUnique( self, **kwargs ):
            self.append_unique_calls += 1
            for item in kwargs.get( 'STATICLIBS' ) or []:
                if item not in self.staticlibs:
                    self.staticlibs.append( item )

    package = FakePackage()
    package._env = FakeEnv( toolchain='gcc153' )

    boost_package_module.use_libs( package, [ 'system', 'thread' ] )

    assert calls == [ '1.92' ]
    assert package._env.append_calls == 1
    assert package._env.append_unique_calls == 0
    assert package._env.staticlibs == [
        '/tmp/boost/lib/libboost_system.a',
        '/tmp/boost/lib/libboost_thread.a',
    ]


def test_boost_package_use_libs_appends_repeated_dependents( monkeypatch ):
    """Later log expansion must re-Append filesystem/thread already linked earlier."""
    monkeypatch.setattr(
        boost_package_module,
        'remove_system_static_lib',
        lambda env, libraries, boost_version=None: list( libraries ),
    )
    monkeypatch.setattr(
        boost_package_module,
        'static_library_name',
        lambda env, lib, toolchain, version, variant, static: 'libboost_{}.a'.format( lib ),
    )

    class FakePackage( object ):
        _version = '1.92'
        _variant = 'rel'

        def lib_dir( self ):
            return '/tmp/boost/lib'

    class FakeEnv( dict ):
        def __init__( self, **kwargs ):
            super().__init__( **kwargs )
            self.staticlibs = []

        def File( self, path ):
            return path

        def Append( self, **kwargs ):
            self.staticlibs.extend( kwargs.get( 'STATICLIBS' ) or [] )

        def AppendUnique( self, **kwargs ):
            raise AssertionError( 'use_libs must Append, not AppendUnique' )

    package = FakePackage()
    package._env = FakeEnv( toolchain='gcc153' )

    boost_package_module.use_libs( package, [ 'filesystem', 'thread' ] )
    boost_package_module.use_libs(
        package,
        [ 'log_setup', 'log', 'program_options', 'unit_test_framework' ],
    )

    names = [ path.rsplit( '/', 1 )[-1] for path in package._env.staticlibs ]
    assert names.count( 'libboost_filesystem.a' ) >= 2
    assert names.count( 'libboost_thread.a' ) >= 2
    log_index = names.index( 'libboost_log.a' )
    assert 'libboost_filesystem.a' in names[ log_index + 1 : ]
    assert 'libboost_thread.a' in names[ log_index + 1 : ]
