import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_toolchain_method(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "active = env['toolchain'].name()\n"
        "looked_up = env.Toolchain(active)\n"
        "assert looked_up is not None\n"
        "assert looked_up.name() == active\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
