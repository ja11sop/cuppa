import sys

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

# Multi-part shell string as in methods.adoc / issue #14.
# Use ./tool on POSIX so a real shell can find the cwd binary; Windows cmd
# finds tool.exe on cwd without .\\ (and .\\ would be mangled by some paths).
_MULTIPART_SHELL_SCONSCRIPT = (
    "Import('env')\n"
    "import os\n"
    "from SCons.Script import Action\n"
    "\n"
    "tool = env.Build('tool', ['tool.cpp'])\n"
    "marker = env.File(os.path.join(env['abs_final_dir'], 'shell.done'))\n"
    "exe = ('./tool' if os.name != 'nt' else 'tool') + env['PROGSUFFIX']\n"
    "shell_cmd = 'cd {} && {} --self-check'.format(env['abs_final_dir'], exe)\n"
    "env.Command(marker, tool, Action(shell_cmd))\n"
)


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
        # Basename only — working_dir is the cwd. Do not use './' / '.\\' prefixes:
        # shlex.split (posix) treats '\\t' in '.\\tool.exe' as an escape on Windows.
        "tool_cmd = 'tool{} --self-check'.format(env['PROGSUFFIX'])\n"
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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "Issue #14 failure mode is posix_spawn → IncrementalSubProcess argv. "
        "Windows colourised SPAWN wraps native PSPAWN (not argv Popen), so "
        "'cd … && …' is outside that failure mode — covered by "
        "test_multipart_shell_action_succeeds_on_windows_colourised_spawn."
    ),
)
def test_multipart_shell_action_fails_under_colourised_posix_spawn(tmp_path):
    """#14: colourised posix SPAWN runs argv lists, so 'cd … && …' fails."""
    project = copy_dummy_project(tmp_path)
    (project / "tool.cpp").write_text(_TOOL_CPP, encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(project, _MULTIPART_SHELL_SCONSCRIPT)
    # Default output (no --raw-output) installs colourised SPAWN.
    result = run_cuppa(project, "--dbg")
    assert "--raw-output" not in result.args
    assert_failure(result)
    assert "No such file or directory: 'cd'" in result.stdout or "cd:" in result.stdout
    assert not find_under_build(project, "shell.done")
    assert not find_under_build(project, "cwd_probe.txt")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Contrasts with colourised posix SPAWN; Windows path is separate.",
)
def test_multipart_shell_action_succeeds_with_raw_output_on_posix(tmp_path):
    """Without colourised SPAWN (--raw-output), SCons' shell can run 'cd … && …'."""
    project = copy_dummy_project(tmp_path)
    (project / "tool.cpp").write_text(_TOOL_CPP, encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(project, _MULTIPART_SHELL_SCONSCRIPT)
    result = run_cuppa(project, "--dbg", "--raw-output")
    assert_success(result)
    assert find_final_binaries(project, "tool")
    probes = find_under_build(project, "cwd_probe.txt")
    assert probes, "shell cd must have run the tool in abs_final_dir"
    assert all("final" in path.parts for path in probes)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Documents Windows colourised SPAWN (PSPAWN wrapper), not posix argv spawn.",
)
def test_multipart_shell_action_succeeds_on_windows_colourised_spawn(tmp_path):
    """Windows colourised SPAWN still delegates to native PSPAWN (shell-capable)."""
    project = copy_dummy_project(tmp_path)
    (project / "tool.cpp").write_text(_TOOL_CPP, encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(project, _MULTIPART_SHELL_SCONSCRIPT)
    # Explicitly colourised path: do not pass --raw-output.
    result = run_cuppa(project, "--dbg")
    assert "--raw-output" not in result.args
    assert_success(result)
    assert find_final_binaries(project, "tool")
    probes = find_under_build(project, "cwd_probe.txt")
    assert probes, "Windows colourised PSPAWN ran the shell cd && tool"
    assert all("final" in path.parts for path in probes)
