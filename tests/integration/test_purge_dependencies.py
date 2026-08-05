"""Integration tests for --purge-dependencies / --purge-all-dependencies."""

from pathlib import Path

import pytest

from cuppa.core.dependency_identity import gitlab_archive_name
from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct
from tests.integration.test_list_dependencies import own_home, strip_ansi
from tests.integration.test_remove_dependencies import (
    _boost_stage_and_bin,
    _b2_toolset_token_for_selection,
    _json_payload,
)


pytestmark = pytest.mark.integration


def _boost_package_sconstruct():
    return """\
import cuppa

Boost = cuppa.package_dependency(
    'boost_package',
    package_manager='gitlab',
    registry='https://gitlab.example/api/v4/projects/1',
    package='boost',
    version='1.91',
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Boost],
    default_dependencies=['boost_package'],
)
"""


def test_purge_refuses_combined_remove_flags(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    (storage / "dependencies").mkdir(parents=True)
    write_sconstruct(project, body=_boost_package_sconstruct())
    result = run_cuppa(
        project,
        "--offline",
        "--purge-dependencies=boost_package",
        "--remove-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert result.returncode != 0
    plain = strip_ansi(result.stdout + (result.stderr or ""))
    assert "do not combine" in plain


def test_purge_gitlab_selected_tarball_and_extract(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"
    deps.mkdir(parents=True)
    downloads.mkdir(parents=True)
    write_sconstruct(project, body=_boost_package_sconstruct())

    listed = run_cuppa(
        project,
        "--offline",
        "--list-dependencies",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    payload = _json_payload(listed)
    missing = [
            entry for entry in payload["entries"]
            if entry.get("dependency") == "boost_package" and entry.get("state") == "missing"
    ]
    assert missing, payload["entries"]
    selected_path = Path(missing[0]["path"])
    tool_variant = missing[0].get("tool_variant")
    assert tool_variant
    selected_path.mkdir(parents=True)
    (selected_path / "include").mkdir(parents=True)
    (selected_path / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")

    archive = gitlab_archive_name("boost", tool_variant)
    pkg_dir = downloads / "packages" / "boost" / "1.91"
    pkg_dir.mkdir(parents=True)
    selected_archive = pkg_dir / archive
    selected_archive.write_bytes(b"pkg-bytes")
    leftover_name = "boost_debian_clang999_rel_x86_64_cxx2c.tar.gz"
    if leftover_name == archive:
        leftover_name = "boost_debian_gcc999_rel_x86_64_cxx2c.tar.gz"
    leftover_archive = pkg_dir / leftover_name
    leftover_archive.write_bytes(b"other-pkg")

    other_variant = "clang999_dbg_x86_64_cxx2c"
    if other_variant == tool_variant:
        other_variant = "gcc999_dbg_x86_64_cxx2c"
    other = deps / other_variant / "boost" / "1.91"
    other.mkdir(parents=True)
    (other / "include").mkdir(parents=True)
    (other / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")

    purged = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--purge-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(purged)
    plain = strip_ansi(purged.stdout)
    assert "Removed" in plain or "removed" in plain
    assert archive in plain
    assert "[E]" in plain
    assert leftover_name in plain
    assert "list-downloads" in plain
    assert not selected_path.exists()
    assert not selected_archive.exists()
    assert leftover_archive.is_file()
    assert other.is_dir()
    assert (downloads / "packages" / "boost" / "1.91").is_dir()


def test_purge_dry_run_changes_nothing(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"
    deps.mkdir(parents=True)
    downloads.mkdir(parents=True)
    write_sconstruct(project, body=_boost_package_sconstruct())

    listed = run_cuppa(
        project,
        "--offline",
        "--list-dependencies",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    payload = _json_payload(listed)
    missing = [
            entry for entry in payload["entries"]
            if entry.get("dependency") == "boost_package" and entry.get("state") == "missing"
    ]
    selected_path = Path(missing[0]["path"])
    tool_variant = missing[0]["tool_variant"]
    selected_path.mkdir(parents=True)
    (selected_path / "include").mkdir(parents=True)
    (selected_path / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")
    archive = gitlab_archive_name("boost", tool_variant)
    pkg_dir = downloads / "packages" / "boost" / "1.91"
    pkg_dir.mkdir(parents=True)
    selected_archive = pkg_dir / archive
    selected_archive.write_bytes(b"pkg-bytes")

    dry = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "-n",
        "--purge-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(dry)
    plain = strip_ansi(dry.stdout)
    assert "Would remove" in plain or "would rm" in plain.lower()
    assert selected_path.is_dir()
    assert selected_archive.is_file()


def test_purge_boost_source_deletes_download_keeps_extract(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"
    # Same extract layout as the remove storage_clean test; download basename matches
    # find_cached_download(archive, path=boost-home).
    boost_home = deps / "boost_source"
    clean = boost_home / "clean"
    dbg, bindir, _tc_name, _abi = _boost_stage_and_bin(clean, "debug")
    token = _b2_toolset_token_for_selection()
    selected_bin = bindir / "boost" / "bin.v2" / "libs" / "system" / token / "debug"
    dbg.mkdir(parents=True)
    selected_bin.mkdir(parents=True)
    (dbg / "lib").mkdir()
    (dbg / "lib" / "libboost_system.a").write_text("x", encoding="utf-8")
    (selected_bin / "obj").write_text("x", encoding="utf-8")
    (clean / "boost").mkdir(parents=True)
    (clean / "boost" / "version.hpp").write_text(
        "#ifndef BOOST_VERSION_HPP\n"
        "#define BOOST_VERSION_HPP\n"
        "#define BOOST_VERSION 109100\n"
        "#define BOOST_LIB_VERSION \"1_91\"\n"
        "#endif\n",
        encoding="utf-8",
    )
    downloads.mkdir(parents=True)
    archive = downloads / "boost_source"
    archive.write_bytes(b"boost-source-tarball")

    write_sconstruct(
        project,
        body="""\
import cuppa

cuppa.run(
    default_variants=['dbg'],
    default_dependencies=['boost'],
)
""",
    )

    purged = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--boost-home={}".format(boost_home),
        "--purge-dependencies=boost",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(purged)
    plain = strip_ansi(purged.stdout)
    assert "Removed" in plain or "removed" in plain.lower()
    assert "list-downloads" in plain
    assert "source assets" in plain
    assert boost_home.is_dir()
    assert (clean / "boost" / "version.hpp").is_file()
    assert not dbg.exists()
    assert not selected_bin.exists()
    assert not archive.exists()


def test_purge_develop_skips_working_copy_but_may_delete_download(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    downloads = storage / "downloads"
    (storage / "dependencies").mkdir(parents=True)
    downloads.mkdir(parents=True)
    develop = tmp_path / "coding" / "widget"
    develop.mkdir(parents=True)
    (develop / "include").mkdir()
    (develop / "include" / "w.hpp").write_text("//\n", encoding="utf-8")
    archive = downloads / "git_https_example.com__org_widget.git@master"
    archive.write_bytes(b"widget-archive")

    write_sconstruct(
        project,
        body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='git+https://example.com/org/widget.git@master',
    develop={develop!r},
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Widget],
    default_dependencies=['widget'],
)
""".format(develop=str(develop)),
    )

    purged = run_cuppa(
        project,
        "--offline",
        "--develop",
        "--purge-dependencies=widget",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(purged)
    plain = strip_ansi(purged.stdout)
    assert "develop" in plain.lower() or "Skipped" in plain
    assert develop.is_dir()
    assert (develop / "include" / "w.hpp").is_file()
