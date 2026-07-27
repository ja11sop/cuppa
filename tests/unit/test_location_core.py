#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os
import tarfile
import zipfile
from urllib.parse import urlparse

import pytest

from cuppa.location import (
    Location,
    LocationException,
    get_common_top_directory_under,
    path_leaf,
)
from cuppa.scms import git as git_scm


pytestmark = pytest.mark.unit


def test_path_leaf():
    assert path_leaf("/tmp/foo/bar.txt") == "bar.txt"
    assert path_leaf("bar.txt") == "bar.txt"


def test_get_scm_system_and_info_git_with_branch():
    scm, vc_type, repo, versioning = Location.get_scm_system_and_info(
        "git+https://example.com/org/repo.git@feature"
    )
    assert scm is git_scm.Git
    assert vc_type == "git"
    assert repo == "https://example.com/org/repo.git"
    assert versioning == "feature"


def test_get_scm_system_and_info_svn_style():
    scm, vc_type, repo, versioning = Location.get_scm_system_and_info(
        "svn+https://example.com/svn/trunk@123"
    )
    assert vc_type == "svn"
    assert repo == "https://example.com/svn/trunk"
    assert versioning == "123"
    assert scm is not None


def test_get_scm_system_and_info_non_vcs_path():
    assert Location.get_scm_system_and_info("/opt/local/lib") == (None, None, None, None)
    assert Location.get_scm_system_and_info("https://example.com/archive.zip") == (
        None,
        None,
        None,
        None,
    )


def test_replace_sconstruct_anchor(tmp_path):
    location = Location.__new__(Location)
    location._cuppa_env = {"sconstruct_dir": str(tmp_path)}
    assert location.replace_sconstruct_anchor("#include") == os.path.join(
        str(tmp_path), "include"
    )
    assert location.replace_sconstruct_anchor("/abs/path") == "/abs/path"


def test_url_is_download_archive_url(monkeypatch):
    monkeypatch.setattr(
        "cuppa.location.pip_is_archive_file",
        lambda path: path.endswith(".zip") or path.endswith(".tar.gz"),
    )
    assert Location.url_is_download_archive_url("https://ex.com/pkg.zip") is True
    assert Location.url_is_download_archive_url("https://ex.com/pkg.zip/download") is True
    assert Location.url_is_download_archive_url("https://ex.com/pkg") is False


def test_folder_name_from_path_file_and_dir(tmp_path):
    archive = tmp_path / "mylib-1.2.3.tar.gz"
    archive.write_bytes(b"not-a-real-archive")
    include = tmp_path / "include"
    include.mkdir()

    location = Location.__new__(Location)
    location._cuppa_env = {
        "sconstruct_dir": str(tmp_path),
        "abs_sconscript_dir": str(tmp_path),
    }
    location._name_hint = None

    assert location.folder_name_from_path(str(archive)) == "mylib-1.2.3"
    assert location.folder_name_from_path(str(include)) == "include"

    url_name = location.folder_name_from_path(
        urlparse("https://example.com/org/widget.git")
    )
    assert "https" in url_name
    assert "example.com" in url_name


def test_expand_secret_registers_mask(monkeypatch):
    monkeypatch.setenv("CUPPA_UNIT_SECRET", "s3cr3t-value")
    from cuppa.log import mask_secrets

    plain = "git+https://example.com/$CUPPA_UNIT_SECRET/repo.git"
    expanded = Location.expand_secret(plain)
    assert "s3cr3t-value" in expanded
    assert "s3cr3t-value" not in mask_secrets(expanded)


def test_ver_rev_summary_variants():
    location = Location.__new__(Location)
    assert location.ver_rev_summary("main", "abc123", "https://x/y") == (
        "main rev. abc123",
        "abc123",
    )
    assert location.ver_rev_summary(None, "abc123", "https://x/y") == (
        "rev. abc123",
        "abc123",
    )
    assert location.ver_rev_summary("main", None, "https://x/y") == ("main", None)
    version, revision = location.ver_rev_summary(
        None, None, "https://example.com/pkg-1.0.tar.gz"
    )
    assert version == "pkg-1.0"
    assert revision == "not under version control"


def test_remove_common_top_directory_under(tmp_path):
    nested = tmp_path / "top" / "a.txt"
    nested.parent.mkdir()
    nested.write_text("hi", encoding="utf-8")
    assert Location.remove_common_top_directory_under(str(tmp_path)) is True
    assert (tmp_path / "a.txt").is_file()
    assert not (tmp_path / "top").exists()

    (tmp_path / "one.txt").write_text("1", encoding="utf-8")
    (tmp_path / "two.txt").write_text("2", encoding="utf-8")
    assert Location.remove_common_top_directory_under(str(tmp_path)) is False


def test_remove_common_top_directory_under_empty(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(LocationException):
        Location.remove_common_top_directory_under(str(empty))


def test_get_common_top_directory_under(tmp_path):
    only = tmp_path / "solo"
    only.mkdir()
    assert get_common_top_directory_under(str(tmp_path)) == "solo"
    (tmp_path / "extra.txt").write_text("x", encoding="utf-8")
    assert get_common_top_directory_under(str(tmp_path)) is None


def test_extract_zip_strips_top_directory(tmp_path):
    archive = tmp_path / "pkg.zip"
    target = tmp_path / "out"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("pkg-1.0/readme.txt", "hello")
        zf.writestr("pkg-1.0/src/a.cpp", "int a;")

    Location.extract(str(archive), str(target))
    assert (target / "readme.txt").read_text(encoding="utf-8") == "hello"
    assert (target / "src" / "a.cpp").is_file()
    assert not (target / "pkg-1.0").exists()


def test_extract_tar(tmp_path):
    # Build from a real tree so members get readable modes (manual TarInfo
    # defaults to mode 0, which breaks shutil.move on some CI runners).
    source = tmp_path / "source"
    wrapped = source / "wrapped"
    wrapped.mkdir(parents=True)
    (wrapped / "file.txt").write_text("payload", encoding="utf-8")

    archive = tmp_path / "pkg.tar"
    target = tmp_path / "out"
    with tarfile.open(archive, "w") as tf:
        tf.add(str(wrapped), arcname="wrapped")

    Location.extract(str(archive), str(target))
    assert (target / "file.txt").read_text(encoding="utf-8") == "payload"
