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


def test_get_scm_system_and_info_windows_file_url_backslash_netloc():
    # urlparse puts drive-letter paths in netloc when written as file://C:\…
    scm, vc_type, repo, versioning = Location.get_scm_system_and_info(
        r"git+file://C:\Users\user\origin@master"
    )
    assert scm is git_scm.Git
    assert vc_type == "git"
    assert repo == "file:///C:/Users/user/origin"
    assert versioning == "master"


def test_get_scm_system_and_info_windows_file_uri_path():
    scm, vc_type, repo, versioning = Location.get_scm_system_and_info(
        "git+file:///C:/Users/user/origin@master"
    )
    assert scm is git_scm.Git
    assert repo == "file:///C:/Users/user/origin"
    assert versioning == "master"


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


def _location_with_retrieval_options(offline, clean):
    location = Location.__new__(Location)
    location._offline = offline
    location._cuppa_env = {"clean": clean}
    return location


def test_retrieval_disabled_reason_names_the_active_option():
    assert _location_with_retrieval_options(False, False).retrieval_disabled_reason() is None
    assert _location_with_retrieval_options(True, False).retrieval_disabled_reason() == "--offline"
    assert _location_with_retrieval_options(False, True).retrieval_disabled_reason() == "--clean"
    assert _location_with_retrieval_options(True, True).retrieval_disabled_reason() == "--offline"


def _repository_location(tmp_path, monkeypatch, offline, clean):
    monkeypatch.setattr("cuppa.location.pip_vcs.vcs.get_backend", lambda vc_type: object())

    location = _location_with_retrieval_options(offline, clean)
    location._cuppa_env["dump"] = False
    location._cuppa_env["location_match_current_branch"] = False
    location._cuppa_env["abs_build_root"] = str(tmp_path / "_build")
    location._supports_relative_versioning = False
    location._default_branch = None
    location._local_folder = "git_https_example.com_org_repo"

    return location, str(tmp_path / "not_downloaded")


def _clean_repository_location(tmp_path, monkeypatch):
    return _repository_location(tmp_path, monkeypatch, offline=False, clean=True)


def _get_local_directory_for_repository(location, missing):
    return location.get_local_directory_for_repository(
        "git+ssh://git@example.com/org/repo",
        None,
        urlparse("git+ssh://git@example.com/org/repo"),
        missing,
    )


def test_missing_local_directory_offline_reports_the_offline_option(tmp_path, monkeypatch):
    location, missing = _repository_location(tmp_path, monkeypatch, offline=True, clean=False)

    with pytest.raises(LocationException) as excinfo:
        _get_local_directory_for_repository(location, missing)

    message = str(excinfo.value)
    assert "--offline" in message
    assert "OFFLINE" not in message


def test_missing_local_directory_does_not_fail_a_clean(tmp_path, monkeypatch, caplog):
    location, missing = _clean_repository_location(tmp_path, monkeypatch)

    with caplog.at_level("DEBUG"):
        result = _get_local_directory_for_repository(location, missing)

    assert result == missing
    assert "--clean" in caplog.text
    assert [record.levelname for record in caplog.records if "--clean" in record.message] == ["INFO"]


def test_clean_warns_when_the_location_left_build_outputs(tmp_path, monkeypatch, caplog):
    location, missing = _clean_repository_location(tmp_path, monkeypatch)

    leftovers = tmp_path / "_build" / location._local_folder
    leftovers.mkdir(parents=True)

    with caplog.at_level("DEBUG"):
        result = _get_local_directory_for_repository(location, missing)

    assert result == missing
    assert [record.levelname for record in caplog.records if "--clean" in record.message] == ["WARNING"]
    assert str(leftovers) in caplog.text


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


def _select_location(tmp_path, default_branch="master", relative=True, match_branch=None):
    location = Location.__new__(Location)
    location._cuppa_env = {
        "clean": False,
        "dump": False,
        "location_match_current_branch": False,
        "location_match_branch": match_branch,
        "location_match_tag": None,
    }
    location._supports_relative_versioning = relative
    location._default_branch = default_branch
    location._current_branch = None
    location._current_revision = None
    Location._unqualified_duplicate_warned = set()
    return location, str(tmp_path / "git_https_example.com__org_repo.git")


def test_select_repository_directory_neither_uses_canonical(tmp_path):
    location, stem = _select_location(tmp_path)
    assert location._select_repository_directory(stem) == stem + "@master"


def test_select_repository_directory_unqualified_only(tmp_path):
    location, stem = _select_location(tmp_path)
    os.mkdir(stem)
    assert location._select_repository_directory(stem) == stem


def test_select_repository_directory_canonical_only(tmp_path):
    location, stem = _select_location(tmp_path)
    os.mkdir(stem + "@master")
    assert location._select_repository_directory(stem) == stem + "@master"


def test_select_repository_directory_both_prefers_canonical_and_warns(tmp_path, caplog):
    location, stem = _select_location(tmp_path)
    os.mkdir(stem)
    os.mkdir(stem + "@master")
    with caplog.at_level("WARNING"):
        chosen = location._select_repository_directory(stem)
    assert chosen == stem + "@master"
    assert "removal candidate" in caplog.text
    # Second call does not warn again.
    caplog.clear()
    with caplog.at_level("WARNING"):
        assert location._select_repository_directory(stem) == stem + "@master"
    assert "removal candidate" not in caplog.text


def test_select_repository_directory_url_already_qualified_is_not_double_suffixed(tmp_path, caplog):
    location, stem = _select_location(tmp_path)
    qualified = stem + "@master"
    os.mkdir(stem)
    os.mkdir(qualified)
    with caplog.at_level("WARNING"):
        chosen = location._select_repository_directory(qualified)
    assert chosen == qualified
    assert "removal candidate" in caplog.text


def test_select_repository_directory_no_default_branch_stays_unqualified(tmp_path):
    location, stem = _select_location(tmp_path, default_branch=None, relative=False)
    assert location._select_repository_directory(stem) == stem


def test_select_repository_directory_match_branch_relative(tmp_path):
    location, stem = _select_location(tmp_path, match_branch="feature_x")
    assert location._select_repository_directory(stem) == stem + "@feature_x"


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
