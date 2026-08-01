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


def own_home(tmp_path):
    """A home directory for the run, so it neither reads nor writes the real one.

    The storage roots default to a folder under the home directory, and cuppa keeps an existing
    older folder in use when it finds one, so a run that shared the developer's home would report
    whatever that machine happens to have.
    """
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def dumped_options(result):
    """The options object cuppa prints under --dump."""
    match = re.search(r"^\{$.*?^\}$", result.stdout, re.MULTILINE | re.DOTALL)
    assert match, "no options dump in cuppa output:\n{}".format(result.stdout)
    return json.loads(match.group(0))


def test_storage_root_puts_both_roots_underneath_it(tmp_path):
    project = a_project(tmp_path)
    storage = tmp_path / "storage"

    result = run_cuppa(
        project,
        "--dbg",
        "--dump",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(result)

    options = dumped_options(result)
    assert options["dependencies_root"] == str(storage / "dependencies")
    assert options["downloads_root"] == str(storage / "downloads")
    assert (storage / "downloads").is_dir()


def test_naming_the_downloads_root_moves_only_that_half(tmp_path):
    project = a_project(tmp_path)
    storage = tmp_path / "storage"
    archives = tmp_path / "archives"

    result = run_cuppa(
        project,
        "--dbg",
        "--dump",
        "--storage-root={}".format(storage),
        "--downloads-root={}".format(archives),
        extra_env=own_home(tmp_path),
    )
    assert_success(result)

    options = dumped_options(result)
    assert options["downloads_root"] == str(archives)
    assert options["dependencies_root"] == str(storage / "dependencies")


def test_the_old_option_names_still_work_and_say_they_are_deprecated(tmp_path):
    project = a_project(tmp_path)
    trees = tmp_path / "trees"
    archives = tmp_path / "archives"

    result = run_cuppa(
        project,
        "--dbg",
        "--dump",
        "--download-root={}".format(trees),
        "--cache-root={}".format(archives),
        extra_env=own_home(tmp_path),
    )
    assert_success(result)

    options = dumped_options(result)
    assert options["dependencies_root"] == str(trees)
    assert options["downloads_root"] == str(archives)
    assert "--download-root" in result.stdout
    assert "--dependencies-root" in result.stdout


def test_an_existing_project_local_cuppa_folder_is_kept_in_use(tmp_path):
    project = a_project(tmp_path)
    (project / "_cuppa").mkdir()

    result = run_cuppa(project, "--dbg", "--dump", extra_env=own_home(tmp_path))
    assert_success(result)

    options = dumped_options(result)
    assert options["dependencies_root"] == "_cuppa"


def test_the_default_roots_are_shared_between_projects(tmp_path):
    project = a_project(tmp_path)
    home = own_home(tmp_path)

    result = run_cuppa(project, "--dbg", "--dump", extra_env=home)
    assert_success(result)

    options = dumped_options(result)
    assert options["dependencies_root"] == str(tmp_path / "home" / ".cuppa" / "dependencies")
    assert options["downloads_root"] == str(tmp_path / "home" / ".cuppa" / "downloads")
