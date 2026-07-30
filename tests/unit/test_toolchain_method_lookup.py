#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.methods.toolchain import ToolchainMethod


pytestmark = pytest.mark.unit


class _FakeToolchain(object):
    def __init__( self, registry_key, display_name=None ):
        self._registry_key = registry_key
        self._display_name = display_name if display_name is not None else registry_key

    def name( self ):
        return self._display_name


def test_toolchain_lookup_by_registry_key():
    clang = _FakeToolchain( 'clang', 'clang-libc++' )
    method = ToolchainMethod( { 'clang': clang, 'gcc': _FakeToolchain( 'gcc' ) } )
    assert method( None, 'clang' ) is clang
    assert method( None, 'gcc' ).name() == 'gcc'


def test_toolchain_lookup_by_abi_name():
    clang = _FakeToolchain( 'clang', 'clang-libc++' )
    method = ToolchainMethod( { 'clang': clang } )
    assert method( None, 'clang-libc++' ) is clang
    assert method( None, 'clang-libc++' ).name() == 'clang-libc++'


def test_toolchain_lookup_missing_returns_none():
    method = ToolchainMethod( { 'gcc': _FakeToolchain( 'gcc' ) } )
    assert method( None, 'clang' ) is None
    assert method( None, None ) is None
    assert method( None, '' ) is None
