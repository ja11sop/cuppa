import os

import pytest

from cuppa.core import storage_options
from cuppa.core.storage_options import default, resolve_root, LEGACY_DEPENDENCIES, LEGACY_DOWNLOADS
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


@pytest.fixture
def elsewhere(monkeypatch, tmp_path):
    """A home and a working directory of our own.

    Storage defaults live under the home directory and the fallback to an older location looks at
    the filesystem, so a test that did not move both would read the machine running it.
    """
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(project)
    return home, project


def env_for(project, **options):
    env = FakeEnv(options)
    env["sconstruct_dir"] = str(project)
    return env


def test_both_roots_default_to_a_shared_folder_under_the_home_directory(elsewhere):
    home, project = elsewhere
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["storage_root"] == str(home / ".cuppa")
    assert env["dependencies_root"] == str(home / ".cuppa" / "dependencies")
    assert env["downloads_root"] == str(home / ".cuppa" / "downloads")


def test_the_build_root_stays_with_the_project(elsewhere):
    home, project = elsewhere
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["build_root"] == default.build_root
    assert env["abs_build_root"] == os.path.join(str(project), default.build_root)


def test_the_artefacts_root_stays_with_the_project(elsewhere):
    home, project = elsewhere
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["artefacts_root"] == default.artefacts_root
    assert env["artifacts_root"] == env["artefacts_root"]
    assert env["abs_artefacts_root"] == os.path.join(str(project), default.artefacts_root)
    assert env["abs_artifacts_root"] == env["abs_artefacts_root"]


def test_a_custom_artefacts_root_is_honoured(elsewhere):
    home, project = elsewhere
    env = env_for(project, artefacts_root="out/reports")

    storage_options.process_storage_options(env)

    assert env["artefacts_root"] == os.path.join("out", "reports")
    assert env["artifacts_root"] == env["artefacts_root"]
    assert env["abs_artefacts_root"] == str(project / "out" / "reports")


def test_legacy_artifacts_folder_is_kept(elsewhere):
    home, project = elsewhere
    (project / "_artifacts").mkdir()
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["artefacts_root"] == "_artifacts"


def test_the_storage_root_moves_both_roots_together(elsewhere):
    home, project = elsewhere
    env = env_for(project, storage_root=str(project / "_cuppa"))

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(project / "_cuppa" / "dependencies")
    assert env["downloads_root"] == str(project / "_cuppa" / "downloads")


def test_a_root_named_on_its_own_leaves_the_other_derived(elsewhere):
    home, project = elsewhere
    env = env_for(project, downloads_root=str(project / "archives"))

    storage_options.process_storage_options(env)

    assert env["downloads_root"] == str(project / "archives")
    assert env["dependencies_root"] == str(home / ".cuppa" / "dependencies")


def test_a_named_root_wins_over_the_storage_root_it_would_otherwise_derive_from(elsewhere):
    home, project = elsewhere
    env = env_for(
        project,
        storage_root=str(project / "_cuppa"),
        dependencies_root=str(project / "elsewhere"),
    )

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(project / "elsewhere")
    assert env["downloads_root"] == str(project / "_cuppa" / "downloads")


def test_a_home_relative_root_is_expanded(elsewhere):
    home, project = elsewhere
    env = env_for(project, storage_root="~/somewhere")

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(home / "somewhere" / "dependencies")


def test_the_downloads_root_is_created_so_an_archive_has_somewhere_to_land(elsewhere):
    home, project = elsewhere
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert os.path.isdir(env["downloads_root"])


# Deprecated aliases


def test_the_old_option_names_still_choose_the_roots(elsewhere):
    home, project = elsewhere
    env = env_for(
        project,
        download_root=str(project / "old_download"),
        cache_root=str(project / "old_cache"),
    )

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(project / "old_download")
    assert env["downloads_root"] == str(project / "old_cache")


def test_using_an_old_option_name_is_reported_as_deprecated(elsewhere, caplog):
    home, project = elsewhere
    env = env_for(project, download_root=str(project / "old_download"))

    with caplog.at_level("WARNING"):
        storage_options.process_storage_options(env)

    assert "--download-root" in caplog.text
    assert "--dependencies-root" in caplog.text


