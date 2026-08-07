#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Develop
#-------------------------------------------------------------------------------

"""Reporting on, updating, cloning, and aligning the local working copies that `--develop`
builds against.

`--develop` substitutes a working copy on disk for a retrieved dependency and says nothing about
the state of that copy, so a build can be reading someone else's spike branch, or a checkout that
has not been pulled for months. `--list-develop` answers what you are actually building against,
`--clone-develop` creates configured paths that are missing, `--update-develop` fast-forwards the
copies where doing so cannot lose work, and `--checkout-develop-branch` /
`--reset-develop-branch` align those copies onto a feature branch and back to the develop base.

The decisions are pure functions of observed state (`classify`, `update_action`, `clone_action`,
`checkout_branch_action`, `reset_branch_action`). Observation, reporting, and the git commands
are kept out of them so the rules can be tested without a repository, and so the options can
never judge the same copy differently.
"""

import locale
import os
import re
import sys
import textwrap

from collections import namedtuple

from cuppa.colourise import (
    as_error,
    as_info,
    as_info_label,
    as_notice,
    as_subdued,
    as_warning,
)
from cuppa.location import develop_location
from cuppa.log import logger
from cuppa.scms import scms
from cuppa.scms.git import Git
from cuppa.utility.storage import (
    emphasised_count_phrase,
    format_severity_count_brackets,
)


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

# Option parser const when `--reset-develop-branch` is passed with no NAME.
RESET_TO_BASE = '__BASE__'


def worst( severities ):
    return max( severities, key=lambda severity: SEVERITY_ORDER[severity] )


def plural( count, noun, plural_noun=None ):
    if count == 1:
        return "{} {}".format( count, noun )
    return "{} {}".format( count, plural_noun or noun + "s" )


def display_path( path ):
    """A develop path as somewhere you can recognise.

    Most develop paths are written relative to the sconstruct, so the resolved path carries the
    `..` segments that got it there. Those are noise in a report, and the same path has to read
    the same way in the table and in the judgement about it.
    """
    if not path:
        return path
    path = os.path.normpath( path )
    home = os.path.expanduser( "~" )
    if path.startswith( home ):
        return "~" + path[len(home):]
    return path


def effective_base_branch( cuppa_env ):
    """Develop home: configured base, else the published default."""
    base = cuppa_env.get( 'location_base_branch' )
    if base:
        return base
    return cuppa_env.get( 'location_default_branch' ) or 'master'


def normalize_base_branch( default_branch, base_branch=None ):
    """Resolve optional base for pure helpers; unset means base ≡ default."""
    if base_branch:
        return base_branch
    return default_branch


#-------------------------------------------------------------------------------
#   The rules
#-------------------------------------------------------------------------------

def classify( copy, current_branch, default_branch, base_branch=None ):
    """How much of a problem this copy is, and why. A pure function of observed state.

    Each note continues the sentence its dependency's name begins, because the report groups
    notes under that name rather than repeating it on every line.

    Local work is benign only where the rest of the world will find it. On the branch being built
    it is the intended workflow, because pushing that branch makes every other build see the same
    code. The same work on the published default branch is a trap: your build reads the working
    copy, while every build without `--develop` resolves the dependency to the published default.
    """
    base_branch = normalize_base_branch( default_branch, base_branch )

    if not copy.exists:
        return Classification( ERROR, [
            "has a develop path [{}] that does not exist, so this build cannot succeed".format(
                    display_path( copy.path ) )
        ] )

    if not copy.is_working_copy:
        return Classification( WARNING, [
            "at [{}] is not a working copy, so its state cannot be reasoned about".format(
                    display_path( copy.path ) )
        ] )

    severities = [ OK ]
    notes = []

    on_built_branch = bool( current_branch ) and copy.branch == current_branch
    on_default_branch = copy.branch == default_branch
    on_base_branch = copy.branch == base_branch
    on_acceptable = on_built_branch or on_default_branch or on_base_branch

    if copy.detached:
        severities.append( WARNING )
        notes.append( "is on a detached HEAD; it works today and is forgotten tomorrow" )
    elif not on_acceptable:
        severities.append( WARNING )
        if current_branch and base_branch != default_branch:
            notes.append(
                    "is on [{}], which is neither [{}], the develop base [{}], nor the default"
                    " branch [{}]".format(
                            copy.branch, current_branch, base_branch, default_branch )
            )
        elif current_branch:
            notes.append( "is on [{}], which is neither [{}] nor the default branch [{}]".format(
                    copy.branch, current_branch, default_branch ) )
        elif base_branch != default_branch:
            notes.append(
                    "is on [{}], which is neither the develop base [{}] nor the default branch"
                    " [{}]".format( copy.branch, base_branch, default_branch )
            )
        else:
            notes.append( "is on [{}], which is not the default branch [{}]".format(
                    copy.branch, default_branch ) )

    if copy.scm != 'git':
        severities.append( NOTE )
        notes.append( "is a {} working copy; ahead, behind and modified are not reported"
                      " for it".format( copy.scm or "non-git" ) )
    elif not copy.detached and not copy.upstream:
        severities.append( NOTE )
        notes.append( "has no upstream branch, so ahead and behind cannot be answered" )

    if copy.behind and copy.ahead:
        severities.append( WARNING )
        notes.append( "has diverged from [{}]: {} ahead, {} behind as of your last fetch".format(
                copy.upstream, copy.ahead, copy.behind ) )
    elif copy.behind:
        severities.append( WARNING )
        notes.append( "is {} behind [{}] as of your last fetch".format(
                plural( copy.behind, "commit" ), copy.upstream ) )
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
        return ( "has {work} on the default branch [{branch}]; a build without --develop resolves"
                 " it to the published [{branch}] and will not see them. Put the work on a branch"
                 " named for the branch you are building, commit it, and push it".format(
                        work=work, branch=copy.branch ) )
    return "has {} on [{}]".format( work, copy.branch )


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


