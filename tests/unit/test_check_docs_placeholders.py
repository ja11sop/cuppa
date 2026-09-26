#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for authored-docs placeholder policy (no U+2026)."""

from pathlib import Path

import pytest

from scripts.check_docs_placeholders import check as check_placeholders


pytestmark = pytest.mark.unit


def test_clean_tree_has_no_unicode_ellipsis_outside_samples(tmp_path: Path):
    pages = tmp_path / "docs" / "modules" / "ROOT" / "pages"
    pages.mkdir(parents=True)
    (pages / "ok.adoc").write_text("Use `<abi>` or `...` for cuts.\n", encoding="utf-8")
    samples = tmp_path / "docs" / "modules" / "ROOT" / "partials" / "samples"
    samples.mkdir(parents=True)
    (samples / "list.txt").write_text("boost_\u2026_gcc.tar.gz\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        "Do **not** use the Unicode ellipsis character (`\u2026`, U+2026).\n",
        encoding="utf-8",
    )
    assert check_placeholders(tmp_path) == []


def test_unicode_ellipsis_in_page_fails(tmp_path: Path):
    pages = tmp_path / "docs" / "modules" / "ROOT" / "pages"
    pages.mkdir(parents=True)
    (pages / "bad.adoc").write_text("See `gcc15`, `\u2026`.\n", encoding="utf-8")
    found = check_placeholders(tmp_path)
    assert len(found) == 1
    assert "bad.adoc:1:" in found[0]
    assert "U+2026" in found[0]


def test_repository_authored_docs_are_clean():
    found = check_placeholders()
    assert not found, "\n".join(found)
