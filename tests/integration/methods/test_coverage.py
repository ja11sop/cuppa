import logging
import os
import shutil

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def test_coverage_method(tmp_path):
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        message = "MSVC does not support gcov coverage; skipping coverage integration test"
        logger.warning(message)
        pytest.skip(message)

    if not shutil.which("gcov"):
        message = "gcov not on PATH; skipping coverage integration test"
        logger.warning(message)
        pytest.skip(message)

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
