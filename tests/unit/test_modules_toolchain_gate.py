#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from tests.helpers.toolchains import (
    MODULES_MIN_CLANG_MAJOR,
    MODULES_MIN_GCC_MAJOR,
    compiler_major_version,
    find_modules_capable_toolchain,
)


pytestmark = pytest.mark.unit


def test_compiler_major_version_parses_gcc(monkeypatch):
    def fake_check_output(cmd, **kwargs):
        return "g++ (Ubuntu 13.3.0-6ubuntu2) 13.3.0\nCopyright (C) 2023 Free Software Foundation, Inc.\n"

    monkeypatch.setattr("subprocess.check_output", fake_check_output)
    assert compiler_major_version("g++") == 13


def test_compiler_major_version_parses_gcc_14(monkeypatch):
    def fake_check_output(cmd, **kwargs):
        return "g++ (Ubuntu 14.2.0-4ubuntu2) 14.2.0\n"

    monkeypatch.setattr("subprocess.check_output", fake_check_output)
    assert compiler_major_version("g++") == 14
    assert compiler_major_version("g++") >= MODULES_MIN_GCC_MAJOR


def test_compiler_major_version_parses_clang(monkeypatch):
    def fake_check_output(cmd, **kwargs):
        return "Debian clang version 18.1.3 (1)\nTarget: x86_64-pc-linux-gnu\n"

    monkeypatch.setattr("subprocess.check_output", fake_check_output)
    assert compiler_major_version("clang++") == 18
    assert compiler_major_version("clang++") >= MODULES_MIN_CLANG_MAJOR


def test_find_modules_capable_prefers_default_gxx_when_new_enough(monkeypatch):
    import tests.helpers.toolchains as helpers

    monkeypatch.setattr(helpers.shutil, "which", lambda name: "/usr/bin/" + name if name == "g++" else None)
    monkeypatch.setattr(helpers, "compiler_major_version", lambda cmd: 15)
    monkeypatch.setattr(helpers, "_discover_versioned_drivers", lambda prefix: [(16, "g++-16")])
    alias, driver, reported = find_modules_capable_toolchain("gcc")
    assert alias == "gcc"
    assert driver == "g++"
    assert reported == 15


def test_find_modules_capable_probes_newest_when_default_too_old(monkeypatch, tmp_path):
    import tests.helpers.toolchains as helpers

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "g++-14").write_text("")
    (bin_dir / "g++-15").write_text("")
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(
        helpers.shutil,
        "which",
        lambda name: str(bin_dir / name) if (bin_dir / name).exists() or name == "g++" else None,
    )

    def major(cmd):
        if cmd.endswith("g++"):
            return 13
        if cmd.endswith("g++-15"):
            return 15
        if cmd.endswith("g++-14"):
            return 14
        return None

    # Default g++ exists but is too old; discover versioned drivers from PATH.
    monkeypatch.setattr(
        helpers.shutil,
        "which",
        lambda name: {
            "g++": "/usr/bin/g++",
            "g++-14": str(bin_dir / "g++-14"),
            "g++-15": str(bin_dir / "g++-15"),
        }.get(name),
    )
    monkeypatch.setattr(helpers, "compiler_major_version", major)
    alias, driver, reported = find_modules_capable_toolchain("gcc")
    assert alias == "gcc15"
    assert driver == "g++-15"
    assert reported == 15


def test_require_modules_capable_toolchain_fails_when_nothing_new_enough(monkeypatch):
    import tests.helpers.toolchains as helpers

    monkeypatch.setenv("CUPPA_TEST_TOOLCHAIN", "gcc")
    monkeypatch.setattr(helpers.shutil, "which", lambda name: "/usr/bin/g++" if name in ("g++", "gcc") else None)
    monkeypatch.setattr(helpers, "compiler_major_version", lambda cmd: 13)
    monkeypatch.setattr(helpers, "find_modules_capable_toolchain", lambda family: None)
    with pytest.raises(pytest.fail.Exception, match="require gcc 14\\+"):
        helpers.require_modules_capable_toolchain()


def test_require_modules_capable_toolchain_skips_msvc(monkeypatch):
    import tests.helpers.toolchains as helpers

    monkeypatch.setenv("CUPPA_TEST_TOOLCHAIN", "vc")
    with pytest.raises(pytest.skip.Exception, match="MSVC"):
        helpers.require_modules_capable_toolchain()
