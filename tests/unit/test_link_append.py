#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for toolchain-opt-in link append helpers."""

import pytest

from cuppa.toolchains.link_append import (
        append_libpath,
        append_shared_libs,
        append_static_libs,
)


pytestmark = pytest.mark.unit


class _FakeEnv( dict ):

    def AppendUnique( self, **kwargs ):
        for key, value in kwargs.items():
            current = list( self.get( key ) or [] )
            for item in value if isinstance( value, ( list, tuple ) ) else [ value ]:
                if item not in current and str( item ) not in { str( x ) for x in current }:
                    current.append( item )
            self[key] = current

    def Append( self, **kwargs ):
        for key, value in kwargs.items():
            current = list( self.get( key ) or [] )
            items = value if isinstance( value, ( list, tuple ) ) else [ value ]
            current.extend( items )
            self[key] = current


class _GccLike( object ):

    def append_static_libs( self, env, libs ):
        env.Append( STATICLIBS = libs )


def test_append_static_libs_defaults_to_unique_without_toolchain_hook():
    env = _FakeEnv( STATICLIBS = [ "a" ] )
    append_static_libs( env, [ "a", "b" ] )
    assert env["STATICLIBS"] == [ "a", "b" ]


def test_append_static_libs_uses_toolchain_append_allowing_repeats():
    env = _FakeEnv( STATICLIBS = [ "a" ], toolchain = _GccLike() )
    append_static_libs( env, [ "a", "b" ] )
    assert env["STATICLIBS"] == [ "a", "a", "b" ]


def test_append_shared_and_libpath_default_unique():
    env = _FakeEnv( SHAREDLIBS = [ "curl" ], LIBPATH = [ "/a" ] )
    append_shared_libs( env, [ "curl", "z" ] )
    append_libpath( env, [ "/a", "/b" ] )
    assert env["SHAREDLIBS"] == [ "curl", "z" ]
    assert env["LIBPATH"] == [ "/a", "/b" ]


def test_gcc_and_clang_expose_append_static_libs():
    from cuppa.toolchains.gcc import Gcc
    from cuppa.toolchains.clang import Clang
    assert callable( getattr( Gcc, "append_static_libs", None ) )
    assert callable( getattr( Clang, "append_static_libs", None ) )
