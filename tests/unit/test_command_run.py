#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.utility.command import _resolve_executable


pytestmark = pytest.mark.unit


def test_resolve_executable_absolute_unchanged(tmp_path):
    abs_tool = str(tmp_path / "tool")
    (tmp_path / "tool").write_text("", encoding="utf-8")
    assert _resolve_executable([abs_tool, "--flag"], str(tmp_path)) == [abs_tool, "--flag"]


def test_resolve_executable_basename_under_working_dir(tmp_path):
    tool = tmp_path / "tool"
    tool.write_text("", encoding="utf-8")
    tool.chmod(0o755)
    resolved = _resolve_executable(["tool", "--self-check"], str(tmp_path))
    assert resolved[0] == str(tool)
    assert resolved[1:] == ["--self-check"]


def test_resolve_executable_dot_slash(tmp_path):
    tool = tmp_path / "tool"
    tool.write_text("", encoding="utf-8")
    resolved = _resolve_executable(["./tool"], str(tmp_path))
    assert os.path.normpath(resolved[0]) == os.path.normpath(str(tool))


def test_resolve_executable_adds_exe_when_present(tmp_path):
    tool = tmp_path / "tool.exe"
    tool.write_text("", encoding="utf-8")
    resolved = _resolve_executable(["tool"], str(tmp_path))
    assert resolved[0] == str(tool)
