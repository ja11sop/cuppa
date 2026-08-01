#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Develop
#-------------------------------------------------------------------------------

"""Reporting on, and updating, the local working copies that `--develop` builds against.

`--develop` substitutes a working copy on disk for a retrieved dependency and says nothing about
the state of that copy, so a build can be reading someone else's spike branch, or a checkout that
has not been pulled for months. `--list-develop` answers what you are actually building against,
and `--update-develop` fast-forwards the copies where doing so cannot lose work.

The decisions are `classify()` and `update_action()`, pure functions of observed state.
Observation, reporting, and the git commands are kept out of them so the rules can be tested
without a repository, and so the two options can never judge the same copy differently.
"""

import os

from collections import namedtuple

from cuppa.colourise import as_error, as_info, as_info_label, as_notice, as_warning
from cuppa.location import develop_location
from cuppa.log import logger
from cuppa.scms import scms
from cuppa.scms.git import Git


OK      = 'ok'
NOTE    = 'note'
WARNING = 'warning'
ERROR   = 'error'

SEVERITY_ORDER = { OK: 0, NOTE: 1, WARNING: 2, ERROR: 3 }


# One develop location and everything observed about it. `ahead`, `behind` and `modified` are
# None when the question could not be answered, which is not the same as zero or clean.
Copy = namedtuple(
        'Copy',
        [ 'name', 'path', 'exists', 'is_working_copy', 'scm',
          'branch', 'detached', 'upstream', 'ahead', 'behind', 'modified' ]
)

Copy.__new__.__defaults__ = ( False, False, None, None, False, None, None, None, None )

Classification = namedtuple( 'Classification', [ 'severity', 'notes' ] )

Action = namedtuple( 'Action', [ 'act', 'reason' ] )


def worst( severities ):
    return max( severities, key=lambda severity: SEVERITY_ORDER[severity] )


def plural( count, noun, plural_noun=None ):
    if count == 1:
        return "{} {}".format( count, noun )
    return "{} {}".format( count, plural_noun or noun + "s" )


#-------------------------------------------------------------------------------
#   The rules
#-------------------------------------------------------------------------------

def classify( copy, current_branch, default_branch ):
    """How much of a problem this copy is, and why. A pure function of observed state.

    Local work is benign only where the rest of the world will find it. On the branch being built
    it is the intended workflow, because pushing that branch makes every other build see the same
    code. The same work on the default branch is a trap: your build reads the working copy, while
    every build without `--develop` resolves the dependency to the published default branch.
    """
    if not copy.exists:
        return Classification( ERROR, [
            "[{}] develop path [{}] does not exist, so this build cannot succeed".format(
                    copy.name, copy.path )
        ] )

    if not copy.is_working_copy:
        return Classification( WARNING, [
            "[{}] at [{}] is not a working copy, so its state cannot be reasoned about".format(
                    copy.name, copy.path )
        ] )

    severities = [ OK ]
    notes = []

    on_built_branch = bool( current_branch ) and copy.branch == current_branch
    on_default_branch = copy.branch == default_branch

    if copy.detached:
        severities.append( WARNING )
        notes.append( "[{}] is on a detached HEAD; it works today and is forgotten"
                      " tomorrow".format( copy.name ) )
    elif not on_built_branch and not on_default_branch:
        severities.append( WARNING )
        if current_branch:
            notes.append( "[{}] is on [{}], which is neither [{}] nor the default branch"
                          " [{}]".format( copy.name, copy.branch, current_branch,
                                          default_branch ) )
        else:
            notes.append( "[{}] is on [{}], which is not the default branch [{}]".format(
                    copy.name, copy.branch, default_branch ) )

    if copy.scm != 'git':
        severities.append( NOTE )
        notes.append( "[{}] is a {} working copy; ahead, behind and modified are not"
                      " reported for it".format( copy.name, copy.scm or "non-git" ) )
    elif not copy.detached and not copy.upstream:
        severities.append( NOTE )
        notes.append( "[{}] has no upstream branch, so ahead and behind cannot be"
                      " answered".format( copy.name ) )

    if copy.behind and copy.ahead:
        severities.append( WARNING )
        notes.append( "[{}] has diverged from [{}]: {} ahead, {} behind as of your last"
                      " fetch".format( copy.name, copy.upstream, copy.ahead, copy.behind ) )
    elif copy.behind:
        severities.append( WARNING )
        notes.append( "[{}] is {} behind [{}] as of your last fetch".format(
                copy.name, plural( copy.behind, "commit" ), copy.upstream ) )
    elif copy.ahead:
        severities.append( _local_work_severity( on_default_branch ) )
        notes.append( _local_work_note( copy, on_default_branch,
                                        plural( copy.ahead, "unpushed commit" ) ) )

    if copy.modified:
        severities.append( _local_work_severity( on_default_branch ) )
        notes.append( _local_work_note( copy, on_default_branch, "uncommitted changes" ) )

    return Classification( worst( severities ), notes )


