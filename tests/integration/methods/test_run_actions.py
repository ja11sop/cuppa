import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_run_and_benchmark(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.Build('noop_bench', 'benches/noop_bench.cpp')\n"
        "env.Run(prog)\n"
        "env.Benchmark(prog)\n",
    )
    result = run_cuppa(project, "--dbg", "--run", "--benchmark")
    assert_success(result)
    assert find_final_binaries(project, "noop_bench")
    assert find_under_build(project, "*.success") or find_under_build(project, "*.report.json")


def test_build_benchmark(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildBenchmark('noop_bench', 'benches/noop_bench.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--benchmark")
    assert_success(result)
    assert find_final_binaries(project, "noop_bench")
