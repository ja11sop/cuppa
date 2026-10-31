import fnmatch
import json
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
    result = run_cuppa(project, "--cov", "--test", "--terse-output")
    assert_success(result)
    assert find_under_build(project, "*coverage*") or "COVERAGE" in result.stdout
    for line in result.stdout.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("gcov"), line
        assert not stripped.startswith("lines:"), line
        assert not stripped.startswith("functions:"), line
        assert not stripped.startswith("branches:"), line


def test_coverage_report_includes_header_lines(tmp_path):
    """A header gcov cannot see from gcov-run is staged and reported with lines.

    ``-Iinclude`` is a raw flag so the compiler records ``include/dummy/hello.hpp``.
    SCons ``CPPPATH`` would turn that into an absolute path, which ``gcov -r`` drops.
    """
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    (project / "tests" / "widget_test.cpp").write_text(
        '#include "dummy/hello.hpp"\n'
        "int main()\n"
        "{\n"
        "    return dummy_answer() == 42 ? 0 : 1;\n"
        "}\n",
        encoding="utf-8",
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Append(CXXFLAGS=['-Iinclude'])\n"
        "prog = env.BuildTest('widget_test', 'tests/widget_test.cpp')\n"
        "env.Coverage(prog, 'tests/widget_test.cpp')\n",
    )
    result = run_cuppa(project, "--cov", "--test", timeout=300)
    assert_success(result)

    reports = list(Path(project).glob("_build/**/final/coverage--widget_test.json"))
    assert len(reports) == 1, reports
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    headers = [
        item
        for item in payload["files"]
        if item["file"].replace("\\", "/").endswith("include/dummy/hello.hpp")
    ]
    assert len(headers) == 1, [item["file"] for item in payload["files"]]
    assert headers[0]["lines"], headers[0]


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


def test_coverage_parallel_prefix_names_keep_their_reports(tmp_path):
    """``lim`` must not take ``lim_table``'s pages, and gcovr runs once per program.

    ``alpha_cov`` / ``beta_cov`` do not share a prefix, so a green run of that
    fixture says nothing about the glob. ``lim`` has two sources; one gcovr
    invocation per program is two commands, not three.
    """
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    tests_dir = Path(project) / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "lim.cpp").write_text(
        "int lim_extra();\n"
        "int main()\n"
        "{\n"
        "    return lim_extra() == 3 ? 0 : 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (tests_dir / "lim_extra.cpp").write_text(
        "int lim_extra()\n"
        "{\n"
        "    return 3;\n"
        "}\n",
        encoding="utf-8",
    )
    (tests_dir / "lim_table.cpp").write_text(
        "int main()\n"
        "{\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "coverage = []\n"
        "for name, sources in ("
        "('lim', ['tests/lim.cpp', 'tests/lim_extra.cpp']),"
        "('lim_table', 'tests/lim_table.cpp'),"
        "):\n"
        "    test = env.BuildTest(name, sources)\n"
        "    coverage.append(env.CollateCoverageFiles("
        "test, destination='#_artefacts/coverage/'))\n"
        "env.CollateCoverageIndex(coverage, destination='#_artefacts/coverage/')\n",
    )

    result = run_cuppa(project, "--cov", "--test", "--parallel", timeout=300)
    assert_success(result)
    assert "Failed moving" not in result.stdout

    gcovr_runs = [
        line for line in result.stdout.splitlines()
        if line.startswith("gcovr ")
    ]
    assert len(gcovr_runs) == 2, gcovr_runs

    final_html = [
        path.name
        for path in Path(project).glob("_build/**/final/*.html")
    ]
    assert "coverage--lim.html" in final_html
    assert "coverage--lim_table.html" in final_html
    assert not any(name.endswith(".coverage.lim.html") for name in final_html)
    assert any(".coverage.lim." in name for name in final_html)
    assert any(".coverage.lim_table." in name for name in final_html)

    lim_json = list(Path(project).glob("_build/**/final/coverage--lim.json"))
    assert len(lim_json) == 1, lim_json
    payload = json.loads(lim_json[0].read_text(encoding="utf-8"))
    covered = {item["file"].replace("\\", "/").rsplit("/", 1)[-1] for item in payload["files"]}
    assert {"lim.cpp", "lim_extra.cpp"} <= covered, payload["files"]

    filters = list(Path(project).glob("_build/**/final/coverage--lim.cov_filter"))
    assert len(filters) == 1, filters
    pattern = filters[0].read_text(encoding="utf-8").splitlines()[0]
    matched = [name for name in final_html if fnmatch.fnmatch(name, pattern)]
    assert matched
    assert all("lim_table" not in name for name in matched)

    assert list(Path(project).glob("*.html")) == []
    assert list(tests_dir.glob("*.html")) == []
    assert list(Path(project).glob("_build/**/gcov-data/lim/gcovr/*.html")) == []

    coverage_root = Path(project) / "_artefacts" / "coverage"
    indexes = list(coverage_root.rglob("coverage-index--*.html"))
    assert indexes
    report_dirs = []
    for program, page in (("lim", "coverage--lim.html"), ("lim_table", "coverage--lim_table.html")):
        href = "{}/{}".format(program, page)
        linked = [
            index for index in indexes
            if 'href="{}"'.format(href) in index.read_text(encoding="utf-8")
        ]
        assert linked, href
        for index in linked:
            report = index.parent / program / page
            assert report.is_file(), report
            assert not (index.parent / page).exists()
            report_dirs.append(index.parent / program)

    # Coverage nodes exist only when the test action is on, so -c has to
    # ask for the same actions that produced the reports.
    clean = run_cuppa(project, "-c", "--cov", "--test", timeout=120)
    assert_success(clean)
    for report_dir in report_dirs:
        assert not report_dir.exists(), report_dir


