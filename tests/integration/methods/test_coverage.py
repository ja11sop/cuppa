import logging
import os
import shutil
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript
from cuppa.cpp.coverage_workflow import PARALLEL_COVERAGE_COLLECTION_WARNING


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def _skip_if_no_gcov_coverage():
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        message = "MSVC does not support gcov coverage; skipping coverage integration test"
        logger.warning(message)
        pytest.skip(message)

    if not shutil.which("gcov"):
        message = "gcov not on PATH; skipping coverage integration test"
        logger.warning(message)
        pytest.skip(message)

    if not shutil.which("gcovr"):
        message = "gcovr not on PATH; skipping coverage integration test"
        logger.warning(message)
        pytest.skip(message)


def test_coverage_method(tmp_path):
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "env.Coverage(prog, 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--cov", "--test")
    assert_success(result)
    assert find_under_build(project, "*coverage*") or "COVERAGE" in result.stdout


def test_collate_coverage_index_shared_destination(tmp_path):
    """Two sconscripts sharing an artifacts coverage dir must not clash on by-source Install."""
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    (project / "sconscript").unlink()
    write_sconstruct(project)

    suite = project / "suite"
    suite.mkdir()
    hello = (
        "#include <cstdlib>\n"
        "int main()\n"
        "{\n"
        "    return EXIT_SUCCESS;\n"
        "}\n"
    )

    for name in ("alpha_test", "beta_test"):
        (suite / "{}.cpp".format(name)).write_text(hello, encoding="utf-8")
        (suite / "{}.sconscript".format(name)).write_text(
            "Import('env')\n"
            "prog = env.BuildTest('{name}', '{name}.cpp')\n"
            "cov = env.CollateCoverageFiles(prog, destination='#_artefacts/coverage/')\n"
            "env.CollateCoverageIndex(cov, destination='#_artefacts/coverage/')\n".format(
                name=name
            ),
            encoding="utf-8",
        )

    result = run_cuppa(project, "--cov", "--test", timeout=300)
    assert_success(result)

    artefacts = Path(project) / "_artefacts" / "coverage"
    indexes = sorted(artefacts.rglob("coverage-index--*.html"))
    assert indexes, "expected collated coverage index HTML under _artefacts/coverage"

    namespaced = [
        path
        for path in artefacts.rglob("*.html")
        if "by-source" in path.parts and path.parent.name.startswith("coverage-index--")
    ]
    assert namespaced, (
        "by-source pages should be namespaced under by-source/<index-stem>/ "
        "so sibling sconscripts can share a coverage destination"
    )


def test_coverage_with_mirrored_nested_source(tmp_path):
    """--cov still works when CompileObject mirrors source trees under working/ (#213)."""
    _skip_if_no_gcov_coverage()

    project = tmp_path / "cov_nested"
    project.mkdir()
    (project / "src" / "detail").mkdir(parents=True)
    (project / "src" / "detail" / "nested_test.cpp").write_text(
        "#include <cstdlib>\n"
        "int main()\n"
        "{\n"
        "    return EXIT_SUCCESS;\n"
        "}\n",
        encoding="utf-8",
    )
    write_sconstruct(project, default_variants=["dbg"])
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.BuildTest('nested_cov', 'src/detail/nested_test.cpp')\n"
        "env.Coverage(prog, 'src/detail/nested_test.cpp')\n",
    )

    result = run_cuppa(project, "--cov", "--test", timeout=300)
    assert_success(result)

    working_dirs = list((Path(project) / "_build").rglob("working"))
    assert working_dirs, "expected a working/ directory under _build"
    mirrored_object = [
        path
        for root in working_dirs
        for path in root.rglob("nested_test.o")
        if path.parent.name == "detail" and path.parent.parent.name == "src"
    ]
    assert mirrored_object, (
        "expected CompileObject to mirror src/detail/nested_test.o under working/"
    )
    mirrored_gcda = [
        path
        for root in working_dirs
        for path in root.rglob("nested_test.gcda")
        if path.parent.name == "detail" and path.parent.parent.name == "src"
    ]
    assert mirrored_gcda, (
        "expected .gcda beside the mirrored object under working/src/detail/"
    )
    assert find_under_build(project, "*coverage*") or "COVERAGE" in result.stdout


def _two_independent_coverage_tests(project):
    write_sconstruct(project)
    hello = (
        "#include <cstdlib>\n"
        "int main()\n"
        "{\n"
        "    return EXIT_SUCCESS;\n"
        "}\n"
    )
    tests_dir = Path(project) / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "alpha_cov.cpp").write_text(hello, encoding="utf-8")
    (tests_dir / "beta_cov.cpp").write_text(hello, encoding="utf-8")
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest('alpha_cov', 'tests/alpha_cov.cpp')\n"
        "env.BuildTest('beta_cov', 'tests/beta_cov.cpp')\n",
    )


def test_coverage_parallel_independent_tests(tmp_path):
    """Two single-file tests (no shared lib) still succeed under --cov --test --parallel."""
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    _two_independent_coverage_tests(project)
    result = run_cuppa(project, "--cov", "--test", "--parallel", timeout=300)
    assert_success(result)
    assert find_under_build(project, "*coverage*") or "COVERAGE" in result.stdout


def test_coverage_parallel_collection_warns(tmp_path):
    """--cov --test --parallel warns when SCons actually runs with -j > 1."""
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    _two_independent_coverage_tests(project)
    result = run_cuppa(project, "--cov", "--test", "--parallel", timeout=300)
    assert_success(result)
    entered_parallel = "parallel mode" in result.stdout
    if entered_parallel:
        assert PARALLEL_COVERAGE_COLLECTION_WARNING in result.stdout
    else:
        assert PARALLEL_COVERAGE_COLLECTION_WARNING not in result.stdout


def test_coverage_parallel_compile_only_does_not_warn(tmp_path):
    """Instrumented compile with --parallel (no --test) is the supported first step."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--cov", "--parallel", timeout=300)
    assert_success(result)
    assert PARALLEL_COVERAGE_COLLECTION_WARNING not in result.stdout
