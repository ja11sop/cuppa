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


def _clang(major, minor=0, name=None, cxx_path=None):
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
    toolchain._cxx_path = cxx_path
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
        (8, ["-flto", "-ffat-lto-objects"]),
        (16, ["-flto", "-ffat-lto-objects"]),
        (17, ["-flto=auto", "-ffat-lto-objects"]),
        (21, ["-flto=auto", "-ffat-lto-objects"]),
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
    assert "-std=c++2c" in toolchain.values["debug_cxx_flags"]
    # GCC 11+: concepts/coroutines are in the dialect — no redundant -f* gates.
    assert "-fconcepts" not in toolchain.values["debug_cxx_flags"]
    assert "-fcoroutines" not in toolchain.values["debug_cxx_flags"]


def test_gcc_feature_flags_only_when_dialect_lacks_them():
    """Match __default_dialect_flags policy: gate only where -std= is not enough."""
    assert _gcc(9)._Gcc__default_dialect_flags() == [ "-std=c++2a", "-fconcepts" ]
    assert _gcc(10)._Gcc__default_dialect_flags() == [ "-std=c++2a", "-fcoroutines" ]
    assert _gcc(11)._Gcc__default_dialect_flags() == [ "-std=c++2b" ]
    assert _gcc(15)._Gcc__default_dialect_flags() == [ "-std=c++2c" ]


def test_clang_lto_is_release_only():
    toolchain = _clang(18, name="clang18")
    with patch("cuppa.build_platform.name", return_value="Linux"):
        with patch.object(toolchain, "_resolve_versioned_tool", return_value=None):
            toolchain._initialise_toolchain(toolchain._reported_version, None)

    assert "-flto=auto" not in toolchain.values["debug_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["coverage_flags"]
    assert "-flto=auto" in toolchain.values["release_cxx_flags"]
    assert "-ffat-lto-objects" in toolchain.values["release_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["debug_link_cxx_flags"]
    assert "-flto=auto" not in toolchain.values["coverage_link_flags"]
    assert "-flto=auto" in toolchain.values["release_link_cxx_flags"]
    assert "-fuse-ld=lld" not in toolchain.values["release_link_cxx_flags"]
    assert "-std=c++2c" in toolchain.values["debug_cxx_flags"]


def test_clang_release_link_prefers_lld_when_available():
    toolchain = _clang(21, name="clang21")

    def _resolve(name):
        if name in ("ld.lld", "lld"):
            return "/usr/bin/ld.lld-21"
        return None

    with patch("cuppa.build_platform.name", return_value="Linux"):
        with patch.object(toolchain, "_resolve_versioned_tool", side_effect=_resolve):
            toolchain._initialise_toolchain(toolchain._reported_version, None)

    assert "-fuse-ld=lld" in toolchain.values["release_link_cxx_flags"]
    assert "-fuse-ld=lld" not in toolchain.values["debug_link_cxx_flags"]


def test_clang_resolve_versioned_tool_prefers_major_suffix(tmp_path):
    llvm_ar = tmp_path / "llvm-ar-21"
    llvm_ar.write_text("", encoding="utf-8")
    llvm_ar.chmod(0o755)
    toolchain = _clang(21, cxx_path=str(tmp_path))
    assert toolchain._resolve_versioned_tool("llvm-ar") == str(llvm_ar)


def test_clang_resolve_versioned_tool_joins_where_is_directory(tmp_path):
    """where_is() returns a directory; AR must be the tool path, not the dir."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    llvm_ar = bindir / "llvm-ar"
    llvm_ar.write_text("", encoding="utf-8")
    llvm_ar.chmod(0o755)
    toolchain = _clang(24, name="clang24_profiles_x", cxx_path=str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    with patch("cuppa.build_platform.where_is", return_value=str(bindir)):
        assert toolchain._resolve_versioned_tool("llvm-ar") == str(llvm_ar)


def test_gcc_dialect_flags_no_longer_embed_lto():
    assert "-flto" not in _gcc(10)._Gcc__default_dialect_flags()
    assert "-flto=auto" not in _gcc(14)._Gcc__default_dialect_flags()