def path_is_clonable_destination( path ):
    """Missing or empty directory — safe to clone into without removing anything."""
    if not path:
        return False
    if not os.path.exists( path ):
        return True
    if not os.path.isdir( path ):
        return False
    try:
        return not os.listdir( path )
    except OSError:
        return False


def looks_like_revision_pin( versioning ):
    """True when ``@versioning`` looks like a commit id rather than a branch name."""
    if not versioning:
        return False
    text = str( versioning ).strip()
    if len( text ) < 7:
        return False
    return bool( re.fullmatch( r'[0-9a-fA-F]{7,40}', text ) )


def clone_action( copy, url=None, vc_type=None, versioning=None, pinned=False ):
    """Whether this develop path should be cloned, or why it is being left alone."""
    if copy.exists and copy.is_working_copy:
        return Action( False, "already a working copy" )
    if copy.exists and not path_is_clonable_destination( copy.path ):
        return Action( False, "destination exists and is not empty" )
    if not url:
        return Action( False, "no cloneable location" )
    if vc_type != 'git':
        return Action( False, "only git locations can be cloned (got {})".format(
                vc_type or "none" ) )
    if pinned or looks_like_revision_pin( versioning ):
        return Action(
                False,
                "location pins a tag or revision; refuse a detached develop copy",
        )
    return Action( True, "clone from [{}]".format( url ) )


def checkout_branch_action( copy, target, default_branch ):
    """Whether this copy can be switched to ``target``, or why not.

    ``reason`` values that begin with ``track:``, ``create:``, or ``already:`` encode the plan
    for the orchestrator; other reasons are refusals.
    """
    if not copy.exists:
        return Action( False, "path does not exist; use --clone-develop" )
    if not copy.is_working_copy:
        return Action( False, "not a working copy" )
    if copy.scm != 'git':
        return Action( False, "only git working copies can change branch" )
    if copy.detached:
        return Action( False, "detached HEAD" )
    if copy.modified:
        return Action( False, "uncommitted changes" )
    if copy.ahead and copy.behind:
        return Action( False, "diverged from [{}]".format( copy.upstream or 'upstream' ) )
    if copy.ahead:
        return Action( False, "ahead of [{}] with unpushed commits".format(
                copy.upstream or copy.branch ) )
    if copy.branch == target:
        return Action( False, "already on [{}]".format( target ) )
    # Leaving another branch is fine when clean and not ahead; orchestrator picks track vs create.
    return Action( True, "switch to [{}]".format( target ) )


def reset_branch_action( copy, target ):
    """Whether this copy can switch to ``target`` and be fast-forwarded."""
    if not copy.exists:
        return Action( False, "path does not exist; use --clone-develop" )
    if not copy.is_working_copy:
        return Action( False, "not a working copy" )
    if copy.scm != 'git':
        return Action( False, "only git working copies can be reset" )
    if copy.detached:
        return Action( False, "detached HEAD" )
    if copy.modified:
        return Action( False, "uncommitted changes" )
    if copy.ahead and copy.behind:
        return Action( False, "diverged from [{}]".format( copy.upstream or 'upstream' ) )
    if copy.ahead:
        return Action( False, "ahead of [{}] with unpushed commits".format(
                copy.upstream or copy.branch ) )
    if copy.branch == target:
        # Still allow update_action to ff if behind.
        return Action( True, "already on [{}]".format( target ) )
    return Action( True, "checkout [{}]".format( target ) )


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
#
#   A report is what was asked for, not commentary on producing it, so it is written to standard
#   output rather than logged. Logging it would mean `--verbosity=warn` printing the warning rows
#   of a table without its header, and `-Q` printing nothing at all. The logger keeps the
#   diagnostics.
#-------------------------------------------------------------------------------

COLUMNS = ( "STATUS", "DEPENDENCY", "BRANCH", "UPSTREAM", "STATE", "PATH" )


def uncoloured( text ):
    return text


# A copy with nothing to be done about it is left in the console's own colour, so the rows that
# want attention are the only coloured ones in the table.
COLOUR_FOR = { OK: uncoloured, NOTE: as_info, WARNING: as_warning, ERROR: as_error }

