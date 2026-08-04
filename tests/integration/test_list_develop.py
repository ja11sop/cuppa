"""Integration coverage for ``--list-develop`` with realistic planted git copies."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct


pytestmark = pytest.mark.integration


def _git_available():
    return shutil.which( "git" ) is not None


def _run_git( cwd, *args ):
    completed = subprocess.run(
            [ "git", *args ],
            cwd=str( cwd ),
            check=True,
            capture_output=True,
            text=True,
    )
    return completed.stdout.strip()


def _init_repo( path, branch="master", message="init" ):
    path = Path( path )
    path.mkdir( parents=True, exist_ok=True )
    _run_git( path, "init", "-b", branch )
    _run_git( path, "config", "user.email", "cuppa-test@example.com" )
    _run_git( path, "config", "user.name", "Cuppa Test" )
    ( path / "README" ).write_text( "{}\n".format( path.name ), encoding="utf-8" )
    _run_git( path, "add", "README" )
    _run_git( path, "commit", "-m", message )
    return path


def _add_commit( path, name, message ):
    ( Path( path ) / name ).write_text( "x\n", encoding="utf-8" )
    _run_git( path, "add", name )
    _run_git( path, "commit", "-m", message )


def _setup_behind_on_branch( work, branch="spike_cache", behind=2 ):
    """Working copy on ``branch``, clean, tracking a local remote that is ahead."""
    work = Path( work )
    bare = work.parent / ( work.name + ".git" )
    _init_repo( work, branch=branch )
    _run_git( work.parent, "clone", "--bare", str( work ), str( bare ) )
    _run_git( work, "remote", "add", "origin", str( bare ) )
    _run_git( work, "push", "-u", "origin", branch )
    # Advance the bare remote without updating the working copy.
    scratch = work.parent / ( work.name + "_scratch" )
    _run_git( work.parent, "clone", str( bare ), str( scratch ) )
    _run_git( scratch, "checkout", branch )
    for index in range( behind ):
        _add_commit( scratch, "ahead_{}.txt".format( index ), "ahead {}".format( index ) )
    _run_git( scratch, "push", "origin", branch )
    shutil.rmtree( scratch )
    # Refresh remote-tracking refs in the working copy without merging.
    _run_git( work, "fetch", "origin" )
    return work


def _plain( text ):
    return re.sub( r"\x1b\[[0-9;]*m", "", text )


def test_list_develop_reports_realistic_working_copy_states( tmp_path ):
    if not _git_available():
        pytest.skip( "git is required for --list-develop integration coverage" )

    project = copy_dummy_project( tmp_path )
    deps = tmp_path / "deps"
    deps.mkdir()

    # Project branch drives "building on branch […]" — cuppa only records it when the
    # sconstruct directory has a recognisable repo URL (a remote is enough).
    _init_repo( project, branch="feature_orders" )
    project_bare = tmp_path / "project.git"
    _run_git( tmp_path, "clone", "--bare", str( project ), str( project_bare ) )
    _run_git( project, "remote", "add", "origin", str( project_bare ) )

    widget = _init_repo( deps / "widget", branch="feature_orders" )
    # Tracked modification on the branch being built → note.
    ( widget / "README" ).write_text( "dirty widget\n", encoding="utf-8" )

    gadget = _init_repo( deps / "gadget", branch="master" )
    gadget_bare = deps / "gadget.git"
    _run_git( deps, "clone", "--bare", str( gadget ), str( gadget_bare ) )
    _run_git( gadget, "remote", "add", "origin", str( gadget_bare ) )
    _run_git( gadget, "push", "-u", "origin", "master" )

    flange = _setup_behind_on_branch( deps / "flange", branch="spike_cache", behind=2 )

    missing = deps / "gizmo"  # deliberately not created

    write_sconstruct(
            project,
            body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='git+https://example.com/org/widget.git',
    develop={widget!r},
)
Gadget = cuppa.location_dependency(
    'gadget',
    location='git+https://example.com/org/gadget.git',
    develop={gadget!r},
)
Flange = cuppa.location_dependency(
    'flange',
    location='git+https://example.com/org/flange.git',
    develop={flange!r},
)
Gizmo = cuppa.location_dependency(
    'gizmo',
    location='git+https://example.com/org/gizmo.git',
    develop={gizmo!r},
)
Boostish = cuppa.location_dependency(
    'boostish',
    location='git+https://example.com/org/boostish.git',
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Widget, Gadget, Flange, Gizmo, Boostish],
    default_dependencies=['widget', 'gadget', 'flange', 'gizmo', 'boostish'],
)
""".format(
                    widget=str( widget ),
                    gadget=str( gadget ),
                    flange=str( flange ),
                    gizmo=str( missing ),
            ),
    )

    listed = run_cuppa(
            project,
            "--list-develop",
            "-Q",
            "--location-default-branch=master",
    )
    # Missing develop path makes the report exit non-zero (CI should hear about it).
    assert listed.returncode == 1
    plain = _plain( listed.stdout )

    assert "Building on branch [feature_orders]" in plain
    assert "default branch [master]" in plain
    assert "--develop is not active" in plain

    assert "STATUS" in plain and "DEPENDENCY" in plain and "BRANCH" in plain
    assert "widget" in plain
    assert "gadget" in plain
    assert "flange" in plain
    assert "gizmo" in plain

    assert "path does not exist" in plain
    assert "spike_cache" in plain
    assert "behind" in plain
    assert "modified" in plain

    assert "develop location" in plain or "develop locations" in plain
    assert "not using develop" in plain

    assert "1 error" in plain
    assert "warning" in plain
    assert "Ahead and behind are relative to your last fetch" in plain
    assert re.search( r"gizmo", plain )
    assert re.search( r"flange", plain )


def test_list_develop_without_develop_locations_still_reports( tmp_path ):
    if not _git_available():
        pytest.skip( "git is required for --list-develop integration coverage" )

    project = copy_dummy_project( tmp_path )
    _init_repo( project, branch="master" )
    write_sconstruct( project )

    listed = run_cuppa( project, "--list-develop", "-Q" )
    assert_success( listed )
    plain = _plain( listed.stdout )
    assert "No dependencies have a develop location configured" in plain
    assert "dependencies in total" in plain or "dependency in total" in plain
