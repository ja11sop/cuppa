#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for docs URL integrity (versionless /cuppa/… must not ship)."""

from pathlib import Path

import pytest

from scripts.check_docs_urls import (
    check,
    check_built_site,
    check_header_partial,
    check_markdown_absolute_urls,
    check_sources,
)


pytestmark = pytest.mark.unit


GOOD_HEADER = """
<a href="{{{siteRootPath}}}/cuppa/latest/contributing.html">Contributing</a>
<a href="{{{siteRootPath}}}/cuppa/latest/install.html">Install</a>
"""

BAD_HEADER = """
<a href="{{{siteRootPath}}}/cuppa/contributing.html">Contributing</a>
"""


def test_good_header_passes():
    assert check_header_partial(GOOD_HEADER, label="header") == []


def test_versionless_header_fails():
    found = check_header_partial(BAD_HEADER, label="header")
    assert len(found) == 1
    assert "contributing.html" in found[0]
    assert "latest" in found[0]


def test_markdown_allows_latest_and_next():
    text = (
        "[a](https://ja11sop.github.io/cuppa/cuppa/latest/install.html) "
        "[b](https://ja11sop.github.io/cuppa/cuppa/next/contributing.html)"
    )
    assert check_markdown_absolute_urls(text, label="README.md") == []


def test_markdown_rejects_versionless_component_url():
    text = "[x](https://ja11sop.github.io/cuppa/cuppa/contributing.html)"
    found = check_markdown_absolute_urls(text, label="README.md")
    assert len(found) == 1
    assert "contributing.html" in found[0]


def test_built_site_rejects_versionless_navbar(tmp_path: Path):
    page = tmp_path / "cuppa" / "latest" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        '<a class="navbar-item" href="../../cuppa/contributing.html">Contributing</a>\n',
        encoding="utf-8",
    )
    found = check_built_site(tmp_path)
    assert found
    assert "contributing.html" in found[0]


def test_built_site_accepts_latest_navbar(tmp_path: Path):
    page = tmp_path / "cuppa" / "latest" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        '<a class="navbar-item" href="../../cuppa/latest/contributing.html">Contributing</a>\n',
        encoding="utf-8",
    )
    assert check_built_site(tmp_path) == []


def test_repository_sources_are_clean():
    found = check_sources()
    assert not found, "\n".join(found)


def test_check_combines_sources_and_built_site(tmp_path: Path):
    # Sources from the real repo should be clean; inject a bad built page.
    page = tmp_path / "index.html"
    page.write_text(
        'href="../../cuppa/install.html"',
        encoding="utf-8",
    )
    found = check(built_site=tmp_path)
    assert any("install.html" in item for item in found)