def _local_work_severity( on_default_branch ):
    return on_default_branch and WARNING or NOTE


def _local_work_note( copy, on_default_branch, work ):
    if on_default_branch:
        return ( "[{name}] has {work} on the default branch [{branch}]; a build without"
                 " --develop resolves [{name}] to the published [{branch}] and will not see"
                 " them. Put the work on a branch named for the branch you are building, commit"
                 " it, and push it".format( name=copy.name, work=work, branch=copy.branch ) )
    return "[{}] has {} on [{}]".format( copy.name, work, copy.branch )


def update_action( copy ):
    """Whether this copy can be fast-forwarded, or why it is being left alone.

    Fast-forwarding a clean copy discards nothing and invents no commits. Everything else is a
    judgement about someone's unpublished work, so it is reported rather than resolved.
    """
    if not copy.exists:
        return Action( False, "path does not exist" )
    if not copy.is_working_copy:
        return Action( False, "not a working copy" )
    if copy.scm != 'git':
        return Action( False, "only git working copies can be updated" )
    if copy.detached:
        return Action( False, "detached HEAD" )
    if not copy.upstream:
        return Action( False, "no upstream branch" )
    if copy.modified:
        return Action( False, "uncommitted changes" )
    if copy.ahead and copy.behind:
        return Action( False, "diverged from [{}]".format( copy.upstream ) )
    if copy.ahead:
        return Action( False, "ahead of [{}]".format( copy.upstream ) )
    if not copy.behind:
        return Action( False, "already up to date" )
    return Action( True, "{} behind [{}]".format(
            plural( copy.behind, "commit" ), copy.upstream ) )


def state_summary( copy ):
    """The STATE column: what was observed, in the order that reads naturally."""
    if not copy.exists:
        return "path does not exist"
    if not copy.is_working_copy:
        return "not a working copy"

    parts = [ copy.modified is None and "unknown" or ( copy.modified and "modified" or "clean" ) ]
    if copy.ahead:
        parts.append( "{} ahead".format( copy.ahead ) )
    if copy.behind:
        parts.append( "{} behind".format( copy.behind ) )
    if copy.scm == 'git' and not copy.detached and not copy.upstream:
        parts.append( "no upstream" )
    return ", ".join( parts )


#-------------------------------------------------------------------------------
#   Observation
#-------------------------------------------------------------------------------

def inspect( name, path ):
    """Observe one develop location. Reads the working copy only; never the network."""
    if not path or not os.path.exists( path ):
        return Copy( name, path )

    try:
        state = Git.get_working_copy_state( path )
        return Copy(
                name            = name,
                path            = path,
                exists          = True,
                is_working_copy = True,
                scm             = 'git',
                branch          = state.branch,
                detached        = state.detached,
                upstream        = state.upstream,
                ahead           = state.ahead,
                behind          = state.behind,
                modified        = state.modified
        )
    except Git.Error:
        pass

    # Subversion, Mercurial and Bazaar report branch and revision. The rest stays unknown rather
    # than being guessed from a backend that cannot answer it.
    url, repository, branch, remote, revision = scms.get_current_rev_info( path )
    if branch or revision:
        return Copy( name, path, exists=True, is_working_copy=True, scm='other',
                     branch=branch, upstream=remote )

    return Copy( name, path, exists=True )


