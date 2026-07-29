import pytest

from tests.helpers.cuppa_runner import (
    assert_failure,
    assert_success,
    find_final_binaries,
    find_under_build,
    run_cuppa,
)
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration

# Writes cwd_probe.txt into the process current directory (verifies working_dir/cwd).
_CWD_PROBE_CPP = """\
#include <fstream>

int main()
{
    std::ofstream("cwd_probe.txt") << "ok\\n";
    return 0;
}
"""

# Accepts optional --self-check; writes cwd_probe.txt in cwd.
_TOOL_CPP = """\
#include <fstream>
#include <cstring>

int main(int argc, char** argv)
{
    if (argc > 1 && std::strcmp(argv[1], "--self-check") != 0)
        return 1;
    std::ofstream("cwd_probe.txt") << "ok\\n";
    return 0;
}
"""


def test_build_test_working_dir_matches_docs(tmp_path):
    """methods.adoc: BuildTest(..., working_dir=env['abs_final_dir'])."""
    project = copy_dummy_project(tmp_path)
    (project / "cwd_probe.cpp").write_text(_CWD_PROBE_CPP, encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest(\n"
        "    'cwd_probe',\n"
        "    ['cwd_probe.cpp'],\n"
        "    working_dir=env['abs_final_dir'],\n"
        ")\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "cwd_probe")
    probes = find_under_build(project, "cwd_probe.txt")
    assert probes, "expected cwd_probe.txt written under the test working_dir"
    assert all("final" in path.parts for path in probes)


def test_utility_command_run_with_cwd_matches_docs(tmp_path):
    """methods.adoc: cuppa.utility.command.run(..., working_dir=..., completion_file=...)."""
    project = copy_dummy_project(tmp_path)
    (project / "tool.cpp").write_text(_TOOL_CPP, encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "from cuppa.utility.command import run\n"
        "\n"
        "tool = env.Build('tool', ['tool.cpp'])\n"
        "marker = env.File(os.path.join(env['abs_final_dir'], 'tool.done'))\n"
        "tool_cmd = '{} --self-check'.format(os.path.join('.', 'tool' + env['PROGSUFFIX']))\n"
        "\n"
        "env.Command(\n"
        "    marker,\n"
        "    tool,\n"
        "    run(tool_cmd, working_dir=env['abs_final_dir'], completion_file=marker),\n"
        ")\n",
    )
    # --parallel exercises the parallel-safe cwd= path called out in the docs.
    result = run_cuppa(project, "--dbg", "--parallel")
    assert_success(result)
    assert find_final_binaries(project, "tool")
    markers = find_under_build(project, "tool.done")
    assert markers
    assert all("final" in path.parts for path in markers)
    probes = find_under_build(project, "cwd_probe.txt")
    assert probes
    assert all("final" in path.parts for path in probes)


def test_multipart_shell_action_fails_without_use_shell(tmp_path):
    """methods.adoc: Action('cd … && …') fails when SPAWN uses argv (no shell)."""
    project = copy_dummy_project(tmp_path)
    (project / "tool.cpp").write_text(_TOOL_CPP, encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "from SCons.Script import Action\n"
        "\n"
        "tool = env.Build('tool', ['tool.cpp'])\n"
        "marker = env.File(os.path.join(env['abs_final_dir'], 'shell.done'))\n"
        "shell_cmd = 'cd {} && {} --self-check'.format(\n"
        "    env['abs_final_dir'],\n"
        "    os.path.join('.', 'tool' + env['PROGSUFFIX']),\n"
        ")\n"
        "env.Command(marker, tool, Action(shell_cmd))\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_failure(result)
    assert not find_under_build(project, "shell.done")
