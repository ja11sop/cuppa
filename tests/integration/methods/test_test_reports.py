import logging
import os
import shutil
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


_HELLO_CPP = (
    "#include <cstdlib>\n"
    "int main()\n"
    "{\n"
    "    return EXIT_SUCCESS;\n"
    "}\n"
)


def _skip_if_no_gcov():
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        pytest.skip("MSVC does not support gcov coverage")
    if not shutil.which("gcov") or not shutil.which("gcovr"):
        pytest.skip("gcov/gcovr not on PATH")


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

    html_reports = find_under_build(project, "*.report.html")
    assert html_reports
    summaries = find_under_build(project, "*.report-summary.json")
    assert summaries
    assert "hello_test" in html_reports[0].read_text(encoding="utf-8")


def test_html_test_report_with_coverage_json(tmp_path):
    """GenerateHtmlTestReport must ignore coverage--*.json beside *.report.json."""
    _skip_if_no_gcov()

    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "env.GenerateHtmlTestReport(prog)\n",
    )
    result = run_cuppa(project, "--cov", "--test")
    assert_success(result)
    assert find_under_build(project, "*.report.html")
    assert find_under_build(project, "coverage--*.json")


def test_collate_test_report_index(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "prog = env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "reports = env.GenerateHtmlTestReport(prog)\n"
        "env.CollateTestReportIndex(reports, destination='#_artifacts/test/')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)

    artifacts = Path(project) / "_artifacts" / "test"
    assert artifacts.is_dir()
    assert list(artifacts.rglob("*.report.html")), "expected collated HTML reports under _artifacts/test"
    assert list(artifacts.rglob("*.report-summary.json")), "expected collated summary JSON"
    index_html = artifacts / "test-report-index.html"
    index_json = artifacts / "test-report-index.json"
    assert index_html.is_file(), "expected master test-report-index.html at sconstruct end"
    assert index_json.is_file(), "expected master test-report-index.json at sconstruct end"
    assert "hello_test" in index_html.read_text(encoding="utf-8")


def test_collate_test_report_index_shared_destination(tmp_path):
    """Sibling sconscripts can collate into the same artifacts test-report destination."""
    project = copy_dummy_project(tmp_path)
    (project / "sconscript").unlink()
    write_sconstruct(project)

    suite = project / "suite"
    suite.mkdir()
    for name in ("alpha_test", "beta_test"):
        (suite / "{}.cpp".format(name)).write_text(_HELLO_CPP, encoding="utf-8")
        (suite / "{}.sconscript".format(name)).write_text(
            "Import('env')\n"
            "prog = env.BuildTest('{name}', '{name}.cpp')\n"
            "reports = env.GenerateHtmlTestReport(prog)\n"
            "env.CollateTestReportIndex(reports, destination='#_artifacts/test/')\n".format(
                name=name
            ),
            encoding="utf-8",
        )

    result = run_cuppa(project, "--dbg", "--test", timeout=300)
    assert_success(result)

    artifacts = Path(project) / "_artifacts" / "test"
    report_names = {path.name for path in artifacts.rglob("*.report.html")}
    assert "alpha_test.report.html" in report_names
    assert "beta_test.report.html" in report_names
    assert (artifacts / "test-report-index.html").is_file()
    index_text = (artifacts / "test-report-index.html").read_text(encoding="utf-8")
    assert "alpha_test" in index_text
    assert "beta_test" in index_text


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