def configured_develop( dependency, cuppa_env ):
    """The develop location a dependency is configured with, and how it is resolved to a path.

    Location dependencies carry theirs in `location_id()`, which also applies the command line
    overrides, and resolve through `develop_location` — the same helper the develop swap uses.
    Package dependencies keep their own and only expand `~`, matching what
    `GitlabPackageDependency` does when it swaps.
    """
    location_id = getattr( dependency, 'location_id', None )
    if location_id:
        try:
            identity = location_id( cuppa_env )
        except Exception as error:
            logger.trace( "Could not resolve the location of [{}]: {}".format(
                    getattr( dependency, '_name', dependency ), str(error) ) )
            identity = None
        if identity and identity[1]:
            return develop_location( cuppa_env['sconstruct_dir'], identity[1] )

    manager = getattr( dependency, '_package_manager', None )
    name = getattr( dependency, '_name', None )
    if manager and name:
        override = cuppa_env.get_option( "-".join( [ name, manager, "develop" ] ) )
        if override:
            return os.path.expanduser( override )

    develop = getattr( dependency, '_develop', None )
    if develop:
        return os.path.expanduser( develop )
    return None


def survey( cuppa_env ):
    """Every dependency with a develop location, observed, whether or not --develop is active."""
    copies = []
    without_develop = []

    for name in sorted( cuppa_env['dependencies'] ):
        factory = cuppa_env['dependencies'][name]
        dependency = getattr( factory, '__self__', factory )
        path = configured_develop( dependency, cuppa_env )
        if path:
            copies.append( inspect( name, path ) )
        else:
            without_develop.append( name )

    return copies, without_develop


#-------------------------------------------------------------------------------
#   Reporting
#-------------------------------------------------------------------------------

COLUMNS = ( "DEPENDENCY", "BRANCH", "UPSTREAM", "STATE", "PATH" )

COLOUR_FOR = { OK: as_info, NOTE: as_info, WARNING: as_warning, ERROR: as_error }


def log_at( severity, message ):
    { OK: logger.info, NOTE: logger.info, WARNING: logger.warn, ERROR: logger.error }[severity](
            COLOUR_FOR[severity]( message ) )


def display_path( path ):
    if not path:
        return path
    path = os.path.normpath( path )
    home = os.path.expanduser( "~" )
    if path.startswith( home ):
        return "~" + path[len(home):]
    return path


def row_for( copy ):
    return (
        copy.name,
        copy.detached and "(detached)" or ( copy.branch or "-" ),
        copy.upstream or "-",
        state_summary( copy ),
        display_path( copy.path )
    )


def table( copies ):
    """The rows, padded to the widest value in each column including the header."""
    rows = [ COLUMNS ] + [ row_for( copy ) for copy in copies ]
    widths = [ max( len( row[column] ) for row in rows ) for column in range( len( COLUMNS ) ) ]
    return [
        "  " + "  ".join( value.ljust( width )
                          for value, width in zip( row, widths ) ).rstrip()
        for row in rows
    ]


