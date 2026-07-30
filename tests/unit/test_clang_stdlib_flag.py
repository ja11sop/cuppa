#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.toolchains.clang import Clang


pytestmark = pytest.mark.unit


def _clang_with_stdlib(stdlib, name="clang21"):
    toolchain = Clang.__new__(Clang)
    toolchain._stdlib = stdlib
    toolchain._name = name
    return toolchain


def test_stdlib_flag_omitted_when_unset():
    """Unset clang-stdlib must not emit -stdlib=None into Boost b2 cxxflags."""
    assert _clang_with_stdlib(None).stdlib_flag(env=None) is None


def test_stdlib_flag_when_libcxx_selected():
    assert _clang_with_stdlib("libc++").stdlib_flag(env=None) == "-stdlib=libc++"


def test_stdlib_flag_when_libstdcxx_selected():
    assert _clang_with_stdlib("libstdc++").stdlib_flag(env=None) == "-stdlib=libstdc++"


def test_default_stdlib_is_libstdcxx_on_linux(monkeypatch):
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    assert Clang.default_stdlib() == "libstdc++"


def test_default_stdlib_unset_off_linux(monkeypatch):
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Darwin")
    assert Clang.default_stdlib() is None


def test_name_omits_linux_default_stdlib(monkeypatch):
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    tc = _clang_with_stdlib("libstdc++")
    assert tc.name() == "clang21"
    assert tc.package_name() == tc.name()


def test_name_tags_non_default_stdlib(monkeypatch):
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    tc = _clang_with_stdlib("libc++")
    assert tc.name() == "clang21-libc++"
    assert tc.package_name() == tc.name()


def test_package_name_equals_name(monkeypatch):
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    assert _clang_with_stdlib("libstdc++").package_name() == "clang21"
    assert _clang_with_stdlib("libc++").package_name() == "clang21-libc++"
