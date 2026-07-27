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
    lines_of_code_format,
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