# Severity has to survive --raw-output, so it is a column rather than a colour or a log prefix.
STATUS_FOR = { OK: "ok", NOTE: "note", WARNING: "warn", ERROR: "error" }

# The column abbreviates to keep the table narrow; a heading has the room to say it in full.
HEADING_FOR = { OK: "ok", NOTE: "note", WARNING: "warning", ERROR: "error" }

INDENT = "  "
RULE = "-"

# Prose is wrapped to the table's right edge so the report has one, but a wide table comes from a
# long path rather than from anything worth reading across, so the text stops at a readable width.
WIDEST_PROSE = 110
NARROWEST_PROSE = 40

# The values a note is about. Colouring these and leaving the prose plain is what lets a name be
# found in a page of text; colouring both leaves nothing to find.
VALUES = re.compile( r'\[([^\[\]]+)\]' )

# tee, elbow, and the two continuations that sit under them, each the same width.
GLYPHS = ( "\u251c\u2500\u2500 ", "\u2514\u2500\u2500 ", "\u2502   ", "    " )
ASCII_GLYPHS = ( "+-- ", "`-- ", "|   ", "    " )


Entry = namedtuple( 'Entry', [ 'copy', 'severity', 'notes' ] )


def write( text="" ):
    print( text )


def highlight_values( text, colour ):
    return VALUES.sub( lambda match: "[" + colour( match.group(1) ) + "]", text )


def action_line( text, colour=as_info ):
    """An action, indented under the table, with only the values it names picked out."""
    return INDENT + highlight_values( text, colour )


def entries( copies, current_branch, default_branch, base_branch=None ):
    """The report as data, so a renderer decides only how to present it."""
    base_branch = normalize_base_branch( default_branch, base_branch )
    return [
        Entry( copy, *classify( copy, current_branch, default_branch, base_branch ) )
        for copy in copies
    ]


def row_for( entry ):
    copy = entry.copy
    return (
        STATUS_FOR[entry.severity],
        copy.name,
        copy.detached and "(detached)" or ( copy.branch or "-" ),
        copy.upstream or "-",
        state_summary( copy ),
        display_path( copy.path )
    )


def table( entries ):
    """Header and rows as plain text, padded to the widest value in each column."""
    rows = [ COLUMNS ] + [ row_for( entry ) for entry in entries ]
    widths = [ max( len( row[column] ) for row in rows ) for column in range( len( COLUMNS ) ) ]
    return [
        INDENT + "  ".join( value.ljust( width )
                            for value, width in zip( row, widths ) ).rstrip()
        for row in rows
    ]


def table_width( entries ):
    return max( len( row ) for row in table( entries ) )


def emphasis( severity, text ):
    """A row asking for attention is shown at full strength, and everything else recedes.

    Reduced intensity is what makes a copy with nothing to be done about it quiet without hiding
    it, and it behaves the same way on a light console as on a dark one.
    """
    coloured = COLOUR_FOR[severity]( text )
    return as_subdued( coloured ) if severity in ( OK, NOTE ) else coloured


def render_table( entries ):
    """The table, ruled around the header and under the last row."""
    rows = table( entries )
    rule = as_subdued( INDENT + RULE * ( table_width( entries ) - len( INDENT ) ) )

    lines = [ rule, rows[0], rule ]
    for entry, row in zip( entries, rows[1:] ):
        lines.append( emphasis( entry.severity, row ) )
    lines.append( rule )
    return lines


def glyphs( encoding=None ):
    """Box drawing where the console can encode it, ASCII where it cannot."""
    encoding = ( encoding
                 or getattr( sys.stdout, 'encoding', None )
                 or locale.getpreferredencoding()
                 or 'ascii' )
    try:
        "".join( GLYPHS ).encode( encoding )
    except ( UnicodeError, LookupError ):
        return ASCII_GLYPHS
    return GLYPHS


def wrapped( text, width ):
    """The text as lines that fit, keeping bracketed values whole so they can still be coloured."""
    if not width:
        return [ text ]
    return textwrap.wrap( text, max( width, NARROWEST_PROSE ),
                          break_long_words=False, break_on_hyphens=False ) or [ text ]


def render_judgements( entries, width=None, encoding=None ):
    """Every judgement in one tree that hangs from the summary line: severity, then dependency,
    then reason, worst first.

    Reading down the tree is reading a work list. What must be fixed for the build to succeed is
    at the top, and what is only worth knowing is at the bottom, each dependency named once.

    A reason long enough to run past `width` is wrapped and the stem is carried down through the
    wrapped lines, so the tree stays a tree and the report keeps one right edge.
    """
    tee, elbow, pipe, gap = glyphs( encoding )
    stub = pipe.rstrip()
    lines = []

    groups = [ ( severity, [ entry for entry in entries
                             if entry.severity == severity and entry.notes ] )
               for severity in ( ERROR, WARNING, NOTE ) ]
    groups = [ group for group in groups if group[1] ]

    for index, ( severity, group ) in enumerate( groups ):
        last_group = index == len( groups ) - 1
        colour = COLOUR_FOR[severity]
        # A gap on the stem above each name, so a dependency and its reasons read as one block
        # rather than as a wall of branches.
        lines.append( as_subdued( stub ) )
        lines.append( as_subdued( last_group and elbow or tee )
                      + colour( plural( len( group ), HEADING_FOR[severity] ) ) )

        under_severity = last_group and gap or pipe
        for position, entry in enumerate( group ):
            last_entry = position == len( group ) - 1
            lines.append( as_subdued( under_severity + stub ) )
            lines.append( as_subdued( under_severity + ( last_entry and elbow or tee ) )
                          + colour( entry.copy.name ) )

            under_entry = under_severity + ( last_entry and gap or pipe )
            for note_index, note in enumerate( entry.notes ):
                last_note = note_index == len( entry.notes ) - 1
                branch = under_entry + ( last_note and elbow or tee )
                carried = under_entry + ( last_note and gap or pipe )
                for piece in wrapped( note, width and width - len( branch ) ):
                    lines.append( as_subdued( branch ) + highlight_values( piece, colour ) )
                    branch = carried

    return lines


