import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_stdcpp_and_flag_helpers(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.StdCpp('c++14')\n"
        "env.AppendUnique(CCFLAGS=['-DCUPPA_FLAG_TEST=1'])\n"
        "env.RemoveFlags(['-DCUPPA_FLAG_TEST'])\n"
        "env.ReplaceFlags(['-Wall'])\n"
        "nodes = [env.File('data/copy_me.txt'), env.File('data/sample.md')]\n"
        "filtered = env.Filter(nodes, match='*.txt')\n"
        "assert len(filtered) == 1\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('main', 'apps/main.cpp')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    assert find_final_binaries(project, "main")
