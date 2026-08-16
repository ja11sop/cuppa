import logging
import os
import shutil
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


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
