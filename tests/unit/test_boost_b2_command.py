#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.dependencies.boost.b2 import b2_command


class _Toolchain(object):
    def __init__( self, family, stdlib_flag=None, abi_flag=None, cxx_version="22", target_store="desktop" ):
        self._family = family
        self._stdlib_flag = stdlib_flag
        self._abi_flag = abi_flag
        self._cxx_version = cxx_version
        self._target_store = target_store

    def family( self ):
        return self._family

    def abi_flag( self, env ):
        return self._abi_flag

    def stdlib_flag( self, env ):
        return self._stdlib_flag

    def cxx_version( self ):
        return self._cxx_version

    def toolset_name( self ):
        return "clang" if self._family == "clang" else self._family

    def short_version( self ):
        return self._cxx_version

    def toolset_tag( self ):
        return "clang" if self._family == "clang" else self._family

    def target_store( self ):
        return self._target_store

    def name( self ):
        return "clang221"


def _patch_b2_helpers( monkeypatch, family ):
    monkeypatch.setattr(
        "cuppa.dependencies.boost.b2.toolset_from_toolchain",
        lambda toolchain: "clang-22" if family == "clang" else family,
    )
    monkeypatch.setattr(
        "cuppa.dependencies.boost.b2.directory_from_abi_flag",
        lambda abi: "c++2c",
    )
    monkeypatch.setattr(
        "cuppa.dependencies.boost.b2.b2_as_command",
        lambda version, location: "./b2",
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "family,target_arch,expect_address,expect_arch",
    [
        ( "clang", "x86_64", "address-model=64", "architecture=x86" ),
        ( "clang", "amd64", "address-model=64", "architecture=x86" ),
        ( "gcc", "x86_64", "address-model=64", "architecture=x86" ),
        ( "gcc", "i686", "address-model=32", "architecture=x86" ),
        ( "clang", "arm64", "address-model=64", "architecture=arm" ),
        ( "cl", "amd64", "address-model=64", "architecture=x86" ),
        ( "cl", "arm64", "address-model=64", "architecture=arm" ),
    ],
)
def test_b2_command_passes_address_model_for_all_toolchains(
    family, target_arch, expect_address, expect_arch, monkeypatch
):
    _patch_b2_helpers( monkeypatch, family )

    env = {}
    toolchain = _Toolchain( family, stdlib_flag="-stdlib=libstdc++" if family == "clang" else None )
    args = b2_command(
        env,
        1.91,
        "/tmp/boost",
        toolchain,
        [ "context" ],
        "release",
        target_arch,
        "static",
        "stage",
        False,
        False,
        1,
        False,
        [],
    )
    assert expect_address in args
    assert expect_arch in args


@pytest.mark.unit
def test_b2_command_keeps_cxxflags_and_defines_as_single_argv_elements( monkeypatch ):
    """Regression: quote-escaping before shlex.split used to split cxxflags on spaces
    and embed literal quotes into define= values, breaking the clang compile line."""
    _patch_b2_helpers( monkeypatch, "clang" )

    toolchain = _Toolchain(
        "clang",
        abi_flag="-std=c++2c",
        stdlib_flag="-stdlib=libstdc++",
    )
    args = b2_command(
        {},
        1.91,
        "/tmp/boost",
        toolchain,
        [ "regex" ],
        "release",
        "x86_64",
        "static",
        "stage",
        True,
        False,
        1,
        False,
        [ "BOOST_PARAMETER_MAX_ARITY=20", "BOOST_BIND_GLOBAL_PLACEHOLDERS" ],
    )

    cxxflags = [ a for a in args if a.startswith( "cxxflags=" ) ]
    assert cxxflags == [ "cxxflags=-std=c++2c -stdlib=libstdc++" ]

    defines = [ a for a in args if a.startswith( "define=" ) ]
    assert "define=BOOST_PARAMETER_MAX_ARITY=20" in defines
    assert "define=BOOST_BIND_GLOBAL_PLACEHOLDERS" in defines
    assert not any( '"' in a for a in args )
    assert "-d+2" in args