def report( copies, without_develop, current_branch, default_branch, develop_active ):
    """Print the table, then the judgements in full, so a reason needs no column decoding."""
    if not copies:
        logger.info( "No dependencies have a develop location configured; {} dependencies"
                     " in total".format( len( without_develop ) ) )
        return OK

    classifications = [
        ( copy, classify( copy, current_branch, default_branch ) ) for copy in copies
    ]

    logger.info( "Building on branch [{}] with default branch [{}]; --develop is {}".format(
            as_info( current_branch or "unknown" ),
            as_info( default_branch ),
            develop_active and as_info_label( "active" ) or as_notice( "not active" )
    ) )

    lines = table( copies )
    logger.info( lines[0] )
    for ( copy, classification ), line in zip( classifications, lines[1:] ):
        log_at( classification.severity, line )

    counts = { OK: 0, NOTE: 0, WARNING: 0, ERROR: 0 }
    for copy, classification in classifications:
        counts[classification.severity] += 1

    logger.info( "{}: {} ok, {}, {}, {};"
                 " {} not using develop".format(
                        plural( len( copies ), "develop location" ),
                        counts[OK],
                        plural( counts[NOTE], "note" ),
                        plural( counts[WARNING], "warning" ),
                        plural( counts[ERROR], "error" ),
                        plural( len( without_develop ), "dependency", "dependencies" ) ) )

    for copy, classification in classifications:
        for note in classification.notes:
            log_at( classification.severity, note )

    logger.info( "Ahead and behind are relative to your last fetch; no remote was contacted" )

    return worst( [ classification.severity for copy, classification in classifications ] )


def list_develop( cuppa_env ):
    """`--list-develop`. Non-zero only when a develop path does not exist, because that build
    cannot succeed and a CI job should hear about it."""
    copies, without_develop = survey( cuppa_env )
    severity = report(
            copies,
            without_develop,
            cuppa_env['current_branch'],
            cuppa_env['location_default_branch'],
            cuppa_env['develop']
    )
    return severity == ERROR and 1 or 0


def update_develop( cuppa_env ):
    """`--update-develop`. Fetch, then fast-forward only where nothing can be lost."""
    if cuppa_env['offline']:
        logger.error( "--update-develop needs the network, but --offline was specified" )
        return 1

    current_branch = cuppa_env['current_branch']
    default_branch = cuppa_env['location_default_branch']
    develop_active = cuppa_env['develop']
    dry_run = cuppa_env.get_option( 'no_exec' ) and True or False

    copies, without_develop = survey( cuppa_env )
    report( copies, without_develop, current_branch, default_branch, develop_active )

    if dry_run:
        logger.info( as_info_label( "Dry run: showing what --update-develop would do" ) )

    failures = 0
    updated = []

    for copy in copies:
        observed, failed = _fetch( copy, dry_run )
        failures += failed

        action = update_action( observed )
        if not action.act:
            logger.info( "Leaving [{}] alone: {}".format(
                    as_info( observed.name ), as_notice( action.reason ) ) )
            continue

        if dry_run:
            logger.info( "Would fast-forward [{}], {}".format(
                    as_info( observed.name ), as_notice( action.reason ) ) )
            continue

        try:
            Git.fast_forward( observed.path )
            updated.append( observed.name )
            logger.info( "Fast-forwarded [{}], which was {}".format(
                    as_info( observed.name ), as_notice( action.reason ) ) )
        except Git.Error as error:
            failures += 1
            logger.error( "Could not fast-forward [{}]: {}".format(
                    as_error( observed.name ), as_error( str(error) ) ) )

    if dry_run:
        return 0

    severity = OK
    if updated:
        logger.info( "Updated {} of {} develop locations. The state is now:".format(
                len( updated ), len( copies ) ) )
        copies, without_develop = survey( cuppa_env )
        severity = report( copies, without_develop, current_branch, default_branch,
                           develop_active )
    else:
        logger.info( "Nothing could be fast-forwarded; no working copy was changed" )
        severity = worst( [ OK ] + [
            classify( copy, current_branch, default_branch ).severity for copy in copies
        ] )

    if failures:
        return 1
    return severity == ERROR and 1 or 0


def _fetch( copy, dry_run ):
    """Fetch, then observe again: the decision must be taken on what is true after the fetch."""
    if not copy.exists or copy.scm != 'git':
        return copy, 0

    if dry_run:
        logger.info( "Would fetch [{}] in [{}]".format(
                as_info( copy.name ), as_notice( display_path( copy.path ) ) ) )
        return copy, 0

    try:
        Git.fetch( copy.path )
    except Git.Error as error:
        logger.error( "Could not fetch [{}]: {}".format(
                as_error( copy.name ), as_error( str(error) ) ) )
        return copy, 1

    return inspect( copy.name, copy.path ), 0
