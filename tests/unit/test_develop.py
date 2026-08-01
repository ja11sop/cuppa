#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""The rules behind --list-develop and --update-develop, which are pure functions of state."""

import os
import shutil
import subprocess

import pytest

from cuppa.develop import (
    ERROR,
    NOTE,
    OK,
    WARNING,
    Copy,
    classify,
    inspect,
    list_develop,
    state_summary,
    survey,
    table,
    update_action,
    update_develop,
)
from cuppa.location import Location, develop_location
from cuppa.scms.git import Git


pytestmark = pytest.mark.unit


BUILT = "feature_orders"
DEFAULT = "master"


def copy( **observed ):
    """A clean git copy on the branch being built, unless the test says otherwise."""
    state = dict(
        name            = "widget",
        path            = "/home/user/coding/widget",
        exists          = True,
        is_working_copy = True,
        scm             = 'git',
        branch          = BUILT,
        detached        = False,
        upstream        = "origin/" + BUILT,
        ahead           = 0,
        behind          = 0,
        modified        = False,
    )
    state.update( observed )
    return Copy( **state )


def severity( **observed ):
    return classify( copy( **observed ), BUILT, DEFAULT ).severity


def notes( **observed ):
    return " ".join( classify( copy( **observed ), BUILT, DEFAULT ).notes )


#-------------------------------------------------------------------------------
#   One case per row of the classification table
#-------------------------------------------------------------------------------

def test_the_branch_being_built_is_ok():
    assert severity( branch=BUILT ) == OK


def test_the_default_branch_is_ok():
    assert severity( branch=DEFAULT, upstream="origin/" + DEFAULT ) == OK


def test_any_other_branch_warns():
    assert severity( branch="spike_cache" ) == WARNING
    assert "neither" in notes( branch="spike_cache" )


def test_a_detached_head_warns():
    assert severity( detached=True, branch=None ) == WARNING


def test_behind_upstream_warns():
    assert severity( behind=12 ) == WARNING
    assert "12 commits behind" in notes( behind=12 )


def test_diverged_warns():
    assert severity( ahead=2, behind=3 ) == WARNING
    assert "diverged" in notes( ahead=2, behind=3 )


def test_ahead_on_the_branch_being_built_is_a_note():
    assert severity( ahead=2 ) == NOTE


def test_modified_on_the_branch_being_built_is_a_note():
    assert severity( modified=True ) == NOTE


def test_ahead_on_the_default_branch_warns():
    assert severity( branch=DEFAULT, upstream="origin/" + DEFAULT, ahead=2 ) == WARNING


def test_modified_on_the_default_branch_warns():
    assert severity( branch=DEFAULT, upstream="origin/" + DEFAULT, modified=True ) == WARNING


def test_no_upstream_is_a_note():
    assert severity( upstream=None, ahead=None, behind=None ) == NOTE
    assert "no upstream" in notes( upstream=None, ahead=None, behind=None )


def test_a_directory_that_is_not_a_working_copy_warns():
    assert severity( is_working_copy=False, scm=None ) == WARNING


def test_a_missing_path_is_an_error():
    assert severity( exists=False ) == ERROR


def test_a_non_git_working_copy_reports_what_it_cannot_answer():
    classification = classify(
            copy( scm='other', upstream=None, ahead=None, behind=None, modified=None ),
            BUILT, DEFAULT
    )
    assert classification.severity == NOTE
    assert "not reported" in " ".join( classification.notes )


#-------------------------------------------------------------------------------
#   The pair that differ only by branch
#-------------------------------------------------------------------------------

def test_local_work_is_judged_by_the_branch_it_sits_on():
    """Identical state, different branch: on the default branch nobody else will see the work."""
    on_built = copy( branch=BUILT, upstream="origin/" + BUILT, modified=True, ahead=1 )
    on_default = on_built._replace( branch=DEFAULT, upstream="origin/" + DEFAULT )

    assert classify( on_built, BUILT, DEFAULT ).severity == NOTE
    assert classify( on_default, BUILT, DEFAULT ).severity == WARNING

    remedy = " ".join( classify( on_default, BUILT, DEFAULT ).notes )
    assert "will not see them" in remedy
    assert "push it" in remedy


def test_the_branch_being_built_is_unknown_outside_a_working_copy():
    """With no branch to match, only the default branch is unremarkable."""
    assert classify( copy( branch=DEFAULT, upstream="origin/" + DEFAULT ), "", DEFAULT ).severity == OK
    other = classify( copy( branch="anything" ), "", DEFAULT )
    assert other.severity == WARNING
    assert "not the default branch" in " ".join( other.notes )


#-------------------------------------------------------------------------------
#   What the table says
#-------------------------------------------------------------------------------

