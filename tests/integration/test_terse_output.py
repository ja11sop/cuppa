import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def _looks_like_tool_command(line):
    return " -c " in line or " /c " in line or " -o " in line or " /Fo" in line


def test_terse_output_folds_a_clean_compile_and_hides_progress_lines(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.CompileStatic('src/hello.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--terse-output")
    assert_success(result)
    assert "[ok]" in result.stdout
    assert "Progress(" not in result.stdout
    commands = [line for line in result.stdout.splitlines() if _looks_like_tool_command(line)]
    assert commands == []
