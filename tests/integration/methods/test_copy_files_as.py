import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_copy_files_as(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "dest = os.path.join(env['abs_final_dir'], 'renamed.txt')\n"
        "env.CopyFilesAs(dest, 'data/copy_me.txt')\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_under_build(project, "renamed.txt")
