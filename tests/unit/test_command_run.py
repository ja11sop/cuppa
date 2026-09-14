#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.utility.command import _resolve_executable
from cuppa.utility.command_failure import (
        line_failure_priority,
        select_failure_detail_lines,
)


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


def test_line_failure_priority_ranks_ninja_and_loader_high():
    assert line_failure_priority( "FAILED: [code=1] gens/foo.pb.cc" ) == 2
    assert line_failure_priority(
            "grpc_cpp_plugin: error while loading shared libraries: libx.so"
    ) == 2
    assert line_failure_priority( "ninja: build stopped: subcommand failed." ) == 2
    assert line_failure_priority( "foo.cc:12: error: ‘any_of’ is not a member" ) == 1
    assert line_failure_priority(
            "warning: ‘void absl::Mutex::Lock()’ is deprecated"
    ) == 0


def test_select_failure_detail_lines_prefers_failed_over_warnings():
    lines = [
            "[1/10] Building CXX object a.cc.o",
            "warning: deprecated MutexLock",
            "FAILED: [code=1] gens/reflection.pb.cc",
            "plugin: error while loading shared libraries: libgrpc_plugin_support.so",
            "--grpc_out: protoc-gen-grpc: Plugin failed with status code 127.",
            "warning: more noise",
            "ninja: build stopped: subcommand failed.",
    ]
    detail = select_failure_detail_lines( lines, limit=10 )
    assert detail[0].startswith( "FAILED:" )
    assert any( "loading shared libraries" in line for line in detail )
    assert any( "ninja: build stopped" in line for line in detail )
    assert not any( line.startswith( "warning:" ) for line in detail )


def test_select_failure_detail_lines_respects_limit_and_dedupes():
    lines = [ "FAILED: once", "error: a", "FAILED: once", "error: b", "error: c" ]
    detail = select_failure_detail_lines( lines, limit=3 )
    assert detail == [ "FAILED: once", "error: a", "error: b" ]
