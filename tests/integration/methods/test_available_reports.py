#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json
import logging
import re
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript
from tests.helpers.toolchains import profiles_toolchain_flags
from tests.integration.methods.test_coverage import _skip_if_no_gcov_coverage


logger = logging.getLogger( __name__ )

pytestmark = pytest.mark.integration


_CLEAN_TEST_CPP = (
    "#include <cstdlib>\n"
    "int main()\n"
    "{\n"
    "    return EXIT_SUCCESS;\n"
    "}\n"
)

_INVENTORY_VIOLATION_CPP = (
    "int main()\n"
    "{\n"
    "    int Automatic;\n"
    "    (void)Automatic;\n"
    "    return 0;\n"
    "}\n"
)

_METRICS_VIOLATION_CPP = (
    "int main()\n"
    "{\n"
    "    int Value [[uninit]];\n"
    "    int Copy = Value;\n"
    "    (void)Copy;\n"
    "    return Copy;\n"
    "}\n"
)

# Three BuildTest programs in one loop — test + coverage collation (gcc/clang + gcov).
TEST_COVERAGE_SCONSCRIPT = (
    "Import('env')\n"
    "test_specs = (\n"
    "    ('smoke_test', 'tests/smoke_test.cpp'),\n"
    "    ('latency_test', 'tests/latency_test.cpp'),\n"
    "    ('throughput_test', 'tests/throughput_test.cpp'),\n"
    ")\n"
    "report_nodes = []\n"
    "coverage_nodes = []\n"
    "for Name, Source in test_specs:\n"
    "    prog = env.BuildTest(Name, Source)\n"
    "    report_nodes.extend(env.GenerateHtmlTestReport(prog))\n"
    "    coverage_nodes.append(\n"
    "        env.CollateCoverageFiles(prog, destination='#_artefacts/coverage/')\n"
    "    )\n"
    "env.CollateTestReportIndex(report_nodes, destination='#_artefacts/test/')\n"
    "env.CollateCoverageIndex(coverage_nodes, destination='#_artefacts/coverage/')\n"
)

# Profiles inventory — separate invocation; index declared in sconscript (not CLI).
PROFILES_SCONSCRIPT = (
    "Import('env')\n"
    "env.Build('inventory_violation', 'tests/inventory_violation.cpp')\n"
    "env.Build('metrics_violation', 'tests/metrics_violation.cpp')\n"
    "env.CollateCxxProfilesIndex()\n"
)


def _strip_ansi( text ):
    return re.sub( r'\x1b\[[0-9;]*m', '', text or '' )


def _write_canonical_test_sources( project ):
    tests_dir = Path( project ) / 'tests'
    tests_dir.mkdir( exist_ok=True )
    ( tests_dir / 'smoke_test.cpp' ).write_text( _CLEAN_TEST_CPP, encoding='utf-8' )
    ( tests_dir / 'latency_test.cpp' ).write_text( _CLEAN_TEST_CPP, encoding='utf-8' )
    ( tests_dir / 'throughput_test.cpp' ).write_text( _CLEAN_TEST_CPP, encoding='utf-8' )
    ( tests_dir / 'inventory_violation.cpp' ).write_text(
        _INVENTORY_VIOLATION_CPP,
        encoding='utf-8',
    )
    ( tests_dir / 'metrics_violation.cpp' ).write_text(
        _METRICS_VIOLATION_CPP,
        encoding='utf-8',
    )


def _has_report_html( report_names, stem ):
    return (
        '{}.report.html'.format( stem ) in report_names
        or '{}.exe.report.html'.format( stem ) in report_names
    )


def test_list_available_reports_judgement_tree( tmp_path ):
    """``--list-available-reports`` on a real sconstruct prints the catalogue tree."""
    project = tmp_path / 'reports_list'
    project.mkdir()
    write_sconstruct( project )
    write_sconscript( project, "Import('env')\n" )

    result = run_cuppa( project, '-Q', '--list-available-reports' )
    assert_success( result )

    text = _strip_ansi( result.stdout )
    header_pos = text.index( 'Report kinds available with current toolchains' )
    artefacts_pos = text.index( '{artefacts_root}:' )
    build_pos = text.index( '{build_root}:' )
    test_pos = text.index( 'Collated Test Report' )
    assert header_pos < artefacts_pos < build_pos < test_pos
    assert 'Collated Coverage Report' in text
    assert 'Collated C++ Profiles Report' in text
    assert 'env.CollateTestReportIndex()' in text
    assert 'env.CollateCoverageIndex()' in text
    assert 'env.CollateCxxProfilesIndex()' in text
    assert '{artefacts_root}/test/' in text
    assert '{artefacts_root}/coverage/' in text
    assert 'specify destination, default' in text
    assert '{artefacts_root}/cxx-profiles/' in text
    assert '--remove-artefacts' in text