def summary( entries, without_develop ):
    """Judgement-tree intro: emphasised subject count, then severity brackets like removal."""
    counts = { OK: 0, NOTE: 0, WARNING: 0, ERROR: 0 }
    for entry in entries:
        counts[entry.severity] += 1
    head = emphasised_count_phrase( len( entries ), "develop location" )
    brackets = format_severity_count_brackets(
            errors=counts[ERROR],
            warnings=counts[WARNING],
            notes=counts[NOTE],
    )
    return "{}: {}; {}; {}".format(
            head,
            brackets,
            plural( counts[OK], "ok" ),
            plural( len( without_develop ), "dependency", "dependencies" )
            + " not using develop",
    )


def suggestion( copies ):
    """What `--update-develop` would make of what has just been observed, or nothing when it
    would leave every copy alone.

    The decision comes from `update_action()`, the same function `--update-develop` uses, so the
    suggestion cannot promise something the option will then decline to do. It can understate,
    because `--update-develop` fetches before deciding and a fetch can find more, and the line
    says so rather than leaving the reader to discover it.
    """
    ready = names_that_would_update( copies )
    if not ready:
        return None
    return ( "Of these, --update-develop would fast-forward {} ({}) as of your last fetch;"
             " it fetches first, so it may find more".format(
                    len( ready ), ", ".join( "[{}]".format( name ) for name in ready ) ) )


def names_that_would_update( copies ):
    """Dependency names ``--update-develop`` would fast-forward as of the last fetch."""
    return [ copy.name for copy in copies if update_action( copy ).act ]


def list_payload( copies, without_develop, current_branch, default_branch, develop_active,
                  base_branch=None ):
    """Serializable report for ``--list-develop --list-format=json``."""
    base_branch = normalize_base_branch( default_branch, base_branch )
    found = entries( copies, current_branch, default_branch, base_branch )
    severities = [ entry.severity for entry in found ]
    return {
        'current_branch': current_branch,
        'default_branch': default_branch,
        'base_branch': base_branch,
        'develop_active': bool( develop_active ),
        'without_develop': list( without_develop ),
        'would_update': names_that_would_update( copies ),
        'worst_severity': worst( severities ) if severities else OK,
        'entries': [
            {
                'name': entry.copy.name,
                'path': entry.copy.path,
                'display_path': display_path( entry.copy.path ),
                'exists': entry.copy.exists,
                'is_working_copy': entry.copy.is_working_copy,
                'scm': entry.copy.scm,
                'branch': entry.copy.branch,
                'detached': entry.copy.detached,
                'upstream': entry.copy.upstream,
                'ahead': entry.copy.ahead,
                'behind': entry.copy.behind,
                'modified': entry.copy.modified,
                'severity': entry.severity,
                'status': STATUS_FOR[entry.severity],
                'state': state_summary( entry.copy ),
                'notes': list( entry.notes ),
            }
            for entry in found
        ],
    }


def report( copies, without_develop, current_branch, default_branch, develop_active, out=write,
            suggest_update=False, base_branch=None ):
    """Write the table, then the judgements in full, so a reason needs no column decoding."""
    if not copies:
        out()
        out( "No dependencies have a develop location configured; {} in total".format(
                plural( len( without_develop ), "dependency", "dependencies" ) ) )
        return OK

    base_branch = normalize_base_branch( default_branch, base_branch )
    found = entries( copies, current_branch, default_branch, base_branch )
    width = min( table_width( found ), WIDEST_PROSE )

    out()
    if base_branch != default_branch:
        out( "Building on branch [{}] with default branch [{}] and develop base [{}];"
             " --develop is {}".format(
                    as_info( current_branch or "unknown" ),
                    as_info( default_branch ),
                    as_info( base_branch ),
                    develop_active and as_info_label( "active" ) or as_notice( "not active" )
            ) )
    else:
        out( "Building on branch [{}] with default branch [{}]; --develop is {}".format(
                as_info( current_branch or "unknown" ),
                as_info( default_branch ),
                develop_active and as_info_label( "active" ) or as_notice( "not active" )
        ) )
    out()

    for line in render_table( found ):
        out( line )

    out()
    out( summary( found, without_develop ) )

    for line in render_judgements( found, width ):
        out( line )

    out()
    out( "Ahead and behind are relative to your last fetch; no remote was contacted" )

    advice = suggest_update and suggestion( copies ) or None
    if advice:
        for piece in wrapped( advice, width ):
            out( highlight_values( piece, as_info ) )

    return worst( [ entry.severity for entry in found ] )


