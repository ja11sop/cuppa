import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_scripts_scoping(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    (project / "only_a").mkdir()
    (project / "only_b").mkdir()
    (project / "only_a" / "sconscript").write_text(
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('prog_a', '#/apps/main.cpp')\n"
    )
    (project / "only_b" / "sconscript").write_text(
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('prog_b', '#/apps/main.cpp')\n"
    )
    # Remove default sconscript so only selected scripts run
    (project / "sconscript").unlink()

    result = run_cuppa(project, "--dbg", "--scripts=only_a/sconscript")
    assert_success(result)
    assert find_final_binaries(project, "prog_a")
    assert not find_final_binaries(project, "prog_b")
