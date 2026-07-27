import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_glob_files_and_recursive_glob(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "tests = env.GlobFiles('*_test.cpp', start='tests')\n"
        "assert len(tests) >= 2\n"
        "deep = env.RecursiveGlob('*.cpp', start='src')\n"
        "assert any('deep.cpp' in str(n).replace('\\\\\\\\','/') for n in deep)\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "env.Compile('src/nested/deep.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")
    assert find_under_build(project, "deep.*")