@pytest.mark.parametrize( "observed,expected", [
    ( {}, "clean" ),
    ( { "modified": True }, "modified" ),
    ( { "modified": True, "ahead": 2 }, "modified, 2 ahead" ),
    ( { "behind": 12 }, "clean, 12 behind" ),
    ( { "ahead": 3, "behind": 2 }, "clean, 3 ahead, 2 behind" ),
    ( { "upstream": None, "ahead": None, "behind": None }, "clean, no upstream" ),
    ( { "is_working_copy": False }, "not a working copy" ),
    ( { "exists": False }, "path does not exist" ),
    ( { "scm": 'other', "modified": None, "upstream": None }, "unknown" ),
] )
def test_state_summary( observed, expected ):
    assert state_summary( copy( **observed ) ) == expected


def test_the_table_has_a_header_row_and_aligned_columns():
    lines = table( [ copy( name="widget" ), copy( name="a_much_longer_name" ) ] )

    assert lines[0].split() == [ "DEPENDENCY", "BRANCH", "UPSTREAM", "STATE", "PATH" ]
    assert lines[0].index( "BRANCH" ) == lines[1].index( BUILT )
    assert lines[1].index( BUILT ) == lines[2].index( BUILT )


#-------------------------------------------------------------------------------
#   The update decision, over the same state
#-------------------------------------------------------------------------------

def test_only_a_clean_copy_that_is_behind_is_fast_forwarded():
    action = update_action( copy( behind=4 ) )
    assert action.act
    assert "4 commits behind" in action.reason


@pytest.mark.parametrize( "observed,reason", [
    ( { "exists": False }, "path does not exist" ),
    ( { "is_working_copy": False }, "not a working copy" ),
    ( { "scm": 'other' }, "only git working copies can be updated" ),
    ( { "detached": True }, "detached HEAD" ),
    ( { "upstream": None }, "no upstream branch" ),
    ( { "behind": 4, "modified": True }, "uncommitted changes" ),
    ( { "behind": 4, "ahead": 2 }, "diverged" ),
    ( { "ahead": 2 }, "ahead of" ),
    ( {}, "already up to date" ),
] )
def test_everything_else_is_skipped_with_a_reason( observed, reason ):
    action = update_action( copy( **observed ) )
    assert not action.act
    assert reason in action.reason


#-------------------------------------------------------------------------------
#   Develop path resolution, shared with the swap it describes
#-------------------------------------------------------------------------------

def test_a_relative_develop_path_is_anchored_to_the_sconstruct_directory():
    assert develop_location( "/project", "../widget" ) == os.path.join( "/project", "../widget" )


def test_an_anchored_develop_path_is_resolved_against_the_sconstruct_directory():
    assert develop_location( "/project", "#sub/widget" ) == os.path.join( "/project", "sub/widget" )


def test_an_absolute_develop_path_is_left_alone():
    assert develop_location( "/project", "/elsewhere/widget" ) == "/elsewhere/widget"


def test_a_home_relative_develop_path_is_expanded_not_anchored():
    assert develop_location( "/project", "~/coding/widget" ) == os.path.join(
            os.path.expanduser( "~" ), "coding/widget" )


def test_no_develop_location_resolves_to_nothing():
    assert develop_location( "/project", None ) is None


def test_the_swap_resolves_paths_through_the_same_helper():
    """Location must not grow its own copy of the rule, or a report can describe another path."""
    location = Location.__new__( Location )
    location._cuppa_env = { 'sconstruct_dir': "/project" }
    assert location.replace_sconstruct_anchor( "#sub/widget" ) == os.path.join(
            "/project", "sub/widget" )


#-------------------------------------------------------------------------------
#   Enumeration and exit status
#-------------------------------------------------------------------------------

class FakeEnv( dict ):

    def get_option( self, option, default=None ):
        return self.get( option, default )


def fake_env( dependencies, **overrides ):
    env = FakeEnv( {
        'dependencies': dependencies,
        'sconstruct_dir': "/project",
        'current_branch': BUILT,
        'location_default_branch': DEFAULT,
        'develop': True,
        'offline': False,
        'no_exec': False,
    } )
    env.update( overrides )
    return env


def dependency_with_develop( name, develop ):
    return type( name, (object,), { '_name': name, '_develop': develop } )


def test_dependencies_without_a_develop_location_are_counted_not_listed( tmp_path ):
    env = fake_env( {
        'widget': dependency_with_develop( 'widget', str(tmp_path) ),
        'gadget': type( 'gadget', (object,), { '_name': 'gadget' } ),
    } )

    copies, without_develop = survey( env )

    assert [ copy.name for copy in copies ] == [ 'widget' ]
    assert without_develop == [ 'gadget' ]


