"""Integration tests for --remove-dependencies (Slice D)."""

import json
import platform
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from cuppa.core.dependency_storage import split_location_folder_name
from cuppa.dependencies.boost.library_naming import (
    directory_from_abi_flag,
    stage_directory,
)
from cuppa.location import Location
from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct
from tests.helpers.toolchains import default_toolchain_flags
from tests.integration.test_list_dependencies import own_home, strip_ansi


pytestmark = pytest.mark.integration


def _json_payload(result):
    match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
    assert match, result.stdout
    return json.loads(match.group(0))


def location_cache_folder_name(location_url, tmp_path):
    """Dependencies-root folder name cuppa would use for ``location_url`` on this OS.

    Windows shortens URL folder names with an MD5 suffix (MAX_PATH); Linux keeps the
    full encoded URL. Tests that plant location trees must use this helper so remove
    / list resolve the same path cuppa expects.
    """
    location = Location.__new__(Location)
    location._cuppa_env = {
        "sconstruct_dir": str(tmp_path),
        "abs_sconscript_dir": str(tmp_path),
    }
    location._name_hint = None
    location.url_replacement_char = "_"
    return location.folder_name_from_path(urlparse(location_url))


def _selection_toolchain_layout():
    """Return (toolchain_name, abi_flag) matching ``run_cuppa``'s default toolchain."""
    flags = default_toolchain_flags()
    family = "gcc"
    for flag in flags:
        if str(flag).startswith("--toolchains="):
            family = str(flag).split("=", 1)[1].split(",")[0].strip()
            break
    if family.startswith("clang") or family in ("cl", "vc", "msvc"):
        if family in ("cl", "vc", "msvc"):
            pytest.skip("Boost archive-clean layout is exercised on gcc/clang")
        from cuppa.toolchains.clang import Clang

        reported = Clang.version_from_command("clang++")
        if not reported:
            reported = Clang.version_from_command("clang")
        assert reported, "clang version not detected"
        major = reported["major"]
        if major >= 17:
            abi = "-std=c++2c"
        elif major >= 13:
            abi = "-std=c++2b"
        elif major >= 6:
            abi = "-std=c++2a"
        else:
            abi = "-std=c++1z"
        return reported["name"], abi

    from cuppa.toolchains.gcc import Gcc

    reported = Gcc.version_from_command("g++ --version", "gcc")
    assert reported, "g++ version not detected"
    major = reported["major"]
    if major >= 14:
        abi = "-std=c++2c"
    elif major >= 11:
        abi = "-std=c++2b"
    elif major >= 10:
        abi = "-std=c++2a"
    else:
        abi = "-std=c++1z"
    return reported["name"], abi


def _boost_stage_and_bin(home, boost_variant):
    """Absolute stage leaf and ``bin.<abi>`` under Boost ``clean``/``patched`` home."""
    class _Toolchain(object):
        def __init__(self, name):
            self._name = name

        def name(self):
            return self._name

    tc_name, abi = _selection_toolchain_layout()
    arch = platform.machine()
    stage = Path(home) / stage_directory(_Toolchain(tc_name), boost_variant, arch, abi)
    bindir = Path(home) / ("bin." + (directory_from_abi_flag(abi) or ""))
    return stage, bindir, tc_name, abi


def _b2_toolset_token_for_selection():
    from cuppa.dependencies.boost.library_naming import b2_build_dir_toolset_token

    tc_name, _abi = _selection_toolchain_layout()
    family = "gcc"
    major = 15
    if tc_name.startswith("clang"):
        family = "clang"
        major = int(tc_name.replace("clang", "")[:2] or "21")
    elif tc_name.startswith("gcc"):
        major = int(tc_name.replace("gcc", "")[:2] or "15")

    class _TC(object):
        def __init__(self):
            self._reported_version = {"major": major, "minor": 0}

        def name(self):
            return tc_name

        def toolset_name(self):
            return family

        def version(self):
            return "{}.0".format(major)

        def cxx_version(self):
            return str(major)

    return b2_build_dir_toolset_token(_TC())