def list_develop( cuppa_env, out=write ):
    """`--list-develop`. Non-zero only when a develop path does not exist, because that build
    cannot succeed and a CI job should hear about it."""
    copies, without_develop = survey( cuppa_env )
    current_branch = cuppa_env['current_branch']
    default_branch = cuppa_env['location_default_branch']
    base_branch = effective_base_branch( cuppa_env )
    develop_active = cuppa_env['develop']

    if cuppa_env.get( 'list_format' ) == 'json':
        from cuppa.utility import storage
        payload = list_payload(
                copies,
                without_develop,
                current_branch,
                default_branch,
                develop_active,
                base_branch=base_branch,
        )
        out( storage.render_json_payload( payload ) )
        return payload['worst_severity'] == ERROR and 1 or 0

    severity = report(
            copies,
            without_develop,
            current_branch,
            default_branch,
            develop_active,
            out,
            suggest_update=True,
            base_branch=base_branch,
    )
    return severity == ERROR and 1 or 0


def update_develop( cuppa_env, out=write ):
    """`--update-develop`. Fetch, then fast-forward only where nothing can be lost."""
    if cuppa_env['offline']:
        logger.error( "--update-develop needs the network, but --offline was specified" )
        return 1

    current_branch = cuppa_env['current_branch']
    default_branch = cuppa_env['location_default_branch']
    base_branch = effective_base_branch( cuppa_env )
    develop_active = cuppa_env['develop']
    dry_run = cuppa_env.get_option( 'no_exec' ) and True or False

    copies, without_develop = survey( cuppa_env )
    report(
            copies, without_develop, current_branch, default_branch, develop_active, out,
            base_branch=base_branch,
    )

    out()
    if dry_run:
        # No fetch happens, so the decisions shown are the ones the last fetch supports.
        out( "{} {}".format(
                as_info_label( "Dry run" ),
                "showing what --update-develop would do, judged as of your last fetch" ) )

    failures = 0
    updated = []

    for copy in copies:
        observed, failed = _fetch( copy, dry_run, out )
        failures += failed

        action = update_action( observed )
        if not action.act:
            out( action_line( "Leaving [{}] alone: {}".format(
                    observed.name, action.reason ) ) )
            continue

        if dry_run:
            out( action_line( "Would fast-forward [{}], {}".format(
                    observed.name, action.reason ) ) )
            continue

        try:
            Git.fast_forward( observed.path )
            updated.append( observed.name )
            out( action_line( "Fast-forwarded [{}], which was {}".format(
                    observed.name, action.reason ) ) )
        except Git.Error as error:
            failures += 1
            out( action_line( "Could not fast-forward [{}]: {}".format(
                    observed.name, str(error) ), as_error ) )

    if dry_run:
        return 0

    if updated:
        out()
        out( "Updated {} of {}. The state is now:".format(
                len( updated ), plural( len( copies ), "develop location" ) ) )
        copies, without_develop = survey( cuppa_env )
        severity = report(
                copies, without_develop, current_branch, default_branch,
                develop_active, out, base_branch=base_branch,
        )
    else:
        out( INDENT + "Nothing could be fast-forwarded; no working copy was changed" )
        severity = worst( [ OK ] + [
            classify( copy, current_branch, default_branch, base_branch ).severity
            for copy in copies
        ] )

    if failures:
        return 1
    return severity == ERROR and 1 or 0


def _fetch( copy, dry_run, out ):
    """Fetch, then observe again: the decision must be taken on what is true after the fetch."""
    if not copy.exists or copy.scm != 'git':
        return copy, 0

    if dry_run:
        out( action_line( "Would fetch [{}] in [{}]".format(
                copy.name, display_path( copy.path ) ) ) )
        return copy, 0

    try:
        Git.fetch( copy.path )
    except Git.Error as error:
        out( action_line( "Could not fetch [{}]: {}".format(
                copy.name, str(error) ), as_error ) )
        return copy, 1

    return inspect( copy.name, copy.path ), 0


#-------------------------------------------------------------------------------
#   Clone / branch alignment
#-------------------------------------------------------------------------------

CloneSource = namedtuple(
        'CloneSource',
        [ 'copy', 'url', 'vc_type', 'versioning', 'pinned', 'relative' ],
)


def _plain_git_url( repo_location ):
    """Strip a trailing ``.git`` path quirk only for display; return clone URL as-is."""
    return repo_location


def _versioning_is_pin( versioning, url ):
    """Heuristic: commit-shaped ``@rev``, or tag-only remote refs (checked at clone time)."""
    if looks_like_revision_pin( versioning ):
        return True
    return False


