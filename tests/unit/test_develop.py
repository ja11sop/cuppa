#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""The rules behind --list-develop and --update-develop, which are pure functions of state."""

import logging
import os
import shutil
import subprocess

from contextlib import contextmanager

import pytest

from cuppa.colourise import colouriser, start_subdued
from cuppa.develop import (
    ERROR,
    NOTE,
    OK,
    WARNING,
    Copy,
    classify,
    entries,
    highlight_values,
    inspect,
    list_develop,
    list_payload,
    names_that_would_update,
    render_judgements,
    render_table,
    row_for,
    state_summary,
    suggestion,
    survey,
    table,
    update_action,
    update_develop,
)
from cuppa.location import Location, develop_location
from cuppa.log import logger
from cuppa.scms.git import Git


pytestmark = pytest.mark.unit


BUILT = "feature_orders"
DEFAULT = "master"

RESET = "\x1b[0m"

STUB  = "\u2502"
TEE   = "\u251c\u2500\u2500 "
ELBOW = "\u2514\u2500\u2500 "
PIPE  = "\u2502   "
GAP   = "    "


@contextmanager
def colour():
    """Colour is off by default in a test run, so a test that is about colour turns it on."""
    was = colouriser.use_colour
    colouriser.enable()
    try:
        yield start_subdued()
    finally:
        colouriser.use_colour = was


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
    lines = table( entries( [ copy( name="widget" ), copy( name="a_much_longer_name" ) ],
                            BUILT, DEFAULT ) )

    assert lines[0].split() == [ "STATUS", "DEPENDENCY", "BRANCH", "UPSTREAM", "STATE", "PATH" ]
    assert lines[0].index( "BRANCH" ) == lines[1].index( BUILT )
    assert lines[1].index( BUILT ) == lines[2].index( BUILT )


def test_the_table_is_ruled_above_and_below_the_header_and_at_the_foot():
    found = entries( [ copy( name="widget" ), copy( name="gadget" ) ], BUILT, DEFAULT )
    lines = render_table( found )

    assert lines[0] == lines[2] == lines[-1]
    assert set( lines[0].strip() ) == { "-" }
    assert len( lines[0] ) == max( len( row ) for row in table( found ) )
    assert lines[1].split()[0] == "STATUS"
    assert len( lines ) == 4 + len( found )


def test_rows_that_need_nothing_recede_and_rows_that_need_attention_do_not():
    """Receding, rather than a background colour, reads the same way on a light console as on a
    dark one, and a terminal that ignores it just shows a plain table."""
    found = entries( [ copy( name="widget" ),
                       copy( name="flange", ahead=2 ),
                       copy( name="gadget", behind=2 ),
                       copy( name="gizmo", exists=False ) ], BUILT, DEFAULT )

    with colour() as subdued:
        rows = render_table( found )[3:-1]

    assert [ row.startswith( subdued ) for row in rows ] == [ True, True, False, False ]


def test_a_note_colours_the_values_and_leaves_the_prose_plain():
    coloured = highlight_values( "[flange] is behind [origin/master] as of your last fetch",
                                 lambda value: "<" + value + ">" )
    assert coloured == "[<flange>] is behind [<origin/master>] as of your last fetch"


def test_judgements_hang_from_the_summary_as_one_tree_worst_first():
    """Reading down the tree is reading a work list: what stops the build, then what needs a
    decision, then what is only worth knowing, all of it one tree rooted on the summary."""
    found = entries( [ copy( name="widget" ),
                       copy( name="flange", ahead=2 ),
                       copy( name="doodad", detached=True, branch=None ),
                       copy( name="gizmo", exists=False ) ], BUILT, DEFAULT )
    lines = render_judgements( found )

    assert lines[0] == STUB
    assert lines[1] == TEE + "1 error"
    assert lines[2] == PIPE + STUB
    assert lines[3] == PIPE + ELBOW + "gizmo"
    assert lines[4].startswith( PIPE + GAP + ELBOW + "has a develop path" )
    assert lines[5] == STUB
    assert lines[6] == TEE + "1 warning"
    assert lines[10] == STUB
    assert lines[11] == ELBOW + "1 note"
    assert lines[12] == GAP + STUB
    assert lines[13] == GAP + ELBOW + "flange"
    assert lines[14] == GAP + GAP + ELBOW + "has 2 unpushed commits on [feature_orders]"


