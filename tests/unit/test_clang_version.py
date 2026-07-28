#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from unittest.mock import MagicMock, patch

import pytest

from cuppa.toolchains.clang import Clang
from tests.helpers.toolchains import is_apple_clang_version_text


APPLE_CLANG_VERSION = """\
Apple clang version 21.0.0 (clang-2100.1.1.101)
Target: arm64-apple-darwin25.4.0
Thread model: posix
InstalledDir: /Applications/Xcode_26.5.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin
"""

LLVM_CLANG_VERSION = """\
clang version 18.1.8
Target: x86_64-unknown-linux-gnu
Thread model: posix
InstalledDir: /usr/bin
"""

DEBIAN_CLANG_VERSION = """\
Debian clang version 21.1.8
Target: x86_64-pc-linux-gnu
Thread model: posix
InstalledDir: /usr/lib/llvm-21/bin
"""


@pytest.mark.unit
def test_is_apple_clang_version_text():
    assert is_apple_clang_version_text(APPLE_CLANG_VERSION)
    assert not is_apple_clang_version_text(LLVM_CLANG_VERSION)
    assert not is_apple_clang_version_text(DEBIAN_CLANG_VERSION)


@pytest.mark.unit
@patch("cuppa.toolchains.clang.command_available", return_value=True)
@patch("cuppa.toolchains.clang.Popen")
def test_apple_clang_version_from_command_sets_apple_flag(mock_popen, _available):
    proc = MagicMock()
    proc.communicate.return_value = (APPLE_CLANG_VERSION.encode("utf-8"), b"")
    mock_popen.return_value = proc

    reported = Clang.version_from_command("clang++")
    assert reported is not None
    assert reported["apple"] is True
    assert reported["major"] == 21
    assert reported["minor"] == 0


@pytest.mark.unit
@patch("cuppa.toolchains.clang.command_available", return_value=True)
@patch("cuppa.toolchains.clang.Popen")
def test_llvm_clang_version_from_command_not_apple(mock_popen, _available):
    proc = MagicMock()
    proc.communicate.return_value = (LLVM_CLANG_VERSION.encode("utf-8"), b"")
    mock_popen.return_value = proc

    reported = Clang.version_from_command("clang++")
    assert reported is not None
    assert reported["apple"] is False
    assert reported["major"] == 18
    assert reported["minor"] == 1


@pytest.mark.unit
def test_resolve_driver_prefers_absolute_path(tmp_path):
    toolchain = Clang.__new__(Clang)
    driver = tmp_path / "clang++"
    driver.write_text("")
    toolchain._cxx_path = str(tmp_path)
    assert toolchain._resolve_driver("clang++") == str(driver)
    assert toolchain._resolve_driver("missing-clang++") == "missing-clang++"


@pytest.mark.unit
def test_apple_clang_does_not_support_modules():
    toolchain = Clang.__new__(Clang)
    toolchain._reported_version = {
        "toolchain": "clang",
        "name": "clang210",
        "major": 21,
        "minor": 0,
        "version": "21.0",
        "short_version": "210",
        "apple": True,
    }
    with patch("cuppa.build_platform.name", return_value="Darwin"):
        assert toolchain.supports_modules(None) is False
        assert toolchain.supports_import_std(None) is False