def clone_source_for_dependency( name, dependency, cuppa_env ):
    """Build a :class:`CloneSource` for one dependency, or ``None`` if no develop path."""
    from cuppa.location import Location

    path = configured_develop( dependency, cuppa_env )
    if not path:
        return None
    copy = inspect( name, path )

    location_id = getattr( dependency, 'location_id', None )
    if not location_id:
        return CloneSource( copy, None, None, None, False, False )

    try:
        identity = location_id( cuppa_env )
    except Exception:
        return CloneSource( copy, None, None, None, False, False )
    if not identity or not identity[0]:
        return CloneSource( copy, None, None, None, False, False )

    configured = identity[0]
    relative = configured.endswith( '@' )
    scm_location = configured[:-1] if relative else configured
    # Unexpanded — never Location.expand_secret.
    scm_system, vc_type, repo_location, versioning = Location.get_scm_system_and_info(
            scm_location
    )
    if not vc_type:
        return CloneSource( copy, None, None, None, False, relative )

    pinned = _versioning_is_pin( versioning, repo_location )
    # Tag pins: versioning present, not a relative-only ``@``, and not a commit — still may be
    # a branch name. Treat as pin only when commit-shaped; branch vs tag decided at clone via
    # ls-remote heads.
    return CloneSource(
            copy,
            _plain_git_url( repo_location ),
            vc_type,
            versioning or None,
            pinned,
            relative,
    )


def survey_clone_sources( cuppa_env ):
    sources = []
    without_develop = []
    for name in sorted( cuppa_env['dependencies'] ):
        factory = cuppa_env['dependencies'][name]
        dependency = getattr( factory, '__self__', factory )
        path = configured_develop( dependency, cuppa_env )
        if not path:
            without_develop.append( name )
            continue
        sources.append( clone_source_for_dependency( name, dependency, cuppa_env ) )
    return sources, without_develop


def choose_clone_branch( source, cuppa_env ):
    """Branch name for a fresh clone, or ``None`` with a refusal reason string."""
    if source.pinned:
        return None, "location pins a tag or revision; refuse a detached develop copy"
    current = cuppa_env.get( 'current_branch' )
    match_current = cuppa_env.get( 'location_match_current_branch' )
    versioning = source.versioning
    url = source.url

    if match_current and current:
        try:
            if Git.remote_branch_exists( url, current ):
                # remote_branch_exists also matches tags — require heads-only intent by checking
                # we are not only a tag. Prefer current when ls-remote --heads finds it.
                return current, None
        except Git.Error:
            pass

    if versioning:
        try:
            # Prefer heads; if only a tag matches, refuse.
            if Git.remote_branch_exists( url, versioning ):
                # Distinguish tag-only: remote_branch_exists also matches tags.
                result = Git.execute_command(
                        "{git} ls-remote --heads {repository} {branch}".format(
                                git=Git.binary(),
                                repository=url,
                                branch=versioning,
                        )
                )
                if result and versioning in result:
                    return versioning, None
                return None, "location pins a tag or revision; refuse a detached develop copy"
        except Git.Error as error:
            return None, str( error )

    try:
        default = Git.remote_default_branch( url )
    except Git.Error as error:
        return None, str( error )
    if default:
        return default, None
    return cuppa_env.get( 'location_default_branch' ), None


def clone_develop( cuppa_env, out=write ):
    """``--clone-develop``. Create missing develop working copies from unexpanded remotes."""
    if cuppa_env['offline']:
        logger.error( "--clone-develop needs the network, but --offline was specified" )
        return 1

    current_branch = cuppa_env['current_branch']
    default_branch = cuppa_env['location_default_branch']
    base_branch = effective_base_branch( cuppa_env )
    develop_active = cuppa_env['develop']
    dry_run = cuppa_env.get_option( 'no_exec' ) and True or False

    sources, without_develop = survey_clone_sources( cuppa_env )
    copies = [ source.copy for source in sources ]
    report(
            copies, without_develop, current_branch, default_branch, develop_active, out,
            base_branch=base_branch,
    )

    out()
    if dry_run:
        out( "{} {}".format(
                as_info_label( "Dry run" ),
                "showing what --clone-develop would do" ) )

    failures = 0
    cloned = []

    for source in sources:
        action = clone_action(
                source.copy,
                url=source.url,
                vc_type=source.vc_type,
                versioning=source.versioning,
                pinned=source.pinned,
        )
        if not action.act:
            out( action_line( "Leaving [{}] alone: {}".format(
                    source.copy.name, action.reason ) ) )
            continue

        branch, branch_error = choose_clone_branch( source, cuppa_env )
        if branch_error:
            failures += 1
            out( action_line( "Could not clone [{}]: {}".format(
                    source.copy.name, branch_error ), as_error ) )
            continue
        if not branch:
            failures += 1
            out( action_line( "Could not clone [{}]: no branch to land on".format(
                    source.copy.name ), as_error ) )
            continue

        if dry_run:
            out( action_line( "Would clone [{}] from [{}] on branch [{}] into [{}]".format(
                    source.copy.name,
                    source.url,
                    branch,
                    display_path( source.copy.path ),
            ) ) )
            continue

        parent = os.path.dirname( source.copy.path.rstrip( os.sep ) )
        created_parents = []
        if parent and not os.path.exists( parent ):
            os.makedirs( parent )
            created_parents.append( parent )

        try:
            if created_parents:
                out( action_line( "Created parent directories: {}".format(
                        ", ".join( display_path( p ) for p in created_parents ) ) ) )
            Git.clone( source.url, source.copy.path, branch=branch, recurse_submodules=True )
            cloned.append( source.copy.name )
            out( action_line( "Cloned [{}] from [{}] on branch [{}] into [{}]".format(
                    source.copy.name,
                    source.url,
                    branch,
                    display_path( source.copy.path ),
            ) ) )
        except Git.Error as error:
            failures += 1
            out( action_line( "Could not clone [{}]: {}".format(
                    source.copy.name, str( error ) ), as_error ) )

    if dry_run:
        return 0

    if cloned:
        out()
        out( "Cloned {} of {}. The state is now:".format(
                len( cloned ), plural( len( copies ), "develop location" ) ) )
        copies, without_develop = survey( cuppa_env )
        severity = report(
                copies, without_develop, current_branch, default_branch, develop_active, out,
                suggest_update=True,
                base_branch=base_branch,
        )
    else:
        out( INDENT + "Nothing was cloned; no working copy was created" )
        severity = worst( [ OK ] + [
            classify( copy, current_branch, default_branch, base_branch ).severity
            for copy in copies
        ] )

    if failures:
        return 1
    return severity == ERROR and 1 or 0


