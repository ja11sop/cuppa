import json
import re

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct


pytestmark = pytest.mark.integration


def own_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "USERPROFILE": str(home)}


def plant_realistic_dependencies_root(storage):
    """Layouts that match a shared legacy dependencies root."""
    deps = storage / "dependencies"

    vcs = deps / "git_https_github.com__fmtlib_fmt.git"
    (vcs / "include" / "fmt").mkdir(parents=True)
    (vcs / "test" / "gtest").mkdir(parents=True)
    (vcs / "readme").write_text("fmt\n", encoding="utf-8")

    package = deps / "gcc153_rel_x86_64_cxx2c" / "boost" / "1.91"
    package.mkdir(parents=True)
    (package / "include" / "boost").mkdir(parents=True)
    (package / "include" / "boost" / "version.hpp").write_text("//\n", encoding="utf-8")

    branched = deps / "git_ssh_git@host__org_widget@master"
    branched.mkdir(parents=True)
    (branched / "src").mkdir()
    (branched / "src" / "a.cpp").write_text("int a;\n", encoding="utf-8")

    return deps, vcs, package, branched


def a_project_with_planted_dependency(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    plant_realistic_dependencies_root(storage)
    write_sconstruct(project)
    return project, storage


def test_list_dependencies_reports_ownership_units_not_nested_source(tmp_path):
    project, storage = a_project_with_planted_dependency(tmp_path)

    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    # Colour codes can sit against cell text; strip CSI sequences before matching.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", listed.stdout)
    assert "Dependencies in" in plain
    assert "DEPENDENCY" in plain

    # Package row names the package, not the version folder.
    assert re.search(r"\bboost\b", plain)
    assert "1.91" in plain
    assert "gcc153_rel_x86_64_cxx2c" in plain

    # VCS top-level trees appear once; nested include/test folders do not.
    assert "fmtlib_fmt" in plain or "git_https_github.com__fmtlib_fmt.git" in plain
    assert "unreferenced" in plain

    # Three ownership units — not every nested include/test folder.
    assert "3 entries" in plain


def test_list_dependencies_json(tmp_path):
    project, storage = a_project_with_planted_dependency(tmp_path)

    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    match = re.search(r"\{.*\}", listed.stdout, re.DOTALL)
    assert match, listed.stdout
    payload = json.loads(match.group(0))
    assert len(payload["entries"]) == 3
    names = {entry["dependency"] for entry in payload["entries"]}
    assert "boost" in names
    assert any("fmt" in name for name in names)
    assert any("widget" in name for name in names)
    boost = next(entry for entry in payload["entries"] if entry["dependency"] == "boost")
    assert boost["qualifier"] == "1.91"
    assert boost["tool_variant"] == "gcc153_rel_x86_64_cxx2c"
    assert boost["state"] == "unreferenced"


def test_list_dependencies_second_pass_still_works(tmp_path):
    project, storage = a_project_with_planted_dependency(tmp_path)

    assert_success(run_cuppa(
        project,
        "--list-dependencies",
        "--exact-sizes",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    ))
    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    assert "3 entries" in listed.stdout
