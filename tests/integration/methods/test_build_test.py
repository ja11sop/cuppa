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


def test_build_test_test_depends_on_associates_file(tmp_path):
    """test_depends_on / data add rebuild Depends, not argv (#34)."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest(\n"
        "    'hello_test',\n"
        "    'tests/hello_test.cpp',\n"
        "    test_depends_on=['data/copy_me.txt'],\n"
        ")\n",
    )
    result = run_cuppa(project, "--dbg", "--test", "--show-test-output")
    assert_success(result)
    assert "copy_me.txt" in result.stdout
    # Legacy data= still works
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest(\n"
        "    'hello_test',\n"
        "    'tests/hello_test.cpp',\n"
        "    data=['data/sample.md'],\n"
        ")\n",
    )
    result_data = run_cuppa(project, "--dbg", "--test")
    assert_success(result_data)
    assert "sample.md" in result_data.stdout
    # Legacy depends_on= still maps to build side (accepted; no failure)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest(\n"
        "    'hello_test',\n"
        "    'tests/hello_test.cpp',\n"
        "    build_depends_on=['data/copy_me.txt'],\n"
        ")\n",
    )
    result_build = run_cuppa(project, "--dbg", "--test")
    assert_success(result_build)


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