def test_a_severity_heading_counts_the_dependencies_under_it():
    """The heading answers how much of this there is before you read any of it."""
    found = entries( [ copy( name="doodad", detached=True, branch=None ),
                       copy( name="gadget", detached=True, branch=None ),
                       copy( name="flange", ahead=2 ) ], BUILT, DEFAULT )
    lines = render_judgements( found )

    assert lines[1] == TEE + "2 warnings"
    assert ELBOW + "1 note" in lines


def test_a_severity_with_two_dependencies_keeps_the_stem_under_the_first():
    found = entries( [ copy( name="doodad", detached=True, branch=None ),
                       copy( name="gadget", branch="spike", upstream="origin/spike",
                             modified=True ) ], BUILT, DEFAULT )
    lines = render_judgements( found )

    assert lines == [
        STUB,
        ELBOW + "2 warnings",
        GAP + STUB,
        GAP + TEE + "doodad",
        GAP + PIPE + ELBOW + "is on a detached HEAD; it works today and is forgotten tomorrow",
        GAP + STUB,
        GAP + ELBOW + "gadget",
        GAP + GAP + TEE + "is on [spike], which is neither [feature_orders] nor the default"
        " branch [master]",
        GAP + GAP + ELBOW + "has uncommitted changes on [spike]",
    ]


def test_the_tree_falls_back_to_ascii_when_the_console_cannot_encode_it():
    found = entries( [ copy( name="doodad", detached=True, branch=None ) ], BUILT, DEFAULT )

    assert render_judgements( found, encoding='ascii' )[:4] == [
        "|", "`-- 1 warning", "    |", "    `-- doodad"
    ]
    assert render_judgements( found, encoding='utf-8' )[3] == GAP + ELBOW + "doodad"


def test_a_long_reason_wraps_and_the_stem_is_carried_down_the_wrapped_lines():
    """A reason that runs past the table's right edge is wrapped rather than left to wrap itself
    at the console edge, which would break the tree."""
    found = entries( [ copy( name="widget", branch=DEFAULT, upstream="origin/" + DEFAULT,
                             modified=True ) ], BUILT, DEFAULT )
    lines = render_judgements( found, width=72 )
    reasons = lines[4:]

    assert len( reasons ) > 1
    assert reasons[0].startswith( GAP + GAP + ELBOW )
    assert all( line.startswith( GAP + GAP + GAP ) for line in reasons[1:] )
    assert all( len( line ) <= 72 for line in lines )
    assert " ".join( line.lstrip( "\u2502\u251c\u2514\u2500 " ) for line in reasons ) \
        == found[0].notes[0]


def test_a_reason_is_not_wrapped_when_no_width_is_given():
    found = entries( [ copy( name="widget", branch=DEFAULT, upstream="origin/" + DEFAULT,
                             modified=True ) ], BUILT, DEFAULT )

    assert render_judgements( found )[4:] == [ GAP + GAP + ELBOW + found[0].notes[0] ]


def test_an_ok_copy_recedes_and_says_nothing_more():
    """Nothing to be done, so nothing to draw the eye: no colour of its own, and no note."""
    entry = entries( [ copy( name="widget" ) ], BUILT, DEFAULT )[0]

    with colour() as subdued:
        row = render_table( [ entry ] )[3]

    assert row == subdued + table( [ entry ] )[1] + RESET
    assert render_judgements( [ entry ] ) == []


def test_a_judgement_names_a_path_the_way_the_table_does():
    """Develop paths are usually written relative to the sconstruct, so the resolved path is full
    of `..`. The table tidies it and the judgement about it has to agree."""
    relative = os.path.join( os.path.expanduser( "~" ), "coding", "project", "..", "gizmo" )
    entry = entries( [ copy( name="gizmo", path=relative, exists=False ) ], BUILT, DEFAULT )[0]

    assert entry.notes[0].startswith( "has a develop path [~/coding/gizmo]" )
    assert row_for( entry )[-1] == "~/coding/gizmo"


def test_severity_is_a_column_so_it_survives_colourless_output():
    """With no log prefix and no colour, the status must still be readable and greppable."""
    rows = table( entries( [ copy( name="widget" ),
                             copy( name="flange", behind=2 ),
                             copy( name="gizmo", exists=False ) ], BUILT, DEFAULT ) )

    assert rows[1].split()[0] == "ok"
    assert rows[2].split()[0] == "warn"
    assert rows[3].split()[0] == "error"


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


def test_the_report_says_what_updating_would_do_when_it_would_do_something():
    """The suggestion comes from update_action(), so it cannot offer what --update-develop then
    declines to do, and it says that a fetch may find more rather than reading as a promise."""
    advice = suggestion( [ copy( name="widget", behind=3 ),
                           copy( name="flange", behind=1 ),
                           copy( name="gadget", modified=True ) ] )

    assert "fast-forward 2 ([widget], [flange])" in advice
    assert "as of your last fetch" in advice
    assert "may find more" in advice