def _resolve_checkout_target( cuppa_env ):
    raw = cuppa_env.get( 'checkout_develop_branch' )
    if raw is None or raw is False or raw == '':
        return None, "--checkout-develop-branch requires a branch name or 'current'"
    if str( raw ) == 'current':
        current = cuppa_env.get( 'current_branch' )
        if not current:
            return None, "current branch is unknown; pass an explicit branch name"
        return current, None
    return str( raw ), None


def resolve_reset_target( cuppa_env ):
    """Branch ``--reset-develop-branch`` should land on, or ``(None, error)``."""
    raw = cuppa_env.get( 'reset_develop_branch' )
    if raw is None:
        return None, "--reset-develop-branch was not requested"
    if raw is True:
        return effective_base_branch( cuppa_env ), None
    text = str( raw )
    if text in ( RESET_TO_BASE, '', 'base' ):
        return effective_base_branch( cuppa_env ), None
    if text == 'current':
        current = cuppa_env.get( 'current_branch' )
        if not current:
            return None, "current branch is unknown; pass an explicit branch name"
        return current, None
    if text == 'default':
        return cuppa_env['location_default_branch'], None
    return text, None


def _perform_checkout( observed, target, base_branch, dry_run, out ):
    """Execute one checkout plan after a successful checkout_branch_action."""
    if dry_run:
        if Git.remote_tracking_branch_exists( observed.path, target ):
            out( action_line( "Would checkout tracking branch [{}] for [{}]".format(
                    target, observed.name ) ) )
        elif Git.local_branch_exists( observed.path, target ):
            out( action_line( "Would checkout local branch [{}] for [{}]".format(
                    target, observed.name ) ) )
        else:
            out( action_line(
                    "Would move [{}] via develop base [{}] then create branch [{}]".format(
                            observed.name, base_branch, target ) ) )
        return 0

    try:
        if Git.remote_tracking_branch_exists( observed.path, target ):
            Git.checkout_tracking_branch( observed.path, target )
            out( action_line( "Checked out tracking branch [{}] for [{}]".format(
                    target, observed.name ) ) )
            return 0
        if Git.local_branch_exists( observed.path, target ):
            Git.checkout_branch( observed.path, target )
            out( action_line( "Checked out local branch [{}] for [{}]".format(
                    target, observed.name ) ) )
            return 0

        # Base path: develop home → ff → create.
        if observed.branch != base_branch:
            Git.checkout_branch( observed.path, base_branch )
            observed = inspect( observed.name, observed.path )
        Git.fetch( observed.path )
        observed = inspect( observed.name, observed.path )
        ff = update_action( observed )
        if ff.act:
            Git.fast_forward( observed.path )
        Git.create_branch_from_head( observed.path, target )
        out( action_line( "Created branch [{}] for [{}] from updated [{}]".format(
                target, observed.name, base_branch ) ) )
        return 0
    except Git.Error as error:
        out( action_line( "Could not checkout [{}] for [{}]: {}".format(
                target, observed.name, str( error ) ), as_error ) )
        return 1