def test_a_new_option_wins_over_the_old_name_for_the_same_root(elsewhere):
    home, project = elsewhere
    env = env_for(
        project,
        dependencies_root=str(project / "new"),
        download_root=str(project / "old"),
    )

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(project / "new")


def test_the_old_env_keys_alias_the_resolved_roots(elsewhere):
    home, project = elsewhere
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["download_root"] == env["dependencies_root"]
    assert env["cache_root"] == env["downloads_root"]


# Keeping an older location in use


def test_a_project_local_cuppa_folder_is_kept_rather_than_re_fetched(elsewhere):
    home, project = elsewhere
    (project / "_cuppa").mkdir()
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == "_cuppa"


def test_a_kept_project_local_folder_stays_relative_so_it_is_still_excluded_from_discovery(elsewhere):
    home, project = elsewhere
    (project / "_cuppa").mkdir()
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert not os.path.isabs(env["dependencies_root"])


def test_the_shared_download_folder_from_an_older_cuppa_is_kept(elsewhere):
    home, project = elsewhere
    (home / "_cuppa" / "_download").mkdir(parents=True)
    (home / "_cuppa" / "_cache").mkdir(parents=True)
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(home / "_cuppa" / "_download")
    assert env["downloads_root"] == str(home / "_cuppa" / "_cache")


def test_a_project_local_folder_is_preferred_over_the_shared_one(elsewhere):
    home, project = elsewhere
    (project / "_cuppa").mkdir()
    (home / "_cuppa" / "_download").mkdir(parents=True)
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == "_cuppa"


def test_a_project_local_folder_is_found_next_to_the_sconstruct_not_the_launch_directory(
    elsewhere, monkeypatch
):
    home, project = elsewhere
    (project / "_cuppa").mkdir()
    leaf = project / "component"
    leaf.mkdir()
    monkeypatch.chdir(leaf)
    env = env_for(project)

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == "_cuppa"


def test_keeping_an_older_folder_is_reported_with_the_option_that_moves_it(elsewhere, caplog):
    home, project = elsewhere
    (project / "_cuppa").mkdir()
    env = env_for(project)

    with caplog.at_level("INFO"):
        storage_options.process_storage_options(env)

    assert "_cuppa" in caplog.text
    assert "--dependencies-root" in caplog.text


def test_a_named_root_wins_over_an_older_folder_that_is_still_there(elsewhere):
    home, project = elsewhere
    (project / "_cuppa").mkdir()
    env = env_for(project, dependencies_root=str(project / "chosen"))

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(project / "chosen")


def test_an_old_option_name_wins_over_an_older_folder_that_is_still_there(elsewhere):
    home, project = elsewhere
    (project / "_cuppa").mkdir()
    env = env_for(project, download_root=str(project / "chosen"))

    storage_options.process_storage_options(env)

    assert env["dependencies_root"] == str(project / "chosen")


# The rule on its own


def test_resolve_root_names_what_decided_the_path(tmp_path):
    chosen = resolve_root("chosen", None, (), "derived")
    assert chosen == ("chosen", "option", None)

    aliased = resolve_root(None, "aliased", (), "derived")
    assert aliased == ("aliased", "deprecated", None)

    derived = resolve_root(None, None, (), "derived")
    assert derived == ("derived", "derived", None)


def test_resolve_root_reports_the_older_folder_it_kept(tmp_path):
    (tmp_path / "_cuppa").mkdir()

    kept = resolve_root(None, None, LEGACY_DEPENDENCIES, "derived", str(tmp_path))

    assert kept.source == "legacy"
    assert kept.origin == "_cuppa"


def test_resolve_root_derives_when_no_older_folder_is_there(elsewhere, tmp_path):
    resolved = resolve_root(None, None, LEGACY_DOWNLOADS, str(tmp_path / "downloads"), str(tmp_path))

    assert resolved.source == "derived"
    assert resolved.path == str(tmp_path / "downloads")


# Reporting the roots in build output


def test_the_roots_are_named_once_however_many_dependencies_are_retrieved(elsewhere, caplog):
    home, project = elsewhere
    env = env_for(project)
    storage_options.process_storage_options(env)

    with caplog.at_level("INFO"):
        storage_options.report_roots(env)
        storage_options.report_roots(env)

    assert caplog.text.count("for dependencies and") == 1
