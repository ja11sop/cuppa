#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

import cuppa.progress as progress
from cuppa.utility.command import _resolve_executable, run
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


def test_command_run_terse_streams_launch_and_muted_children( monkeypatch, capsys ):
    progress.reset_progress_ledger()
    progress.take_terse_launch()

    def fake_popen2( stdout_processor, stderr_processor, args_list, **kwargs ):
        assert kwargs.get( "suppress_output" ) is True
        stdout_processor( "[1/2] Building CXX object a.cpp.o" )
        stdout_processor( "[2/2] Linking CXX static library liba.a" )
        return 0

    monkeypatch.setattr(
            "cuppa.utility.command.IncrementalSubProcess.Popen2",
            fake_popen2,
    )
    env = {
            "terse_output": True,
            "variant": type( "V", (), { "name": lambda self: "dbg" } )(),
            "toolchain": type( "T", (), { "name": lambda self: "gcc16" } )(),
            "target_arch": "x86_64",
            "abi": "cxx2c",
            "sconscript_file": "./pkg/sconscript",
    }
    action = run(
            "cmake --build _build/x --parallel 1",
            working_dir="/tmp",
            terse_summary="-B _build/x --parallel 1",
            terse_action="cmake-build",
    )
    assert action( [ "cmake.build.complete" ], [], env ) == 0
    out = capsys.readouterr().out
    assert "delegate" in out
    assert "[launch] pkg · gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/x --parallel 1" in out
    assert "· start ·" not in out
    assert "→ [1/2] Building CXX object a.cpp.o" in out
    assert "→ [2/2] Linking CXX static library liba.a" in out
    assert "cmake --build _build/x --parallel 1\n" not in out
    emitted, command = progress.take_terse_launch()
    assert emitted
    assert command == "cmake --build _build/x --parallel 1"


def test_command_run_interrupt_skips_error_logging( monkeypatch, capsys ):
    """SIGINT from first Ctrl-C is drain, not ``cuppa: command: [error]``."""
    import signal

    progress.reset_progress_ledger()
    progress.reset_build_interrupted()

    def fake_popen2( stdout_processor, stderr_processor, args_list, **kwargs ):
        stdout_processor( "ninja: build stopped: interrupted by user." )
        return -signal.SIGINT

    monkeypatch.setattr(
            "cuppa.utility.command.IncrementalSubProcess.Popen2",
            fake_popen2,
    )
    env = {
            "terse_output": True,
            "variant": type( "V", (), { "name": lambda self: "dbg" } )(),
            "toolchain": type( "T", (), { "name": lambda self: "gcc16" } )(),
            "target_arch": "x86_64",
            "abi": "cxx2c",
            "sconscript_file": "./pkg/sconscript",
    }
    action = run(
            "cmake --build _build/x --parallel 14",
            working_dir="/tmp",
            terse_summary="-B _build/x --parallel 14",
            terse_action="cmake-build",
    )
    assert action( [ "cmake.build.complete" ], [], env ) == -signal.SIGINT
    out = capsys.readouterr().out
    assert "ninja: build stopped: interrupted by user." in out
    # No failure dump — interrupt banner owns the close.
    assert "terminated by signal" not in out
    assert "Failure detail" not in out
    assert "[error]" not in out


def test_command_run_terse_without_delegate_opts_skips_launch( monkeypatch, capsys ):
    progress.reset_progress_ledger()
    progress.take_terse_launch()
    seen = {}

    def fake_popen2( stdout_processor, stderr_processor, args_list, **kwargs ):
        seen["suppress_output"] = kwargs.get( "suppress_output" )
        stdout_processor( "copied" )
        return 0

    monkeypatch.setattr(
            "cuppa.utility.command.IncrementalSubProcess.Popen2",
            fake_popen2,
    )
    env = { "terse_output": True }
    action = run( "cp -f a.a b.a", working_dir="/tmp" )
    assert action( [ "b.a" ], [ "a.a" ], env ) == 0
    out = capsys.readouterr().out
    assert "[launch]" not in out
    assert "copied\n" in out
    assert seen.get( "suppress_output" ) is True
    assert progress.take_terse_launch() == ( False, None )


def test_select_failure_detail_lines_respects_limit_and_dedupes():
    lines = [ "FAILED: once", "error: a", "FAILED: once", "error: b", "error: c" ]
    detail = select_failure_detail_lines( lines, limit=3 )
    assert detail == [ "FAILED: once", "error: a", "error: b" ]
