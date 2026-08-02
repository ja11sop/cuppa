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
    assert "--remove-build" in listed.stdout


def test_remove_build_dry_run_keeps_the_tree(tmp_path):
    project = a_project(tmp_path)
    assert_success(run_cuppa(project, "--dbg"))

    dry = run_cuppa(project, "--dbg", "--remove-build", "-n")
    assert_success(dry)
    assert "Would remove" in dry.stdout or "dry run" in dry.stdout
    assert (project / "_build").exists()


def test_remove_build_removes_matching_trees(tmp_path):
    project = a_project(tmp_path)
    assert_success(run_cuppa(project, "--dbg"))
    assert (project / "_build").exists()

    removed = run_cuppa(project, "--dbg", "--remove-build")
    assert_success(removed)
    # The selected variant trees are gone; the build root may remain as an empty shell
    # or be fully pruned depending on what else was under it.
    assert "removed" in removed.stdout
    remaining = list((project / "_build").rglob("working")) if (project / "_build").exists() else []
    assert remaining == []


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
