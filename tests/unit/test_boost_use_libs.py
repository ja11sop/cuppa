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
        self.staticlibs = None
        self.depends = None
        self.requested_libs = None

    def BoostStaticLibs( self, libs ):
        self.requested_libs = list( libs )
        return [ 'libboost_filesystem.a', 'libboost_system.a' ]

    def AppendUnique( self, **kwargs ):
        self.staticlibs = kwargs.get( 'STATICLIBS' )

    def Depends( self, nodes, dependencies ):
        self.depends = ( nodes, dependencies )


def test_boost_use_libs_appends_staticlibs_via_boost_static_libs():
    boost = Boost.__new__( Boost )
    env = _FakeEnv()
    boost._env = env

    result = boost.use_libs( [ 'filesystem', 'system' ] )

    assert env.requested_libs == [ 'filesystem', 'system' ]
    assert env.staticlibs == [ 'libboost_filesystem.a', 'libboost_system.a' ]
    assert result == env.staticlibs
    assert env.depends is None


def test_boost_use_libs_honours_depends_on():
    boost = Boost.__new__( Boost )
    env = _FakeEnv()
    boost._env = env

    boost.use_libs( 'filesystem', depends_on=[ 'header_gen' ] )

    assert env.requested_libs == [ 'filesystem' ]
    assert env.depends[0] == [ 'libboost_filesystem.a', 'libboost_system.a' ]
    assert env.depends[1] == [ 'header_gen' ]
