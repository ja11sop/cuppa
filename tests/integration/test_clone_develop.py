"""Integration coverage for ``--clone-develop`` and develop branch helpers."""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import write_sconstruct


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


@pytest.fixture
def widget_origin( tmp_path ):
    if not _git_available():
        pytest.skip( "git is not available" )
    return _init_repo( tmp_path / "origin" )


def _write_project( project, origin, develop_path ):
    write_sconstruct(
            project,
            """
import cuppa
Widget = cuppa.location_dependency(
        'widget',
        location={location!r},
        develop={develop!r},
)
cuppa.run(
        default_dependencies=['widget'],
        dependencies=[Widget],
)
""".format(
                    location="git+file://{}@master".format( Path( origin ).resolve() ),
                    develop=str( develop_path ),
            ),
    )
    ( project / "main.cpp" ).write_text( "int main() { return 0; }\n", encoding="utf-8" )


def test_clone_develop_creates_working_copy( tmp_path, widget_origin ):
    project = tmp_path / "project"
    project.mkdir()
    develop = tmp_path / "develop" / "widget"
    _write_project( project, widget_origin, develop )

    result = run_cuppa(
            project,
            "--clone-develop",
            "-Q",
            offline=False,
    )
    assert_success( result )
    assert ( develop / ".git" ).exists()
    assert "Cloned [widget]" in re.sub( r"\x1b\[[0-9;]*m", "", result.stdout )
    config = ( develop / ".git" / "config" ).read_text( encoding="utf-8" )
    assert "oauth2:" not in config


def test_clone_develop_refuses_nonempty( tmp_path, widget_origin ):
    project = tmp_path / "project"
    project.mkdir()
    develop = tmp_path / "develop" / "widget"
    develop.mkdir( parents=True )
    ( develop / "noise.txt" ).write_text( "keep\n", encoding="utf-8" )
    _write_project( project, widget_origin, develop )

    result = run_cuppa(
            project,
            "--clone-develop",
            "-Q",
            offline=False,
    )
    assert_success( result )
    assert "not empty" in result.stdout
    assert not ( develop / ".git" ).exists()


def test_checkout_and_reset_develop_branch( tmp_path, widget_origin ):
    project = tmp_path / "project"
    project.mkdir()
    develop = tmp_path / "develop" / "widget"
    _write_project( project, widget_origin, develop )

    assert_success( run_cuppa(
            project, "--clone-develop", "-Q", offline=False,
    ) )

    _run_git( widget_origin, "checkout", "-b", "feature_orders" )
    ( widget_origin / "feature.txt" ).write_text( "f\n", encoding="utf-8" )
    _run_git( widget_origin, "add", "feature.txt" )
    _run_git( widget_origin, "commit", "-m", "feature" )
    _run_git( widget_origin, "checkout", "master" )

    result = run_cuppa(
            project,
            "--checkout-develop-branch=feature_orders",
            "-Q",
            offline=False,
    )
    assert_success( result )
    branch = _run_git( develop, "rev-parse", "--abbrev-ref", "HEAD" )
    assert branch == "feature_orders"

    result = run_cuppa(
            project,
            "--reset-develop-branch",
            "-Q",
            offline=False,
    )
    assert_success( result )
    branch = _run_git( develop, "rev-parse", "--abbrev-ref", "HEAD" )
    assert branch == "master"
