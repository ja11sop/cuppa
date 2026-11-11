#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for ``--deep-clean`` option helpers and b2 clean argv."""

from __future__ import annotations

import pytest
import SCons.Errors

from cuppa.core import deep_clean
from cuppa.dependencies.boost.b2 import b2_clean_command, b2_command
from cuppa.package_managers import package_cascade as cascade


pytestmark = pytest.mark.unit


class _Env( dict ):
    def __init__( self, options=None, **kwargs ):
        super().__init__( **kwargs )
        self._options = dict( options or {} )

    def get_option( self, name, default=None ):
        return self._options.get( name, default )


def test_deep_clean_enabled_requires_clean_and_flag():
    assert deep_clean.deep_clean_enabled(
            _Env( clean=True, deep_clean=True )
    )
    assert not deep_clean.deep_clean_enabled(
            _Env( clean=True, deep_clean=False )
    )
    assert not deep_clean.deep_clean_enabled(
            _Env( clean=False, deep_clean=True )
    )
    assert deep_clean.deep_clean_enabled(
            _Env( options={ 'clean': True, 'deep-clean': True } )
    )


def test_check_deep_clean_options_refuses_without_clean():
    with pytest.raises( SCons.Errors.StopError ) as caught:
        deep_clean.check_deep_clean_options(
                _Env( options={ 'deep-clean': True, 'clean': False } )
        )
    assert '--deep-clean' in str( caught.value )
    assert '-c' in str( caught.value )


def test_check_deep_clean_options_allows_with_clean():
    deep_clean.check_deep_clean_options(
            _Env( options={ 'deep-clean': True, 'clean': True } )
    )


def test_check_deep_clean_options_noop_without_flag():
    deep_clean.check_deep_clean_options( _Env( options={ 'clean': False } ) )


def test_b2_clean_command_inserts_clean_after_exe( monkeypatch ):
    class _Toolchain:
        def family( self ):
            return 'gcc'
        def abi_flag( self, env ):
            return '-std=c++17'
        def stdlib_flag( self, env ):
            return None
        def name( self ):
            return 'gcc15'
        def target_store( self ):
            return 'desktop'

    monkeypatch.setattr(
            'cuppa.dependencies.boost.b2.cuppa.build_platform.name',
            lambda: 'Linux',
    )
    monkeypatch.setattr(
            'cuppa.dependencies.boost.b2.toolset_from_toolchain',
            lambda toolchain: 'gcc',
    )
    args = b2_clean_command(
            {},
            1.86,
            '/home/user/deps/boost',
            _Toolchain(),
            [ 'filesystem', 'system' ],
            'release',
            'x86_64',
            'static',
            'build.c++17/gcc15/release/x86_64',
            False,
            False,
            4,
            True,
            [],
    )
    assert args[0].endswith( 'b2' ) or args[0] == './b2'
    assert args[1] == '--clean'
    assert '--clean-all' not in args
    assert 'toolset=gcc' in args
    assert 'variant=release' in args
    assert '--with-filesystem' in args
    build_args = b2_command(
            {},
            1.86,
            '/home/user/deps/boost',
            _Toolchain(),
            [ 'filesystem', 'system' ],
            'release',
            'x86_64',
            'static',
            'build.c++17/gcc15/release/x86_64',
            False,
            False,
            4,
            True,
            [],
    )
    assert '--clean' not in build_args


def test_tip_forward_args_keeps_deep_clean_with_clean():
    tip = [
            'scons',
            '-D',
            '-c',
            '--deep-clean',
            '--rel',
            '--toolchains=gcc15',
            '--publish-package',
            '--cascade',
            '--publisher-root=../../',
            '--cuppa-mode',
    ]
    forwarded = cascade.tip_forward_args( tip )
    assert '-c' in forwarded
    assert '--deep-clean' in forwarded
    assert '--cascade' not in forwarded
