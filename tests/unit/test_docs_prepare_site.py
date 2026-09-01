#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for docs site prepare helpers (tag → Antora version rewrite)."""

from pathlib import Path

import pytest

from scripts.docs_prepare_site import parse_release_tag, rewrite_antora_yml


pytestmark = pytest.mark.unit


def test_parse_release_tag_with_v_prefix():
    tag, minor, display = parse_release_tag("v1.8.2")
    assert tag == "v1.8.2"
    assert minor == "1.8"
    assert display == "1.8.2"


def test_parse_release_tag_without_v_prefix():
    tag, minor, display = parse_release_tag("2.0.0")
    assert tag == "v2.0.0"
    assert minor == "2.0"
    assert display == "2.0.0"


def test_parse_release_tag_rejects_prerelease_suffix():
    with pytest.raises(ValueError, match="must look like"):
        parse_release_tag("v1.9.0.dev")


def test_rewrite_antora_yml_sets_minor_and_display(tmp_path: Path):
    path = tmp_path / "antora.yml"
    path.write_text(
        "name: cuppa\n"
        "title: Cuppa\n"
        "version: ~\n"
        "start_page: ROOT:index.adoc\n",
        encoding="utf-8",
    )
    rewrite_antora_yml(path, version="1.8", display_version="1.8.2")
    text = path.read_text(encoding="utf-8")
    assert "version: '1.8'\n" in text
    assert "display_version: '1.8.2'\n" in text
    assert "version: ~" not in text


def test_rewrite_antora_yml_drops_prerelease(tmp_path: Path):
    path = tmp_path / "antora.yml"
    path.write_text(
        "name: cuppa\n"
        "title: Cuppa\n"
        "version: next\n"
        "prerelease: true\n"
        "start_page: ROOT:index.adoc\n",
        encoding="utf-8",
    )
    rewrite_antora_yml(path, version="1.8", display_version="1.8.2")
    text = path.read_text(encoding="utf-8")
    assert "version: '1.8'\n" in text
    assert "display_version: '1.8.2'\n" in text
    assert "prerelease" not in text
    assert "next" not in text
