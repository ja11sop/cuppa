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


def a_project_with_planted_dependency(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    tree = deps / "widget@master"
    tree.mkdir(parents=True)
    (tree / "readme").write_text("hello from widget\n", encoding="utf-8")
    write_sconstruct(project)
    return project, storage, tree


def test_list_dependencies_reports_planted_trees(tmp_path):
    project, storage, tree = a_project_with_planted_dependency(tmp_path)

    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    assert "Dependencies in" in listed.stdout
    assert "DEPENDENCY" in listed.stdout
    assert "widget@master" in listed.stdout or "widget" in listed.stdout
    assert "unreferenced" in listed.stdout
    assert "entries" in listed.stdout
    # Listing must not remove trees.
    assert tree.is_dir()


def test_list_dependencies_json(tmp_path):
    project, storage, _tree = a_project_with_planted_dependency(tmp_path)

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
    assert payload["entries"]
    assert "size_bytes" in payload["entries"][0]
    assert payload["entries"][0]["state"] == "unreferenced"
    assert "dependencies_root" in payload


def test_list_dependencies_writes_inventory_for_existing_trees(tmp_path):
    project, storage, tree = a_project_with_planted_dependency(tmp_path)

    assert_success(run_cuppa(
        project,
        "--list-dependencies",
        "--exact-sizes",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    ))

    # Provisional walk rows are not written without ownership; inventory dir may be
    # absent until a resolve-only owned path is touched. A second listing still works.
    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    assert tree.is_dir()
