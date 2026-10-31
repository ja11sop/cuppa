#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json
import os

import pytest

from cuppa.cpp.coverage_by_source import generate_by_source_coverage, source_coverage_entry
from cuppa.cpp.run_gcov_coverage import (
    CoverageIndexBuilder,
    _copy_coverage_artifact,
    _copy_coverage_artifacts_relative,
    _publish_coverage_report,
    coverage_report_dir_name,
    lines_of_code_format,
    link_coverage_report,
)


pytestmark = pytest.mark.unit


def test_copy_coverage_artifact_creates_destination(tmp_path):
    source = tmp_path / "src" / "index.html"
    source.parent.mkdir()
    source.write_text("hello", encoding="utf-8")
    destination = tmp_path / "artifacts" / "nested" / "index.html"

    _copy_coverage_artifact(str(source), str(destination))

    assert destination.read_text(encoding="utf-8") == "hello"


def test_copy_coverage_artifacts_relative_preserves_tree(tmp_path):
    source_root = tmp_path / "final"
    nested = source_root / "by-source" / "coverage-index--suite.alpha"
    nested.mkdir(parents=True)
    page = nested / "lib--widget.hpp.html"
    page.write_text("<html/>", encoding="utf-8")
    destination_root = tmp_path / "artifacts"

    _copy_coverage_artifacts_relative(str(source_root), str(destination_root), [str(page)])

    copied = destination_root / "by-source" / "coverage-index--suite.alpha" / "lib--widget.hpp.html"
    assert copied.read_text(encoding="utf-8") == "<html/>"


def test_source_coverage_entry_namespaces_by_source_subdir():
    entry = source_coverage_entry(
        "include/foo.hpp",
        {1: "covered"},
        by_source_subdir="coverage-index--suite.alpha",
    )
    assert entry.coverage_file == os.path.join(
        "by-source",
        "coverage-index--suite.alpha",
        "include--foo.hpp.html",
    )


def test_generate_by_source_uses_index_subdir_and_copies_independently(tmp_path):
    repo = tmp_path / "repo"
    header = repo / "lib" / "widget.hpp"
    header.parent.mkdir(parents=True)
    header.write_text("int x;\n", encoding="utf-8")

    final = tmp_path / "final"
    final.mkdir()
    payload = {
        "files": [
            {
                "file": "lib/widget.hpp",
                "lines": [{"line_number": 1, "count": 1}],
            }
        ]
    }
    (final / "coverage--alpha.json").write_text(json.dumps(payload), encoding="utf-8")

    written_paths = []
    for index_stem in (
        "coverage-index--suite.alpha",
        "coverage-index--suite.beta",
    ):
        _summary, _entries, show_tab, written = generate_by_source_coverage(
            search_roots=[str(final)],
            output_dir=str(final),
            repo_root=str(repo),
            index_basename=index_stem + ".html",
            get_source_template=CoverageIndexBuilder.get_source_template,
            LOC=lines_of_code_format,
            by_source_subdir=index_stem,
        )
        assert show_tab is True
        assert written
        written_paths.extend(written)
        page = final / "by-source" / index_stem / "lib--widget.hpp.html"
        assert page.is_file()

    destination = tmp_path / "artifacts"
    _copy_coverage_artifacts_relative(str(final), str(destination), written_paths)

    assert (
        destination / "by-source" / "coverage-index--suite.alpha" / "lib--widget.hpp.html"
    ).is_file()
    assert (
        destination / "by-source" / "coverage-index--suite.beta" / "lib--widget.hpp.html"
    ).is_file()


class _Href(object):
    def __init__( self, coverage_file ):
        self.coverage_file = coverage_file


def test_report_directory_name_is_the_program():
    assert coverage_report_dir_name("coverage--account_table.html") == "account_table"
    assert coverage_report_dir_name("coverage-index--gcc15.test.html") is None
    assert coverage_report_dir_name("coverage--.html") is None
    assert coverage_report_dir_name("coverage--../x.html") is None
    assert coverage_report_dir_name("coverage--a/b.html") is None


def test_link_coverage_report_points_into_the_program_directory():
    entry = _Href("coverage--lim_table.html")
    link_coverage_report(entry)
    assert entry.coverage_file == "lim_table/coverage--lim_table.html"

    index = _Href("coverage-index--gcc15.test.sconscript.html")
    link_coverage_report(index)
    assert index.coverage_file == "coverage-index--gcc15.test.sconscript.html"


def test_publish_coverage_report_replaces_its_directory_and_drops_flat_copies(tmp_path):
    source = tmp_path / "final"
    source.mkdir()
    index = source / "coverage--lim.html"
    detail = source / "test.gcc15.coverage.lim.lim.cpp.abc.html"
    index.write_text("index", encoding="utf-8")
    detail.write_text("detail", encoding="utf-8")

    destination = tmp_path / "artifacts"
    destination.mkdir()
    stale = destination / "coverage--lim.html"
    stale.write_text("old", encoding="utf-8")
    report_dir = destination / "lim"
    report_dir.mkdir()
    (report_dir / "obsolete.html").write_text("gone", encoding="utf-8")

    published = _publish_coverage_report(
        str(destination),
        "coverage--lim.html",
        [str(index), str(detail)],
    )

    assert published == [str(index), str(detail)]
    assert (destination / "lim" / "coverage--lim.html").read_text(encoding="utf-8") == "index"
    assert (destination / "lim" / "test.gcc15.coverage.lim.lim.cpp.abc.html").is_file()
    assert not (destination / "lim" / "obsolete.html").exists()
    assert not stale.exists()