def test_a_report_exits_zero_even_when_it_warns( tmp_path ):
    """A directory that is not a working copy is worth a warning, not a failed build."""
    env = fake_env( { 'widget': dependency_with_develop( 'widget', str(tmp_path) ) } )
    assert list_develop( env ) == 0


def test_a_missing_develop_path_exits_non_zero( tmp_path ):
    missing = str( tmp_path / "not_here" )
    env = fake_env( { 'widget': dependency_with_develop( 'widget', missing ) } )
    assert list_develop( env ) == 1


def test_update_refuses_to_run_offline( tmp_path ):
    env = fake_env( { 'widget': dependency_with_develop( 'widget', str(tmp_path) ) },
                    offline=True )
    assert update_develop( env ) == 1


def test_a_dry_run_changes_nothing_and_exits_zero( tmp_path, monkeypatch ):
    def refuse( *args, **kwargs ):
        raise AssertionError( "a dry run must not touch the working copy" )

    monkeypatch.setattr( Git, 'fetch', refuse )
    monkeypatch.setattr( Git, 'fast_forward', refuse )

    env = fake_env( { 'widget': dependency_with_develop( 'widget', str(tmp_path) ) },
                    no_exec=True )
    assert update_develop( env ) == 0


#-------------------------------------------------------------------------------
#   Observation against a real working copy
#-------------------------------------------------------------------------------

git_available = pytest.mark.skipif(
    shutil.which( "git" ) is None, reason="git is not installed"
)


def git( path, *arguments ):
    subprocess.check_output(
        [ "git", "-c", "user.email=test@example.com", "-c", "user.name=test",
          "-c", "commit.gpgsign=false" ] + list( arguments ),
        cwd = str(path),
        stderr = subprocess.STDOUT
    )


def commit( path, name ):
    ( path / name ).write_text( name )
    git( path, "add", name )
    git( path, "commit", "-m", name )


@pytest.fixture
def working_copy( tmp_path ):
    """A clone of a local origin, so ahead and behind are real without touching a network."""
    origin = tmp_path / "origin"
    origin.mkdir()
    git( origin, "init", "--initial-branch=master", "." )
    commit( origin, "first" )

    clone = tmp_path / "clone"
    subprocess.check_output(
        [ "git", "clone", str(origin), str(clone) ], stderr=subprocess.STDOUT
    )
    return origin, clone


@git_available
def test_a_clean_clone_is_observed_as_clean( working_copy ):
    origin, clone = working_copy
    observed = inspect( "widget", str(clone) )

    assert observed.exists and observed.is_working_copy
    assert observed.scm == 'git'
    assert observed.branch == "master"
    assert observed.upstream == "origin/master"
    assert ( observed.ahead, observed.behind, observed.modified ) == ( 0, 0, False )


@git_available
def test_local_commits_are_observed_as_ahead( working_copy ):
    origin, clone = working_copy
    commit( clone, "local" )

    observed = inspect( "widget", str(clone) )
    assert ( observed.ahead, observed.behind ) == ( 1, 0 )
    assert update_action( observed ).reason.startswith( "ahead of" )


@git_available
def test_upstream_commits_are_observed_as_behind_after_a_fetch( working_copy ):
    origin, clone = working_copy
    commit( origin, "second" )

    assert inspect( "widget", str(clone) ).behind == 0, "behind is relative to the last fetch"

    Git.fetch( str(clone) )
    observed = inspect( "widget", str(clone) )

    assert ( observed.ahead, observed.behind ) == ( 0, 1 )
    assert update_action( observed ).act

    Git.fast_forward( str(clone) )
    assert inspect( "widget", str(clone) ).behind == 0


@git_available
def test_uncommitted_changes_are_observed_but_untracked_files_are_not( working_copy ):
    origin, clone = working_copy

    ( clone / "untracked" ).write_text( "untracked" )
    assert inspect( "widget", str(clone) ).modified is False

    ( clone / "first" ).write_text( "changed" )
    assert inspect( "widget", str(clone) ).modified is True


@git_available
def test_a_detached_head_is_observed_as_detached( working_copy ):
    origin, clone = working_copy
    git( clone, "checkout", "--detach", "HEAD" )

    observed = inspect( "widget", str(clone) )
    assert observed.detached
    assert observed.branch is None
    assert not update_action( observed ).act


@git_available
def test_a_branch_with_no_upstream_is_observed_as_such( working_copy ):
    origin, clone = working_copy
    git( clone, "checkout", "-b", "spike" )

    observed = inspect( "widget", str(clone) )
    assert observed.branch == "spike"
    assert observed.upstream is None
    assert ( observed.ahead, observed.behind ) == ( None, None )


@git_available
def test_a_directory_that_is_not_a_working_copy_is_observed_as_such( tmp_path ):
    observed = inspect( "widget", str(tmp_path) )
    assert observed.exists
    assert not observed.is_working_copy