def test_remove_dependencies_unknown_name(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    (storage / "dependencies").mkdir(parents=True)
    write_sconstruct(
        project,
        body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='git+https://example.com/org/widget.git@master',
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Widget],
    default_dependencies=['widget'],
)
""",
    )
    removed = run_cuppa(
        project,
        "--offline",
        "--remove-dependencies=widgt",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert removed.returncode != 0
    plain = strip_ansi(removed.stdout + (removed.stderr or ""))
    assert "is not a used dependency" in plain
    assert "widgt" in plain
    assert "Collating dependency tree" in plain
    assert "Known dependencies which can be removed" in plain
    assert "DEPENDENCY" in plain
    assert "widget" in plain


def test_remove_rejects_builtin_boost_when_only_package_declared(tmp_path):
    """Auto-registered ``boost`` is not removable unless the project uses it."""
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    archive = deps / "https_archives.boost.io__release_1.91.0_source_boost_1_91_0.tar.gz"
    archive.mkdir(parents=True)
    (archive / "boost").mkdir()
    (archive / "boost" / "version.hpp").write_text("//\n", encoding="utf-8")

    write_sconstruct(
        project,
        body="""\
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
""",
    )
    removed = run_cuppa(
        project,
        "--offline",
        "-n",
        "--remove-dependencies=boost",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert removed.returncode != 0
    plain = strip_ansi(removed.stdout + (removed.stderr or ""))
    assert "is not a used dependency" in plain
    assert "boost" in plain
    assert "Known dependencies which can be removed" in plain
    assert "boost_package" in plain
    assert "DEPENDENCY" in plain
    assert archive.is_dir()


def test_remove_location_keeps_sibling_branch(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    master_url = "git+https://example.com/org/widget.git@master"
    feature_url = "git+https://example.com/org/widget.git@feature_x"
    master_name = location_cache_folder_name(master_url, tmp_path)
    feature_name = location_cache_folder_name(feature_url, tmp_path)
    master = deps / master_name
    feature = deps / feature_name
    master.mkdir(parents=True)
    feature.mkdir(parents=True)
    (master / "src").mkdir()
    (master / "src" / "a.cpp").write_text("int a;\n", encoding="utf-8")
    (feature / "src").mkdir()
    (feature / "src" / "b.cpp").write_text("int b;\n", encoding="utf-8")

    # Sibling leftover reporting needs a shared stem (name before @branch). On Windows,
    # URL folder names are hashed including the @branch, so stems diverge and leftovers
    # are not detected — the other tree must still be left on disk.
    master_stem, _ = split_location_folder_name(master_name)
    feature_stem, _ = split_location_folder_name(feature_name)
    siblings_share_stem = master_stem == feature_stem

    write_sconstruct(
        project,
        body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='git+https://example.com/org/widget.git@master',
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Widget],
    default_dependencies=['widget'],
)
""",
    )

    dry = run_cuppa(
        project,
        "--offline",
        "-n",
        "--remove-dependencies=widget",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(dry)
    plain = strip_ansi(dry.stdout)
    assert "Would remove" in plain or "would rm" in plain.lower()
    assert master.is_dir()
    assert feature.is_dir()

    removed = run_cuppa(
        project,
        "--offline",
        "--remove-dependencies=widget",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "Removed" in plain
    assert master_name in plain
    assert "LAST USED" in plain
    assert not master.exists()
    assert feature.is_dir()
    assert "list-dependencies" in plain
    if siblings_share_stem:
        assert "Leaving" in plain
        assert "as shown" in plain
        assert "feature_x" in plain or "@feature_x" in plain
        # Leftover leaf uses the identity label, not the raw cache folder name.
        assert "widget / @feature_x" in plain


def test_remove_develop_skips_working_copy(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    (storage / "dependencies").mkdir(parents=True)
    develop = tmp_path / "coding" / "widget"
    develop.mkdir(parents=True)
    (develop / "include").mkdir()
    (develop / "include" / "w.hpp").write_text("//\n", encoding="utf-8")

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

    removed = run_cuppa(
        project,
        "--offline",
        "--develop",
        "--remove-dependencies=widget",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "develop" in plain.lower() or "Skipped" in plain
    assert develop.is_dir()
    assert (develop / "include" / "w.hpp").is_file()


def test_remove_gitlab_package_keeps_other_toolchain(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    deps.mkdir(parents=True)

    write_sconstruct(
        project,
        body="""\
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
""",
    )

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
    selected_path = missing[0]["path"]
    tool_variant = missing[0].get("tool_variant")
    assert tool_variant
    assert selected_path

    from pathlib import Path
    selected = Path(selected_path)
    selected.mkdir(parents=True)
    (selected / "include").mkdir(parents=True)
    (selected / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")

    other_variant = "clang999_dbg_x86_64_cxx2c"
    if other_variant == tool_variant:
        other_variant = "gcc999_dbg_x86_64_cxx2c"
    other = deps / other_variant / "boost" / "1.91"
    other.mkdir(parents=True)
    (other / "include").mkdir(parents=True)
    (other / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")

    removed = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--remove-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "Removed" in plain or "removed" in plain
    assert not selected.exists()
    assert other.is_dir()
    assert "Leaving" in plain
    assert "as shown" in plain
    assert other_variant in plain or str(other.relative_to(deps)).replace("\\", "/") in plain


def test_remove_multiple_toolchains(tmp_path):
    """--toolchains=gcc,clang removes each selected package variant."""
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    deps.mkdir(parents=True)

    write_sconstruct(
        project,
        body="""\
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
""",
    )

    def missing_path(toolchains):
        listed = run_cuppa(
            project,
            "--offline",
            "--list-dependencies",
            "--list-format=json",
            "--toolchains={}".format(toolchains),
            "--storage-root={}".format(storage),
            extra_env=own_home(tmp_path),
        )
        if listed.returncode != 0:
            return None
        payload = _json_payload(listed)
        missing = [
                entry for entry in payload["entries"]
                if entry.get("dependency") == "boost_package"
                and entry.get("state") == "missing"
        ]
        if not missing:
            return None
        return missing[0]["path"], missing[0].get("tool_variant")

    gcc_info = missing_path("gcc")
    clang_info = missing_path("clang")
    if not gcc_info or not clang_info:
        pytest.skip("gcc and clang toolchains required for multi-toolchain removal test")
    if gcc_info[1] == clang_info[1]:
        pytest.skip("gcc and clang resolved to the same tool_variant")

    from pathlib import Path
    paths = []
    for path_str, _variant in (gcc_info, clang_info):
        path = Path(path_str)
        path.mkdir(parents=True)
        (path / "include").mkdir(parents=True)
        (path / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")
        paths.append(path)

    # Single invocation must resolve both package extracts.
    listed_both = run_cuppa(
        project,
        "--offline",
        "--list-dependencies",
        "--list-format=json",
        "--toolchains=gcc,clang",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed_both)
    both_payload = _json_payload(listed_both)
    boost_paths = {
            entry["path"]
            for entry in both_payload["entries"]
            if entry.get("dependency") == "boost_package"
    }
    assert Path(gcc_info[0]) in {Path(p) for p in boost_paths}
    assert Path(clang_info[0]) in {Path(p) for p in boost_paths}

    removed = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--toolchains=gcc,clang",
        "--remove-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "Removed" in plain or "removed" in plain
    for path in paths:
        assert not path.exists(), path
    assert gcc_info[1] in plain
    assert clang_info[1] in plain
    assert "2 tree" in plain or "2 trees" in plain or "Removed 2" in plain


def test_remove_boost_cleans_selected_variant_products(tmp_path):
    """Source Boost with storage_clean removes stage/toolset bin products, not the extract."""
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    # --boost-home is the extract root; Boost.local() is extract/clean.
    boost_home = deps / "boost_source"
    clean = boost_home / "clean"
    dbg, bindir, tc_name, _abi = _boost_stage_and_bin(clean, "debug")
    rel, _, _, _ = _boost_stage_and_bin(clean, "release")
    token = _b2_toolset_token_for_selection()
    other_token = "gcc-15" if token.startswith("clang") else "clang-linux-21"
    selected_bin = bindir / "boost" / "bin.v2" / "libs" / "system" / token / "debug"
    other_bin = bindir / "boost" / "bin.v2" / "libs" / "system" / other_token / "debug"
    dbg.mkdir(parents=True)
    rel.mkdir(parents=True)
    selected_bin.mkdir(parents=True)
    other_bin.mkdir(parents=True)
    (dbg / "lib").mkdir()
    (dbg / "lib" / "libboost_system.a").write_text("x", encoding="utf-8")
    (rel / "lib").mkdir()
    (rel / "lib" / "libboost_system.a").write_text("x", encoding="utf-8")
    (selected_bin / "obj").write_text("x", encoding="utf-8")
    (other_bin / "obj").write_text("x", encoding="utf-8")
    (clean / "boost").mkdir(parents=True)
    (clean / "boost" / "version.hpp").write_text(
        "#ifndef BOOST_VERSION_HPP\n"
        "#define BOOST_VERSION_HPP\n"
        "#define BOOST_VERSION 109100\n"
        "#define BOOST_LIB_VERSION \"1_91\"\n"
        "#endif\n",
        encoding="utf-8",
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

    removed = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--boost-home={}".format(boost_home),
        "--remove-dependencies=boost",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "Removed" in plain or "removed" in plain.lower()
    assert "source assets" in plain
    assert "leaving a final archive size of" in plain
    assert "cuppa -Q -D --list-dependencies" in plain
    assert "--exact-sizes" not in plain
    assert boost_home.is_dir()
    assert clean.is_dir()
    assert (clean / "boost" / "version.hpp").is_file()
    assert not dbg.exists()
    assert rel.is_dir()
    assert bindir.is_dir()
    assert not selected_bin.exists()
    assert other_bin.is_dir()
    assert "[{}_dbg_".format(tc_name) in plain or "bin." in plain
    assert "Leaving" in plain or "release" in plain.lower()
