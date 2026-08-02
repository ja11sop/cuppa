import json
import re

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct


pytestmark = pytest.mark.integration


def a_project(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    return project


def test_list_builds_after_a_debug_build(tmp_path):
    project = a_project(tmp_path)
    built = run_cuppa(project, "--dbg")
    assert_success(built)

    listed = run_cuppa(project, "--dbg", "--list-builds")
    assert_success(listed)
    assert "BUILD FOLDER" in listed.stdout
    assert "BY TOOLCHAIN VARIANT" in listed.stdout
    assert "BY SCONSCRIPT" in listed.stdout
    assert "selected" in listed.stdout
    assert "cuppa -D" in listed.stdout
    assert "--remove-builds" in listed.stdout


def test_remove_builds_dry_run_keeps_the_tree(tmp_path):
    project = a_project(tmp_path)
    assert_success(run_cuppa(project, "--dbg"))

    dry = run_cuppa(project, "--dbg", "--remove-builds", "-n")
    assert_success(dry)
    assert "Would remove" in dry.stdout or "dry run" in dry.stdout
    assert "BUILD FOLDER" in dry.stdout
    assert "REMOVED" in dry.stdout or "BY SCONSCRIPT" in dry.stdout
    assert "Verify the removal" in dry.stdout
    assert "--list-builds" in dry.stdout
    assert (project / "_build").exists()


def test_remove_builds_removes_matching_trees(tmp_path):
    project = a_project(tmp_path)
    assert_success(run_cuppa(project, "--dbg"))
    assert (project / "_build").exists()

    removed = run_cuppa(project, "--dbg", "--remove-builds")
    assert_success(removed)
    # The selected variant trees are gone; the build root may remain as an empty shell
    # or be fully pruned depending on what else was under it.
    assert "BUILD FOLDER" in removed.stdout
    assert "REMOVED" in removed.stdout
    assert "Removed" in removed.stdout and "freeing up" in removed.stdout
    assert "Verify the removal" in removed.stdout
    remaining = list((project / "_build").rglob("working")) if (project / "_build").exists() else []
    assert remaining == []

    listed = run_cuppa(project, "--dbg", "--list-builds")
    assert_success(listed)
    assert "selected (0 of" in listed.stdout or "Selected 0" in listed.stdout or (
        "0 of 0" in listed.stdout
    )


def test_remove_all_builds_dry_run_keeps_the_root(tmp_path):
    project = a_project(tmp_path)
    assert_success(run_cuppa(project, "--dbg"))

    dry = run_cuppa(project, "--remove-all-builds", "-n")
    assert_success(dry)
    assert "Would remove build root" in dry.stdout
    assert "BUILD FOLDER" in dry.stdout
    assert "REMOVED" in dry.stdout
    assert "dry run" in dry.stdout
    assert "--list-builds" in dry.stdout
    assert (project / "_build").exists()
    assert list((project / "_build").rglob("working"))


def test_remove_all_builds_removes_the_build_root(tmp_path):
    project = a_project(tmp_path)
    assert_success(run_cuppa(project, "--dbg"))
    assert (project / "_build").exists()

    removed = run_cuppa(project, "--remove-all-builds")
    assert_success(removed)
    assert "BUILD FOLDER" in removed.stdout
    assert "REMOVED" in removed.stdout
    assert "Removed build root" in removed.stdout
    assert "freeing up" in removed.stdout
    assert not (project / "_build").exists()


def test_list_builds_json(tmp_path):
    project = a_project(tmp_path)
    assert_success(run_cuppa(project, "--dbg"))

    listed = run_cuppa(project, "--dbg", "--list-builds", "--list-format=json")
    assert_success(listed)
    match = re.search(r"\{.*\}", listed.stdout, re.DOTALL)
    assert match, listed.stdout
    payload = json.loads(match.group(0))
    assert payload["entries"]
    assert "size_bytes" in payload["entries"][0]
    assert "folder" in payload
    assert "by_toolchain_variant" in payload
    assert "by_sconscript" in payload
    assert "summary" in payload
