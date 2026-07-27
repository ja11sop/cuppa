import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_run_and_redirect_to_file(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.Build('noop_bench', 'benches/noop_bench.cpp')\n"
        "env.RunAndRedirectToFile([], prog, extension='.captured')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    assert find_under_build(project, "*.captured")
