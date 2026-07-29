import pytest

from tests.helpers.cuppa_runner import (
    assert_failure,
    assert_success,
    find_final_binaries,
    run_cuppa,
)
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_build_test_passes(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\nenv.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")


def test_default_variants_honoured_with_test_only(tmp_path):
    """Project default_variants=['dbg'] must apply when only --test is passed (#47)."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project, default_variants=["dbg"])
    write_sconscript(
        project,
        "Import('env')\nenv.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--test")
    assert_success(result)
    binaries = find_final_binaries(project, "hello_test")
    assert binaries
    assert all("dbg" in path.parts for path in binaries)
    assert not any("rel" in path.parts for path in binaries)


def test_build_test_fails_on_nonzero_exit(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\nenv.BuildTest('fail_test', 'tests/fail_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_failure(result)


def test_test_method_on_built_binary(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.Build('hello_test', 'tests/hello_test.cpp')\n"
        "env.Test(prog)\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
