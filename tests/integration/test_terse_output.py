import re

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def _looks_like_tool_command(line):
    return " -c " in line or " /c " in line or " -o " in line or " /Fo" in line


def _compile_hello(tmp_path, *flags):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.CompileStatic('src/hello.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", *flags)
    assert_success(result)
    assert "[ok]" in result.stdout
    assert "compile" in result.stdout
    assert "hello.cpp" in result.stdout
    commands = [line for line in result.stdout.splitlines() if _looks_like_tool_command(line)]
    assert commands == []
    return result


def _plain( text ):
    return re.sub( r"\x1b\[[0-9;]*m", "", text )


def test_terse_output_folds_a_clean_compile_and_prints_progress_checkpoints(tmp_path):
    result = _compile_hello(tmp_path, "--terse-output")
    plain = _plain( result.stdout )
    assert "[progress]" in plain
    assert "· begin" in plain
    assert "· end" in plain
    assert "Progress(" not in plain


def test_quiet_keeps_terse_progress_checkpoints(tmp_path):
    result = _compile_hello(tmp_path, "--terse-output", "-Q")
    plain = _plain( result.stdout )
    assert "[progress]" in plain
    assert "· begin" in plain
    assert "· end" in plain
    assert "Progress(" not in plain
