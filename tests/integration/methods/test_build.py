import pytest

from tests.helpers.cuppa_runner import (
    assert_success,
    build_files,
    find_final_binaries,
    find_under_build,
    run_cuppa,
)
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_build_main(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('main', 'apps/main.cpp')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    assert find_final_binaries(project, "main")


def test_build_then_clean_removes_outputs(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('main', 'apps/main.cpp')\n",
    )
    assert_success(run_cuppa(project, "--dbg"))
    assert build_files(project), "expected build outputs before clean"
    assert find_final_binaries(project, "main")
    assert find_under_build(project, "*.o") or find_under_build(project, "*.obj")

    assert_success(run_cuppa(project, "--dbg", "--clean"))
    assert build_files(project) == [], (
        "expected no files under _build after --clean, found:\n"
        + "\n".join(str(path) for path in build_files(project))
    )