def test_coverage_parallel_independent_tests(tmp_path):
    """Two single-file tests (no shared lib) still succeed under --cov --test --parallel."""
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    _two_independent_coverage_tests(project)
    result = run_cuppa(project, "--cov", "--test", "--parallel", timeout=300)
    assert_success(result)
    assert find_under_build(project, "*coverage*") or "COVERAGE" in result.stdout
    assert "Collecting coverage with SCons -j is not reliable" not in result.stdout


def _shared_library_project(tmp_path):
    """Two tests, one static library, one library function per test.

    Coverage is collected over the library source as well as the test source,
    so each test's report says which library function that test ran. If the
    two processes shared one ``.gcda``, both reports would show both functions.
    """
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    lib_dir = Path(project) / "lib"
    lib_dir.mkdir()
    (lib_dir / "shared.hpp").write_text(
        "int used_by_alpha();\nint used_by_beta();\n",
        encoding="utf-8",
    )
    (lib_dir / "shared.cpp").write_text(
        "int used_by_alpha()\n{\n    return 1;\n}\n"
        "int used_by_beta()\n{\n    return 2;\n}\n",
        encoding="utf-8",
    )
    for name, call, value in (("alpha_cov", "used_by_alpha", 1), ("beta_cov", "used_by_beta", 2)):
        (Path(project) / "tests" / (name + ".cpp")).write_text(
            '#include "../lib/shared.hpp"\n'
            "int main() {{ return {}() == {} ? 0 : 1; }}\n".format(call, value),
            encoding="utf-8",
        )
    write_sconscript(
        project,
        "Import('env')\n"
        "lib = env.BuildStaticLib('shared_cov', 'lib/shared.cpp')\n"
        "for name in ('alpha_cov', 'beta_cov'):\n"
        "    sources = ['tests/{}.cpp'.format(name)]\n"
        "    prog = env.Build(name, sources, LIBS=lib)\n"
        "    test = env.Test(prog)\n"
        "    cov = env.Coverage(prog, sources + ['lib/shared.cpp'])\n"
        "    env.Depends(cov, test)\n",
    )
    return project


def _library_function_counts(project, program):
    reports = list(Path(project).glob("_build/**/final/coverage--{}.json".format(program)))
    assert len(reports) == 1, reports
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    counts = {}
    for item in payload["files"]:
        if item["file"].replace("\\", "/").endswith("lib/shared.cpp"):
            for function in item["functions"]:
                for name in ("used_by_alpha", "used_by_beta"):
                    if name in function["name"]:
                        counts[name] = function["execution_count"]
    assert set(counts) == {"used_by_alpha", "used_by_beta"}, payload
    return counts


@pytest.mark.parametrize("parallel", [False, True], ids=["serial", "parallel"])
def test_coverage_shared_library_notes_are_per_test(tmp_path, parallel):
    """Each test's ``.gcda`` for a shared library is its own (``GCOV_PREFIX``).

    The prefix is always on under ``--cov``, so serial collection takes the
    same path. Sconscript-owned fixtures (a port, a database) are out of scope.
    """
    _skip_if_no_gcov_coverage()

    project = _shared_library_project(tmp_path)
    flags = ["--cov", "--test"] + (["--parallel"] if parallel else [])
    result = run_cuppa(project, *flags, timeout=300)
    assert_success(result)

    notes = [
        path for path in Path(project).glob("_build/**/gcov-data/*/**/shared.gcda")
        if "gcov-run" not in path.parts
    ]
    owners = sorted(
        path.parts[path.parts.index("gcov-data") + 1] for path in notes
    )
    assert owners == ["alpha_cov", "beta_cov"], notes
    beside_object = [
        path for path in Path(project).glob("_build/**/shared.gcda")
        if "gcov-data" not in path.parts
    ]
    assert beside_object == [], "the library .gcda must not be written beside its object"

    alpha = _library_function_counts(project, "alpha_cov")
    beta = _library_function_counts(project, "beta_cov")
    assert alpha["used_by_alpha"] == 1 and alpha["used_by_beta"] == 0, alpha
    assert beta["used_by_beta"] == 1 and beta["used_by_alpha"] == 0, beta


def test_coverage_build_benchmark_uses_per_binary_notes(tmp_path):
    """Benchmarks share the test runners, so they get the same note isolation."""
    _skip_if_no_gcov_coverage()

    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildBenchmark('noop_bench', 'benches/noop_bench.cpp')\n",
    )
    result = run_cuppa(project, "--cov", "--benchmark", timeout=300)
    assert_success(result)

    assert list(Path(project).glob("_build/**/gcov-data/noop_bench/**/noop_bench.gcda"))
    reports = list(Path(project).glob("_build/**/final/coverage--noop_bench.json"))
    assert len(reports) == 1, reports
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert any(line["count"] > 0 for item in payload["files"] for line in item["lines"]), payload


def test_coverage_parallel_compile_only(tmp_path):
    """Instrumented compile with --parallel (no --test) still builds and does not collect."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--cov", "--parallel", timeout=300)
    assert_success(result)
    assert "Collecting coverage with SCons -j is not reliable" not in result.stdout
