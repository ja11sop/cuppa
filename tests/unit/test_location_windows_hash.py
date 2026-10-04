#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import platform

import pytest

from cuppa.location import Location


@pytest.mark.unit
def test_windows_folder_name_from_path_hashes_string(monkeypatch, tmp_path):
    """Regression: hashlib requires bytes on Python 3; Windows shortens folder names via MD5."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")

    include = tmp_path / "include"
    include.mkdir()

    location = Location.__new__(Location)
    location._cuppa_env = {
        "sconstruct_dir": str(tmp_path),
        "abs_sconscript_dir": str(tmp_path),
    }
    location._name_hint = None
    location.url_replacement_char = "+"

    folder = location.folder_name_from_path(str(include))
    assert isinstance(folder, str)
    assert len(folder) > 0
    # path prefix (up to 8 chars) + 8-char digest suffix
    assert len(folder) <= 16


@pytest.mark.unit
def test_windows_folder_hash_ignores_terse_name_hint(monkeypatch):
    """``name_hint`` is terse-only; hashed MAX_PATH names stay URL-derived."""
    from urllib.parse import urlparse

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    location = Location.__new__(Location)
    location._cuppa_env = {}
    location.url_replacement_char = "_"
    url = urlparse("git+https://example.com/org/widget.git@master")
    location._name_hint = None
    unnamed = location.folder_name_from_path(url)
    location._name_hint = "widget"
    named = location.folder_name_from_path(url)
    assert unnamed == named
    assert not named.startswith( "widget" )
    assert len( unnamed ) == 16
