"""Integration tests for --wipe-dependencies and --force-wipe-*."""

from pathlib import Path

import pytest

from cuppa.core.dependency_identity import gitlab_archive_name
from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct
from tests.integration.test_list_dependencies import own_home, strip_ansi
from tests.integration.test_purge_dependencies import _boost_package_sconstruct
from tests.integration.test_remove_dependencies import (
    _boost_stage_and_bin,
    _b2_toolset_token_for_selection,
    _json_payload,
)


pytestmark = pytest.mark.integration


def test_wipe_refuses_combined_remove_or_purge(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    (storage / "dependencies").mkdir(parents=True)
    write_sconstruct(project, body=_boost_package_sconstruct())

    with_remove = run_cuppa(
        project,
        "--offline",
        "--wipe-dependencies=boost_package",
        "--remove-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert with_remove.returncode != 0
    assert "do not combine" in strip_ansi(with_remove.stdout).lower()

    with_purge = run_cuppa(
        project,
        "--offline",
        "--force-wipe-dependencies=boost/1.86.0",
        "--purge-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert with_purge.returncode != 0
    assert "do not combine" in strip_ansi(with_purge.stdout).lower()


def test_wipe_boost_source_deletes_extract_and_download(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"
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

    dry = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "-n",
        "--boost-home={}".format(boost_home),
        "--wipe-dependencies=boost",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(dry)
    plain_dry = strip_ansi(dry.stdout)
    assert "Would wipe" in plain_dry or "would" in plain_dry.lower()
    assert boost_home.is_dir()
    assert archive.is_file()

    wiped = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--boost-home={}".format(boost_home),
        "--wipe-dependencies=boost",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(wiped)
    plain = strip_ansi(wiped.stdout)
    assert "Wiping" in plain or "wiped" in plain.lower() or "Removed" in plain
    assert "list-downloads" in plain
    assert "list-dependencies" in plain
    assert not boost_home.exists()
    assert not archive.exists()


def test_wipe_gitlab_selected_tarball_and_extract(tmp_path):
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

    wiped = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--wipe-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(wiped)
    plain = strip_ansi(wiped.stdout)
    assert "Wiping" in plain or "wiped" in plain.lower() or "Removed" in plain
    assert not selected_path.exists()
    assert not selected_archive.exists()
    assert leftover_archive.is_file()
    assert other.is_dir()


def _plant_boost_version(deps, downloads, folder, version_hpp_define, archive_name=None):
    home = deps / folder
    clean = home / "clean"
    clean.mkdir(parents=True)
    (clean / "boost").mkdir(parents=True)
    (clean / "boost" / "version.hpp").write_text(
        "#define BOOST_VERSION {}\n".format(version_hpp_define),
        encoding="utf-8",
    )
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / (archive_name or folder)
    archive.write_bytes(b"boost-" + folder.encode("utf-8"))
    return home, archive


def test_force_wipe_named_boost_versions_keeps_current(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"

    current, current_archive = _plant_boost_version(
            deps, downloads, "boost_1_91_0", "109100"
    )
    old_a, old_a_archive = _plant_boost_version(
            deps, downloads, "boost_1_86_0", "108600"
    )
    old_b, old_b_archive = _plant_boost_version(
            deps, downloads, "boost_1_87_0", "108700"
    )

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

    dry = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "-n",
        "--boost-home={}".format(current),
        "--force-wipe-dependencies=boost/1.86.0,boost/1.87.0",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(dry)
    assert old_a.is_dir() and old_b.is_dir() and current.is_dir()

    wiped = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--boost-home={}".format(current),
        "--force-wipe-dependencies=boost/1.86.0,boost/1.87.0",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(wiped)
    plain = strip_ansi(wiped.stdout)
    assert "Wiping" in plain or "Would wipe" in plain or "wiped" in plain.lower()
    assert not old_a.exists()
    assert not old_b.exists()
    assert not old_a_archive.exists()
    assert not old_b_archive.exists()
    assert current.is_dir()
    assert current_archive.is_file()


def test_force_wipe_wildcard_boost_versions_keeps_current(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"

    current, current_archive = _plant_boost_version(
            deps, downloads, "boost_1_91_0", "109100"
    )
    old_a, old_a_archive = _plant_boost_version(
            deps, downloads, "boost_1_86_0", "108600"
    )
    old_b, old_b_archive = _plant_boost_version(
            deps, downloads, "boost_1_87_0", "108700"
    )

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

    dry = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "-n",
        "--boost-home={}".format(current),
        "--force-wipe-dependencies=boost/1.8*",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(dry)
    plain_dry = strip_ansi(dry.stdout)
    assert "Would wipe" in plain_dry
    assert "boost_1_86_0" in plain_dry or "1.86" in plain_dry
    assert "boost_1_87_0" in plain_dry or "1.87" in plain_dry
    assert old_a.is_dir() and old_b.is_dir() and current.is_dir()

    wiped = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--boost-home={}".format(current),
        "--force-wipe-dependencies=boost/1.8*",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(wiped)
    assert not old_a.exists()
    assert not old_b.exists()
    assert not old_a_archive.exists()
    assert not old_b_archive.exists()
    assert current.is_dir()
    assert current_archive.is_file()


def test_force_wipe_unreferenced_deletes_old_boost_keeps_current(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"

    current, current_archive = _plant_boost_version(
            deps, downloads, "boost_source", "109100"
    )
    old, old_archive = _plant_boost_version(
            deps, downloads, "boost_1_90_0", "109000",
            archive_name="boost_1_90_0.tar.gz",
    )

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

    wiped = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--boost-home={}".format(current),
        "--force-wipe-unreferenced-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(wiped)
    plain = strip_ansi(wiped.stdout)
    assert "list-scope=unreferenced" in plain
    assert not old.exists()
    assert not old_archive.exists()
    assert current.is_dir()
    assert current_archive.is_file()
