import logging

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def test_html_test_report(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "env.GenerateHtmlTestReport(prog)\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_under_build(project, "*.report.html")


def test_bitten_report(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "env.GenerateBittenReport(prog)\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_under_build(project, "*bitten*.xml")
