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
        "active = env.Toolchain()\n"
        "assert active is env['toolchain']\n"
        "assert env.HasToolchain(active.name())\n"
        "assert not env.HasToolchain('definitely_missing_toolchain_xyz')\n"
        "assert env.Variant() is env['variant']\n"
        "assert env.Variant().name() == 'dbg'\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
