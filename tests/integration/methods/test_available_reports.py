#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging
import re
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript
from tests.helpers.toolchains import require_profiles_capable_toolchain
from tests.integration.methods.test_coverage import _skip_if_no_gcov_coverage


logger = logging.getLogger( __name__ )

pytestmark = pytest.mark.integration


# Canonical consumer pattern: build + test/coverage collate chain + Profiles index.
# Matches ``REPORT_CATALOG`` in ``cuppa/reports/available_reports_display.py``.
CANONICAL_REPORTS_SCONSCRIPT = (
    "Import('env')\n"
    "env.Build('main', 'apps/main.cpp')\n"
    "prog = env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
    "reports = env.GenerateHtmlTestReport(prog)\n"
    "env.CollateTestReportIndex(reports, destination='#_artefacts/test/')\n"
    "cov = env.CollateCoverageFiles(prog, destination='#_artefacts/coverage/')\n"
    "env.CollateCoverageIndex(cov, destination='#_artefacts/coverage/')\n"
    "env.CollateCxxProfilesIndex()\n"
)


def _strip_ansi( text ):
    return re.sub( r'\x1b\[[0-9;]*m', '', text or '' )


def _require_gcov_and_profiles_toolchains():
    _skip_if_no_gcov_coverage()
    _, profiles_flag = require_profiles_capable_toolchain()
    return profiles_flag


def test_list_available_reports_judgement_tree( tmp_path ):
    """``--list-available-reports`` on a real sconstruct prints the catalogue tree."""
    project = tmp_path / "reports_list"
    project.mkdir()
    write_sconstruct( project )
    write_sconscript( project, "Import('env')\n" )

    result = run_cuppa( project, "-Q", "--list-available-reports" )
    assert_success( result )

    text = _strip_ansi( result.stdout )
    header_pos = text.index( "Report kinds available with current toolchains" )
    artefacts_pos = text.index( "{artefacts_root}:" )
    build_pos = text.index( "{build_root}:" )
    test_pos = text.index( "Collated Test Report" )
    assert header_pos < artefacts_pos < build_pos < test_pos
    assert "Collated Coverage Report" in text
    assert "Collated C++ Profiles Report" in text
    assert "env.CollateTestReportIndex()" in text
    assert "env.CollateCoverageIndex()" in text
    assert "env.CollateCxxProfilesIndex()" in text
    assert "{artefacts_root}/test/" in text
    assert "{artefacts_root}/coverage/" in text
    assert "specify destination, default" in text
    assert "{artefacts_root}/cxx-profiles/" in text
    assert "--remove-artefacts" in text


def test_list_available_reports_json( tmp_path ):
    """``--list-available-reports --list-format=json`` exits zero on a real project."""
    project = tmp_path / "reports_json"
    project.mkdir()
    write_sconstruct( project )
    write_sconscript( project, "Import('env')\n" )

    result = run_cuppa(
        project,
        "-Q",
        "--list-available-reports",
        "--list-format=json",
    )
    assert_success( result )
    assert '"report_kinds"' in result.stdout
    assert '"cxx-profiles"' in result.stdout


def test_canonical_collated_reports_under_artefacts_root( tmp_path ):
    """
    Build, test, coverage, and Profiles indexes land under ``_artefacts/`` together.

    Skips when gcov/gcovr or a Profiles-capable Clang is unavailable.
    """
    profiles_flag = _require_gcov_and_profiles_toolchains()

    project = copy_dummy_project( tmp_path )
    write_sconstruct( project )
    write_sconscript( project, CANONICAL_REPORTS_SCONSCRIPT )

    result = run_cuppa(
        project,
        "--dbg",
        "--test",
        "--cov",
        "--cxx-profiles",
        "--cxx-profiles-enforce=std::init",
        "--cxx-disable-error-limit",
        "-i",
        profiles_flag,
        timeout=300,
    )
    assert_success( result )

    assert find_final_binaries( project, "main" ), "expected built main under _build/final/"
    assert find_final_binaries( project, "hello_test" ), "expected built hello_test under _build/final/"

    test_dir = Path( project ) / "_artefacts" / "test"
    coverage_dir = Path( project ) / "_artefacts" / "coverage"
    profiles_dir = Path( project ) / "_artefacts" / "cxx-profiles"

    assert ( test_dir / "test-report-index.html" ).is_file()
    assert ( test_dir / "test-report-index.json" ).is_file()
    assert list( test_dir.rglob( "*.report.html" ) ), "expected collated test HTML under _artefacts/test/"

    coverage_indexes = sorted( coverage_dir.rglob( "coverage-index--*.html" ) )
    assert coverage_indexes, "expected coverage index HTML under _artefacts/coverage/"

    assert ( profiles_dir / "cxx-profiles-index.html" ).is_file()
    assert ( profiles_dir / "cxx-profiles-index.json" ).is_file()