def checkout_develop_branch( cuppa_env, out=write ):
    """``--checkout-develop-branch``. Align develop copies onto a named branch."""
    if cuppa_env['offline']:
        logger.error(
                "--checkout-develop-branch needs the network, but --offline was specified"
        )
        return 1

    target, error = _resolve_checkout_target( cuppa_env )
    if error:
        logger.error( error )
        return 1

    current_branch = cuppa_env['current_branch']
    default_branch = cuppa_env['location_default_branch']
    base_branch = effective_base_branch( cuppa_env )
    develop_active = cuppa_env['develop']
    dry_run = cuppa_env.get_option( 'no_exec' ) and True or False

    copies, without_develop = survey( cuppa_env )
    report(
            copies, without_develop, current_branch, default_branch, develop_active, out,
            base_branch=base_branch,
    )
    out()
    if dry_run:
        out( "{} {}".format(
                as_info_label( "Dry run" ),
                "showing what --checkout-develop-branch would do" ) )

    failures = 0
    changed = []
    skipped_person = False

    for copy in copies:
        observed, failed = _fetch( copy, dry_run, out )
        failures += failed
        action = checkout_branch_action( observed, target, base_branch )
        if not action.act:
            if action.reason.startswith( 'already on' ):
                out( action_line( "Leaving [{}] alone: {}".format(
                        observed.name, action.reason ) ) )
            else:
                skipped_person = True
                out( action_line( "Leaving [{}] alone: {}".format(
                        observed.name, action.reason ) ) )
            continue

        result = _perform_checkout( observed, target, base_branch, dry_run, out )
        failures += result
        if not dry_run and result == 0:
            changed.append( observed.name )

    if dry_run:
        return 0

    if changed:
        out()
        out( "Switched {} of {}. The state is now:".format(
                len( changed ), plural( len( copies ), "develop location" ) ) )
        copies, without_develop = survey( cuppa_env )
        severity = report(
                copies, without_develop, current_branch, default_branch, develop_active, out,
                base_branch=base_branch,
        )
    else:
        out( INDENT + "No develop branch was switched" )
        copies, without_develop = survey( cuppa_env )
        severity = report(
                copies, without_develop, current_branch, default_branch, develop_active, out,
                base_branch=base_branch,
        )

    if skipped_person:
        out()
        out( "Resolve dirty or unpushed copies with git locally, then "
             "cuppa -Q -D --list-develop" )

    if failures:
        return 1
    return severity == ERROR and 1 or 0


def reset_develop_branch( cuppa_env, out=write ):
    """``--reset-develop-branch``. Return develop copies to the develop base (or named target)."""
    if cuppa_env['offline']:
        logger.error( "--reset-develop-branch needs the network, but --offline was specified" )
        return 1

    target, error = resolve_reset_target( cuppa_env )
    if error:
        logger.error( error )
        return 1

    current_branch = cuppa_env['current_branch']
    default_branch = cuppa_env['location_default_branch']
    base_branch = effective_base_branch( cuppa_env )
    develop_active = cuppa_env['develop']
    dry_run = cuppa_env.get_option( 'no_exec' ) and True or False

    copies, without_develop = survey( cuppa_env )
    report(
            copies, without_develop, current_branch, default_branch, develop_active, out,
            base_branch=base_branch,
    )
    out()
    if dry_run:
        out( "{} {}".format(
                as_info_label( "Dry run" ),
                "showing what --reset-develop-branch would do" ) )

    failures = 0
    changed = []
    skipped_person = False

    for copy in copies:
        observed, failed = _fetch( copy, dry_run, out )
        failures += failed
        action = reset_branch_action( observed, target )
        if not action.act:
            skipped_person = True
            out( action_line( "Leaving [{}] alone: {}".format(
                    observed.name, action.reason ) ) )
            continue

        if dry_run:
            if observed.branch != target:
                out( action_line( "Would checkout [{}] for [{}]".format(
                        target, observed.name ) ) )
            out( action_line( "Would fetch and fast-forward [{}] if behind".format(
                    observed.name ) ) )
            continue

        try:
            if observed.branch != target:
                Git.checkout_branch( observed.path, target )
                observed = inspect( observed.name, observed.path )
                out( action_line( "Checked out [{}] for [{}]".format(
                        target, observed.name ) ) )
            Git.fetch( observed.path )
            observed = inspect( observed.name, observed.path )
            ff = update_action( observed )
            if ff.act:
                Git.fast_forward( observed.path )
                out( action_line( "Fast-forwarded [{}], which was {}".format(
                        observed.name, ff.reason ) ) )
            else:
                out( action_line( "Left [{}] on [{}]: {}".format(
                        observed.name, target, ff.reason ) ) )
            changed.append( observed.name )
        except Git.Error as error:
            failures += 1
            out( action_line( "Could not reset [{}]: {}".format(
                    observed.name, str( error ) ), as_error ) )

    if dry_run:
        return 0

    if changed:
        out()
        out( "Reset {} of {}. The state is now:".format(
                len( changed ), plural( len( copies ), "develop location" ) ) )
    else:
        out( INDENT + "No develop branch was reset" )

    copies, without_develop = survey( cuppa_env )
    severity = report(
            copies, without_develop, current_branch, default_branch, develop_active, out,
            base_branch=base_branch,
    )

    if skipped_person:
        out()
        out( "Resolve dirty or unpushed copies with git locally, then "
             "cuppa -Q -D --list-develop" )

    if failures:
        return 1
    return severity == ERROR and 1 or 0