def test_nothing_is_suggested_when_every_copy_would_be_left_alone():
    assert suggestion( [ copy( name="widget" ), copy( name="gadget", modified=True ) ] ) is None


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


def test_the_report_is_written_to_standard_output( tmp_path, capsys ):
    env = fake_env( { 'widget': dependency_with_develop( 'widget', str(tmp_path) ) } )
    list_develop( env )

    written = capsys.readouterr().out
    assert "DEPENDENCY" in written
    assert "widget" in written
    assert "develop location" in written


def test_the_report_survives_a_quiet_log_level( tmp_path, capsys ):
    """The report is what was asked for, so a quieter log must not take pieces out of it."""
    env = fake_env( { 'widget': dependency_with_develop( 'widget', str(tmp_path) ) } )

    was = logger.level
    logger.setLevel( logging.CRITICAL )
    try:
        list_develop( env )
    finally:
        logger.setLevel( was )

    written = capsys.readouterr().out
    assert "DEPENDENCY" in written
    assert "not a working copy" in written
    assert "develop location" in written


def test_a_missing_develop_path_exits_non_zero( tmp_path ):
    missing = str( tmp_path / "not_here" )
    env = fake_env( { 'widget': dependency_with_develop( 'widget', missing ) } )
    assert list_develop( env ) == 1


def test_list_payload_carries_severity_and_would_update():
    behind = copy(
            name='flange',
            behind=2,
            branch='spike_cache',
            upstream='origin/spike_cache',
    )
    missing = copy( name='gizmo', path='/missing', exists=False )
    payload = list_payload(
            [ behind, missing ],
            without_develop=[ 'boost' ],
            current_branch=BUILT,
            default_branch=DEFAULT,
            develop_active=False,
    )
    assert payload['current_branch'] == BUILT
    assert payload['default_branch'] == DEFAULT
    assert payload['develop_active'] is False
    assert payload['without_develop'] == [ 'boost' ]
    assert payload['would_update'] == [ 'flange' ]
    assert payload['worst_severity'] == ERROR
    by_name = { entry['name']: entry for entry in payload['entries'] }
    assert by_name['flange']['severity'] == WARNING
    assert by_name['flange']['status'] == 'warn'
    assert by_name['flange']['behind'] == 2
    assert by_name['flange']['state'] == 'clean, 2 behind'
    assert by_name['gizmo']['exists'] is False
    assert by_name['gizmo']['severity'] == ERROR
    assert names_that_would_update( [ behind, missing ] ) == [ 'flange' ]


def test_list_develop_json_is_parseable_and_exits_on_missing( tmp_path, capsys ):
    import json

    missing = str( tmp_path / "not_here" )
    env = fake_env(
            { 'widget': dependency_with_develop( 'widget', missing ) },
            list_format='json',
    )
    assert list_develop( env ) == 1
    written = capsys.readouterr().out
    payload = json.loads( written )
    assert payload['worst_severity'] == ERROR
    assert payload['entries'][0]['name'] == 'widget'
    assert payload['entries'][0]['exists'] is False
    assert 'DEPENDENCY' not in written


def test_list_develop_json_with_no_develop_locations( capsys ):
    import json

    env = fake_env(
            { 'gadget': type( 'gadget', (object,), { '_name': 'gadget' } ) },
            list_format='json',
    )
    assert list_develop( env ) == 0
    payload = json.loads( capsys.readouterr().out )
    assert payload['entries'] == []
    assert payload['without_develop'] == [ 'gadget' ]
    assert payload['worst_severity'] == OK
    assert payload['would_update'] == []


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


@git_available
def test_listing_ends_by_saying_what_updating_would_do( working_copy, capsys ):
    origin, clone = working_copy
    commit( origin, "second" )
    Git.fetch( str(clone) )

    list_develop( fake_env( { 'widget': dependency_with_develop( 'widget', str(clone) ) } ) )

    assert "--update-develop would fast-forward 1 ([widget])" in capsys.readouterr().out


@git_available
def test_updating_does_not_suggest_the_option_you_have_just_run( working_copy, capsys ):
    origin, clone = working_copy
    commit( origin, "second" )

    update_develop( fake_env( { 'widget': dependency_with_develop( 'widget', str(clone) ) } ) )

    assert "--update-develop would fast-forward" not in capsys.readouterr().out
