import pytest

from cuppa.core.dependency_identity import (
    boost_archive_extension_from_folder,
    boost_remote_from_folder,
    gitlab_archive_name,
)


pytestmark = pytest.mark.unit


def test_boost_remote_from_folder_preserves_zip_extension():
    folder = "https_archives.boost.io__release_1.91.0_source_boost_1_91_0.zip"
    assert boost_archive_extension_from_folder(folder) == ".zip"
    assert boost_remote_from_folder(folder) == (
        "https://archives.boost.io/release/1.91.0/source/boost_1_91_0.zip"
    )


def test_boost_remote_from_folder_preserves_tar_gz_extension():
    folder = "https_archives.boost.io__release_1.91.0_source_boost_1_91_0.tar.gz"
    assert boost_archive_extension_from_folder(folder) == ".tar.gz"
    assert boost_remote_from_folder(folder) == (
        "https://archives.boost.io/release/1.91.0/source/boost_1_91_0.tar.gz"
    )


def test_boost_remote_fallback_extension_follows_platform(monkeypatch):
    folder = "https_archives.boost.io__release_1.91.0_source_boost_1_91_0"
    monkeypatch.setattr(
        "cuppa.core.dependency_identity.platform.system",
        lambda: "Windows",
    )
    assert boost_archive_extension_from_folder(folder) == ".zip"
    assert boost_remote_from_folder(folder).endswith(".zip")

    monkeypatch.setattr(
        "cuppa.core.dependency_identity.platform.system",
        lambda: "Linux",
    )
    assert boost_archive_extension_from_folder(folder) == ".tar.gz"
    assert boost_remote_from_folder(folder).endswith(".tar.gz")


def test_gitlab_archive_name_uses_platform_extension(monkeypatch):
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.os_release_id",
        lambda: "windows",
    )
    assert gitlab_archive_name("boost", "vc143_rel_x86_64_cxx17") == (
        "boost_windows_vc143_rel_x86_64_cxx17.zip"
    )

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Linux",
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.os_release_id",
        lambda: "debian",
    )
    assert gitlab_archive_name("boost", "gcc153_rel_x86_64_cxx2c") == (
        "boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz"
    )
