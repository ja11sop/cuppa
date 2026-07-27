import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_copy_files_and_target_from(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "copied = env.CopyFiles('copied', 'data/copy_me.txt')\n"
        "assert copied\n"
        "src = env.File('tests/hello_test.cpp')\n"
        "name = env.TargetFrom(src)\n"
        "env.BuildTest(name, src)\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_under_build(project, "copy_me.txt")
