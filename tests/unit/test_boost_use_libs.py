#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for Boost.use_libs (parity with boost_package.use_libs)."""

import pytest

from cuppa.dependencies.build_with_boost import Boost


pytestmark = pytest.mark.unit


class _FakeEnv( object ):
    def __init__( self ):
        self.staticlibs = []
        self.depends = None
        self.requested_libs = None
        self.append_calls = 0
        self.append_unique_calls = 0

    def BoostStaticLibs( self, libs ):
        self.requested_libs = list( libs )
        return [ 'libboost_filesystem.a', 'libboost_system.a' ]

    def Append( self, **kwargs ):
        self.append_calls += 1
        self.staticlibs.extend( kwargs.get( 'STATICLIBS' ) or [] )

    def AppendUnique( self, **kwargs ):
        self.append_unique_calls += 1
        for item in kwargs.get( 'STATICLIBS' ) or []:
            if item not in self.staticlibs:
                self.staticlibs.append( item )

    def Depends( self, nodes, dependencies ):
        self.depends = ( nodes, dependencies )


def test_boost_use_libs_appends_staticlibs_via_boost_static_libs():
    boost = Boost.__new__( Boost )
    env = _FakeEnv()
    boost._env = env

    result = boost.use_libs( [ 'filesystem', 'system' ] )

    assert env.requested_libs == [ 'filesystem', 'system' ]
    assert env.staticlibs == [ 'libboost_filesystem.a', 'libboost_system.a' ]
    assert result == [ 'libboost_filesystem.a', 'libboost_system.a' ]
    assert env.append_calls == 1
    assert env.append_unique_calls == 0
    assert env.depends is None


def test_boost_use_libs_allows_repeated_archives_across_calls():
    """Second use_libs must Append again so dependents can follow later libs."""
    boost = Boost.__new__( Boost )
    env = _FakeEnv()
    boost._env = env

    boost.use_libs( [ 'filesystem', 'system' ] )
    boost.use_libs( [ 'filesystem', 'system' ] )

    assert env.staticlibs == [
        'libboost_filesystem.a', 'libboost_system.a',
        'libboost_filesystem.a', 'libboost_system.a',
    ]
    assert env.append_calls == 2
    assert env.append_unique_calls == 0


def test_boost_use_libs_honours_depends_on():
    boost = Boost.__new__( Boost )
    env = _FakeEnv()
    boost._env = env

    boost.use_libs( 'filesystem', depends_on=[ 'header_gen' ] )

    assert env.requested_libs == [ 'filesystem' ]
    assert env.depends[0] == [ 'libboost_filesystem.a', 'libboost_system.a' ]
    assert env.depends[1] == [ 'header_gen' ]