def test_list_available_reports_json( tmp_path ):
    """``--list-available-reports --list-format=json`` exits zero on a real project."""
    project = tmp_path / 'reports_json'
    project.mkdir()
    write_sconstruct( project )
    write_sconscript( project, "Import('env')\n" )

    result = run_cuppa(
        project,
        '-Q',
        '--list-available-reports',
        '--list-format=json',
    )
    assert_success( result )
    assert '"report_kinds"' in result.stdout
    assert '"cxx-profiles"' in result.stdout


def test_canonical_collated_reports_under_artefacts_root( tmp_path ):
    """
    Canonical ``_artefacts/`` tree from separate test/coverage and Profiles runs.

    Test and coverage share one ``--cov --test`` invocation (three ``BuildTest``
    programs in a loop). Profiles uses a second invocation with Alliance Clang
    (local or ``--toolchain-archive=``), ``env.CollateCxxProfilesIndex()`` in
    the sconscript (no ``--cxx-profiles-report``); keep-going is implied by
    inventory mode (no manual ``-i``).
    """
    _skip_if_no_gcov_coverage()
    profiles_flags, needs_network = profiles_toolchain_flags( allow_archive=True )

    project = copy_dummy_project( tmp_path )
    _write_canonical_test_sources( project )
    write_sconstruct( project )

    write_sconscript( project, TEST_COVERAGE_SCONSCRIPT )
    test_cov_result = run_cuppa(
        project,
        '--dbg',
        '--test',
        '--cov',
        timeout=300,
    )
    assert_success( test_cov_result )

    write_sconscript( project, PROFILES_SCONSCRIPT )
    profiles_result = run_cuppa(
        project,
        '--dbg',
        '--cxx-profiles',
        '--cxx-profiles-enforce=std::init',
        '--cxx-disable-error-limit',
        *profiles_flags,
        offline=not needs_network,
        timeout=900 if needs_network else 300,
    )
    assert_success( profiles_result )

    for test_name in ( 'smoke_test', 'latency_test', 'throughput_test' ):
        assert find_final_binaries( project, test_name ), (
            'expected {} binary under _build/final/'.format( test_name )
        )

    test_dir = Path( project ) / '_artefacts' / 'test'
    coverage_dir = Path( project ) / '_artefacts' / 'coverage'
    profiles_dir = Path( project ) / '_artefacts' / 'cxx-profiles'

    test_index = test_dir / 'test-report-index.html'
    assert test_index.is_file(), 'expected master test-report-index.html under _artefacts/test/'
    index_text = test_index.read_text( encoding='utf-8' )
    for test_name in ( 'smoke_test', 'latency_test', 'throughput_test' ):
        assert test_name in index_text

    report_names = { path.name for path in test_dir.rglob( '*.report.html' ) }
    for test_name in ( 'smoke_test', 'latency_test', 'throughput_test' ):
        assert _has_report_html( report_names, test_name ), (
            'expected collated {} HTML under _artefacts/test/'.format( test_name )
        )

    coverage_indexes = sorted( coverage_dir.rglob( 'coverage-index--*.html' ) )
    assert coverage_indexes, 'expected coverage index HTML under _artefacts/coverage/'
    for test_name in ( 'smoke_test', 'latency_test', 'throughput_test' ):
        per_test = sorted( coverage_dir.rglob( 'coverage--{}.html'.format( test_name ) ) )
        assert per_test, 'expected coverage HTML for {}'.format( test_name )

    profiles_json = profiles_dir / 'cxx-profiles-index.json'
    assert ( profiles_dir / 'cxx-profiles-index.html' ).is_file()
    assert profiles_json.is_file()

    payload = json.loads( profiles_json.read_text( encoding='utf-8' ) )
    summary = payload.get( 'summary' ) or {}
    total_references = summary.get( 'total_references' ) or 0
    assert total_references >= 2, (
        'expected Profiles inventory from inventory_violation and metrics_violation '
        '(total_references={})'.format( total_references )
    )
