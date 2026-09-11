#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.methods.toolchain import HasToolchainMethod, ToolchainMethod, lookup_toolchain
from cuppa.methods.using import HasDependencyMethod, UseMethod
from cuppa.methods.variant import VariantMethod


pytestmark = pytest.mark.unit


class _FakeToolchain(object):
    def __init__( self, registry_key, display_name=None ):
        self._registry_key = registry_key
        self._display_name = display_name if display_name is not None else registry_key

    def name( self ):
        return self._display_name


class _FakeVariant(object):
    def name( self ):
        return 'dbg'


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
    assert method( None, '' ) is None


def test_toolchain_zero_arg_returns_active():
    active = _FakeToolchain( 'gcc' )
    method = ToolchainMethod( { 'gcc': active } )
    env = { 'toolchain': active }
    assert method( env ) is active
    assert method( env, None ) is active


def test_toolchain_keyed_emits_deprecation( monkeypatch ):
    warnings = []
    monkeypatch.setattr(
            'cuppa.methods.toolchain.logger.warn',
            lambda message: warnings.append( message ),
    )
    clang = _FakeToolchain( 'clang', 'clang-libc++' )
    method = ToolchainMethod( { 'clang': clang } )
    assert method( {}, 'clang' ) is clang
    assert len( warnings ) == 1
    assert 'HasToolchain' in warnings[0]
    assert 'removed in cuppa 2.0' in warnings[0]


def test_has_toolchain():
    clang = _FakeToolchain( 'clang', 'clang-libc++' )
    method = HasToolchainMethod( { 'clang': clang } )
    assert method( None, 'clang' ) is True
    assert method( None, 'clang-libc++' ) is True
    assert method( None, 'gcc' ) is False
    assert method( None, '' ) is False


def test_lookup_toolchain_helper():
    clang = _FakeToolchain( 'clang', 'clang-libc++' )
    toolchains = { 'clang': clang }
    assert lookup_toolchain( toolchains, 'clang' ) is clang
    assert lookup_toolchain( toolchains, 'clang-libc++' ) is clang
    assert lookup_toolchain( toolchains, None ) is None


def test_variant_returns_active():
    variant = _FakeVariant()
    assert VariantMethod()( { 'variant': variant } ) is variant


def test_has_dependency():
    method = HasDependencyMethod( { 'boost': object(), 'widget': object() } )
    assert method( None, 'boost' ) is True
    assert method( None, 'missing' ) is False


def test_using_emits_deprecation_and_returns_factory( monkeypatch ):
    warnings = []
    monkeypatch.setattr(
            'cuppa.methods.using.logger.warn',
            lambda message: warnings.append( message ),
    )
    factory = object()
    method = UseMethod( { 'boost': factory } )
    assert method( None, 'boost' ) is factory
    assert method( None, 'missing' ) is None
    assert len( warnings ) == 2
    assert 'HasDependency' in warnings[0]
