#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from unittest.mock import patch

import pytest

from cuppa.toolchains.clang import Clang
from cuppa.toolchains.gcc import Gcc


pytestmark = pytest.mark.unit


def _gcc(major, minor=0):
    toolchain = Gcc.__new__(Gcc)
    toolchain._reported_version = {
        "major": major,
        "minor": minor,
        "name": "gcc{}{}".format(major, minor if minor else ""),
        "version": "{}.{}".format(major, minor),
        "short_version": str(major),
    }
    toolchain.values = {}
    return toolchain


def _clang(major, minor=0, name=None):
    toolchain = Clang.__new__(Clang)
    toolchain._reported_version = {
        "major": major,
        "minor": minor,
        "name": name or "clang{}".format(major),
        "version": "{}.{}".format(major, minor),
        "short_version": str(major),
    }
    toolchain._suppress_debug_for_auto = False
    toolchain._stdlib = None
    toolchain._gcov_format = None
    toolchain.values = {}
    return toolchain


@pytest.mark.parametrize(
    "major,expected",
    [
        (7, []),
        (8, ["-flto"]),
        (11, ["-flto"]),
        (12, ["-flto=auto"]),
        (15, ["-flto=auto"]),
    ],
)
def test_gcc_lto_flags_by_version(major, expected):
    assert _gcc(major)._Gcc__lto_flags() == expected


@pytest.mark.parametrize(
    "major,expected",
    [
        (7, []),
        (8, ["-flto"]),
        (16, ["-flto"]),
        (17, ["-flto=auto"]),
        (21, ["-flto=auto"]),
    ],
)
def test_clang_lto_flags_by_version(major, expected):
    assert _clang(major)._Clang__lto_flags() == expected


def test_gcc_lto_is_release_only():
    toolchain = _gcc(15)
    with patch("cuppa.build_platform.name", return_value="Linux"):
        toolchain._initialise_toolchain(toolchain._reported_version)

    assert "-flto=auto" not in toolchain.values["debug_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["coverage_cxx_flags"]
    assert "-flto=auto" in toolchain.values["release_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["debug_link_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["coverage_link_cxx_flags"]
    assert "-flto=auto" in toolchain.values["release_link_cxx_flags"]
    assert "-fconcepts" in toolchain.values["debug_cxx_flags"]
    assert "-std=c++2c" in toolchain.values["debug_cxx_flags"]


def test_clang_lto_is_release_only():
    toolchain = _clang(18, name="clang18")
    with patch("cuppa.build_platform.name", return_value="Linux"):
        toolchain._initialise_toolchain(toolchain._reported_version, None)

    assert "-flto=auto" not in toolchain.values["debug_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["coverage_flags"]
    assert "-flto=auto" in toolchain.values["release_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["debug_link_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["coverage_link_flags"]
    assert "-flto=auto" in toolchain.values["release_link_cxx_flags"]
    assert "-std=c++2c" in toolchain.values["debug_cxx_flags"]


def test_gcc_dialect_flags_no_longer_embed_lto():
    assert "-flto" not in _gcc(10)._Gcc__default_dialect_flags()
    assert "-flto=auto" not in _gcc(14)._Gcc__default_dialect_flags()
