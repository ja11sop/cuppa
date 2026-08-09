#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Storage helpers — sizing, containment, removal, tables
#-------------------------------------------------------------------------------

"""Shared helpers for listing and removing what cuppa keeps on disk.

Phase 2 uses these for builds; later phases reuse the same table shape, containment rules, and
sizing for dependencies and downloads so the reports never disagree about how a path is judged.
"""

import json
import locale
import os
import re
import shutil
import stat
import sys
import textwrap
import time
from collections import namedtuple

from cuppa.utility.preprocess import AnsiEscape


class StorageError( Exception ):
    pass


# CSI / OSC sequences inflate len(); table padding and rule widths must ignore them.
_ANSI_ESCAPE_RE = AnsiEscape.ansi_escape_re


def visible_len( text ):
    """Display width of ``text`` with ANSI escape sequences removed."""
    return len( _ANSI_ESCAPE_RE.sub( '', str( text ) ) )


def pad_visible( text, width ):
    """Left-justify ``text`` to a visible width of ``width`` columns."""
    text = str( text )
    pad = width - visible_len( text )
    if pad <= 0:
        return text
    return text + ( ' ' * pad )


# tee, elbow, and the two continuations that sit under them, each the same width.
GLYPHS = ( "\u251c\u2500\u2500 ", "\u2514\u2500\u2500 ", "\u2502   ", "    " )
ASCII_GLYPHS = ( "+-- ", "`-- ", "|   ", "    " )

# Affirmative mark for a selected / removed build row; ASCII where the console cannot encode it.
SELECTED_MARK = "\u2713"
ASCII_SELECTED_MARK = "*"
# Heavier form used when a fully matched name-row mark is emphasised.
HEAVY_SELECTED_MARK = "\u2714"

# Ballot for a removal that failed; ASCII where the console cannot encode it.
FAILED_MARK = "\u2717"
ASCII_FAILED_MARK = "x"
# Heavier form used when a fully matched name-row mark is emphasised.
HEAVY_FAILED_MARK = "\u2718"

DirectoryStats = namedtuple( 'DirectoryStats', [ 'bytes', 'mtime' ] )


def human_size( nbytes ):
    """Human-readable size using 1024-based units, matching common ``du -h`` output."""
    if nbytes is None:
        return '-'
    value = float( nbytes )
    for unit in ( 'B', 'K', 'M', 'G', 'T', 'P' ):
        if value < 1024.0 or unit == 'P':
            if unit == 'B':
                return "{}B".format( int( value ) )
            formatted = "{:.1f}".format( value )
            if formatted.endswith( '.0' ):
                formatted = formatted[:-2]
            return formatted + unit
        value /= 1024.0
    return "{}P".format( int( value ) )


def relative_age( mtime, now=None ):
    """How long ago ``mtime`` was, in words suited to a listing column."""
    if mtime is None:
        return '-'
    now = time.time() if now is None else now
    seconds = max( 0, int( now - mtime ) )
    days = seconds // 86400
    if days < 1:
        return 'today'
    if days == 1:
        return 'yesterday'
    if days < 14:
        return "{} days ago".format( days )
    weeks = days // 7
    if days < 60:
        return "{} weeks ago".format( weeks )
    months = days // 30
    if days < 730:
        return "{} month ago".format( months ) if months == 1 else "{} months ago".format( months )
    years = days // 365
    return "{} year ago".format( years ) if years == 1 else "{} years ago".format( years )


def display_path( path ):
    """A path with the home directory replaced by ``~``, normalised for a report."""
    if not path:
        return path
    path = os.path.normpath( path )
    home = os.path.expanduser( '~' )
    if path == home:
        return '~'
    prefix = home + os.sep
    if path.startswith( prefix ):
        return '~' + path[len( home ):]
    return path


def _console_encoding( encoding=None ):
    return ( encoding
             or getattr( sys.stdout, 'encoding', None )
             or locale.getpreferredencoding()
             or 'ascii' )


def glyphs( encoding=None ):
    """Box drawing where the console can encode it, ASCII where it cannot."""
    try:
        "".join( GLYPHS ).encode( _console_encoding( encoding ) )
    except ( UnicodeError, LookupError ):
        return ASCII_GLYPHS
    return GLYPHS


def selected_mark( encoding=None ):
    """Check mark where the console can encode it, ``*`` where it cannot."""
    try:
        SELECTED_MARK.encode( _console_encoding( encoding ) )
    except ( UnicodeError, LookupError ):
        return ASCII_SELECTED_MARK
    return SELECTED_MARK


def failed_mark( encoding=None ):
    """Ballot mark where the console can encode it, ``x`` where it cannot."""
    try:
        FAILED_MARK.encode( _console_encoding( encoding ) )
    except ( UnicodeError, LookupError ):
        return ASCII_FAILED_MARK
    return FAILED_MARK


def with_heavy_marks( text, encoding=None ):
    """Upgrade light ``✓`` / ``✗`` to heavy ``✔`` / ``✘`` when the console can encode them."""
    if not text:
        return text
    try:
        ( HEAVY_SELECTED_MARK + HEAVY_FAILED_MARK ).encode( _console_encoding( encoding ) )
    except ( UnicodeError, LookupError ):
        return text
    return text.replace( SELECTED_MARK, HEAVY_SELECTED_MARK ).replace(
        FAILED_MARK, HEAVY_FAILED_MARK
    )


def selection_triple( status, encoding=None ):
    """Three-character selection: full ``✓✓✓``, partial ``-✓-``, none ``---`` (ASCII ``*``)."""
    mark = selected_mark( encoding )
    if status == 'full':
        return mark * 3
    if status == 'partial':
        return '-' + mark + '-'
    return '---'


def outcome_triple( selection, result, encoding=None ):
    """Rollup mark for a removal report: checks for success, ballots for failure.

    ``result`` is ``removed``, ``failed``, ``mixed``, or ``none``.
    All-failed rollups are ``✗✗✗``; mixed success and failure is ``✓-✗``; all-removed follows
    the usual full / partial check pattern.
    """
    if result == 'none' or selection == 'none':
        return '---' if selection != 'none' else ''
    ok = selected_mark( encoding )
    bad = failed_mark( encoding )
    if result == 'removed':
        if selection == 'full':
            return ok * 3
        return '-' + ok + '-'
    if result == 'failed':
        return bad * 3
    # mixed: some removed, some failed
    return ok + '-' + bad


def outcome_binary( result, encoding=None ):
    """Single-slot mark when a parent has only one actionable child (e.g. a VCS branch)."""
    if result in ( None, 'none' ):
        return '-'
    ok = selected_mark( encoding )
    bad = failed_mark( encoding )
    if result == 'removed':
        return ok
    if result == 'failed':
        return bad
    if result == 'mixed':
        return ok + bad
    return '-'


def short_path( path, project_dir=None ):
    """Prefer a project-relative path, otherwise ``~``, for report text."""
    if not path:
        return path
    path = os.path.normpath( path )
    if project_dir:
        project = real_path( project_dir )
        real = real_path( path )
        try:
            common = os.path.commonpath( [ real, project ] )
        except ValueError:
            common = None
        if common == project:
            relative = os.path.relpath( real, project )
            return relative if relative != '.' else os.path.basename( project ) or '.'
    return display_path( path )


def shorten_paths_in_text( text, project_dir=None ):
    """Replace absolute / home paths in ``text`` with :func:`short_path` forms."""
    if not text:
        return text

    def replace( match ):
        quote = match.group( 1 ) or ''
        raw = match.group( 2 ) or match.group( 3 )
        shortened = short_path( raw, project_dir=project_dir )
        if quote:
            return quote + shortened + quote
        return shortened

    # Quoted paths first, then bare absolute / home paths.
    pattern = re.compile(
        r"(['\"])([^'\"]+)\1|(?<![\w./])(~?/[^\s\"']+)"
    )
    return pattern.sub( replace, text )


# Bracketed placeholders in report prose — colour these, leave the surrounding text plain
# (same convention as ``--list-develop``).
_VALUES = re.compile( r'\[([^\[\]]+)\]' )
WIDEST_PROSE = 110
NARROWEST_PROSE = 40


def highlight_values( text, colour ):
    """Colour only ``[placeholder]`` spans in otherwise plain report prose."""
    return _VALUES.sub( lambda match: "[" + colour( match.group( 1 ) ) + "]", text )


def format_severity_count_brackets( errors=0, warnings=0, notes=0 ):
    """Always ``[N errors][N warnings][N notes]``; mute zeros, colour non-zeros.

    Non-zero brackets use error / warning / info colour so removal and ``--list-develop``
    judgement intros share one look.
    """
    from cuppa.colourise import as_error, as_info, as_subdued, as_warning

    specs = (
            ( errors, 'error', 'errors', as_error ),
            ( warnings, 'warning', 'warnings', as_warning ),
            ( notes, 'note', 'notes', as_info ),
    )
    parts = []
    for count, singular, plural_noun, colour in specs:
        label = '{} {}'.format( count, singular if count == 1 else plural_noun )
        text = '[{}]'.format( label )
        parts.append( colour( text ) if count else as_subdued( text ) )
    return ''.join( parts )


def emphasised_count_phrase( count, noun, plural_noun=None ):
    """``{emphasised N} {noun}`` / plural — shared subject count for judgement intros."""
    from cuppa.colourise import as_emphasised

    word = noun if count == 1 else ( plural_noun or noun + 's' )
    return "{} {}".format( as_emphasised( str( count ) ), word )


def wrapped( text, width ):
    """Wrap prose, keeping bracketed values whole so they can still be coloured."""
    if not width:
        return [ text ]
    return textwrap.wrap(
        text, max( width, NARROWEST_PROSE ),
        break_long_words=False, break_on_hyphens=False
    ) or [ text ]


def directory_stats( path ):
    """Total size and newest modification time under ``path``. Symlinks are not followed."""
    total = 0
    newest = None
    if not os.path.exists( path ):
        return DirectoryStats( 0, None )
    if os.path.islink( path ) or os.path.isfile( path ):
        info = os.lstat( path )
        return DirectoryStats( info.st_size, info.st_mtime )

    for root, dirnames, filenames in os.walk( path, followlinks=False ):
        dirnames[:] = [
            name for name in dirnames
            if not os.path.islink( os.path.join( root, name ) )
        ]
        try:
            root_mtime = os.lstat( root ).st_mtime
            newest = root_mtime if newest is None else max( newest, root_mtime )
        except OSError:
            pass
        for name in filenames:
            filepath = os.path.join( root, name )
            try:
                info = os.lstat( filepath )
            except OSError:
                continue
            if stat.S_ISREG( info.st_mode ) or stat.S_ISLNK( info.st_mode ):
                total += info.st_size
                newest = info.st_mtime if newest is None else max( newest, info.st_mtime )
    return DirectoryStats( total, newest )


def directory_size( path ):
    """Total size of regular files under ``path``. Symlinks are not followed."""
    return directory_stats( path ).bytes


def real_path( path ):
    return os.path.realpath( os.path.expanduser( path ) )


def is_contained( path, root ):
    """True when ``path`` resolves inside ``root`` (both realpath'd)."""
    if not path or not root:
        return False
    real = real_path( path )
    base = real_path( root )
    try:
        common = os.path.commonpath( [ real, base ] )
    except ValueError:
        return False
    return common == base


def is_suspicious_root( path ):
    """Roots that must never be removed wholesale, regardless of configuration."""
    if not path:
        return True
    real = real_path( path )
    home = real_path( os.path.expanduser( '~' ) )
    if real in ( os.sep, home ):
        return True
    # Drive roots on Windows look like ``C:\``.
    parent, name = os.path.split( real.rstrip( os.sep ) )
    if name == '' or parent == real:
        return True
    return False


def ensure_contained( path, root, what="path" ):
    if not is_contained( path, root ):
        raise StorageError(
            "{} [{}] is outside managed root [{}]".format( what, path, root )
        )


def remove_path( path, dry_run=False ):
    """Remove a file, symlink, or directory tree. Refuses to follow a symlink directory."""
    if not os.path.lexists( path ):
        return False

    if os.path.islink( path ) or os.path.isfile( path ):
        if not dry_run:
            os.unlink( path )
        return True

    if os.path.isdir( path ):
        if not dry_run:
            shutil.rmtree( path )
        return True

    return False


def prune_empty_parents( path, stop_at ):
    """Remove empty directories from ``path`` up to, but not including, ``stop_at``."""
    stop_at = real_path( stop_at )
    current = real_path( path ) if os.path.isdir( path ) else real_path( os.path.dirname( path ) )

    while current and current != stop_at and is_contained( current, stop_at ):
        try:
            os.rmdir( current )
        except OSError:
            break
        parent = os.path.dirname( current )
        if parent == current:
            break
        current = parent


def render_table( columns, rows ):
    """Padded plain-text table: header, one row per entry. Columns are ``(key, heading)``.

    Widths use visible length so cells that already carry ANSI colour still align with
    plain headers and with rows painted differently (e.g. referenced vs unreferenced).
    """
    keys = [ key for key, _heading in columns ]
    headings = [ heading for _key, heading in columns ]
    cells = [ headings ]
    for row in rows:
        cells.append( [ str( row.get( key, '' ) ) for key in keys ] )

    widths = [ max( visible_len( cell[i] ) for cell in cells ) for i in range( len( keys ) ) ]
    lines = []
    for cell in cells:
        lines.append( "  ".join(
            pad_visible( value, widths[i] ) for i, value in enumerate( cell )
        ).rstrip() )
    return lines


def render_json( columns, rows, total_bytes=None, extra=None ):
    keys = [ key for key, _heading in columns ]
    entries = []
    for row in rows:
        entry = { key: row.get( key ) for key in keys }
        if 'size_bytes' in row:
            entry['size_bytes'] = row['size_bytes']
        entries.append( entry )
    payload = { 'entries': entries }
    if total_bytes is not None:
        payload['total_bytes'] = total_bytes
        payload['total'] = human_size( total_bytes )
    if extra:
        payload.update( extra )
    return render_json_payload( payload )


def _json_is_multiline( value ):
    """Non-empty objects and arrays get Allman bracing; scalars and empties stay inline."""
    if isinstance( value, dict ):
        return bool( value )
    if isinstance( value, list ):
        return bool( value )
    return False


def _dumps_allman( value, indent=4, level=0 ):
    """Serialize JSON with 4-space indent and braces/brackets on the next line."""
    pad = ' ' * ( indent * level )
    child = ' ' * ( indent * ( level + 1 ) )

    if isinstance( value, dict ):
        if not value:
            return '{}'
        lines = [ '{' ]
        items = sorted( value.items() )
        for index, ( key, item ) in enumerate( items ):
            comma = ',' if index < len( items ) - 1 else ''
            key_text = json.dumps( key )
            if _json_is_multiline( item ):
                rendered = _dumps_allman( item, indent=indent, level=level + 1 )
                lines.append( '{}{}:\n{}{}{}'.format(
                        child, key_text, child, rendered, comma
                ) )
            else:
                lines.append( '{}{}: {}{}'.format(
                        child, key_text, _dumps_allman( item, indent=indent, level=level + 1 ),
                        comma
                ) )
        lines.append( '{}{}'.format( pad, '}' ) )
        return '\n'.join( lines )

    if isinstance( value, list ):
        if not value:
            return '[]'
        lines = [ '[' ]
        for index, item in enumerate( value ):
            comma = ',' if index < len( value ) - 1 else ''
            if _json_is_multiline( item ):
                rendered = _dumps_allman( item, indent=indent, level=level + 1 )
                lines.append( '{}{}{}'.format( child, rendered, comma ) )
            else:
                lines.append( '{}{}{}'.format(
                        child,
                        _dumps_allman( item, indent=indent, level=level + 1 ),
                        comma
                ) )
        lines.append( '{}{}'.format( pad, ']' ) )
        return '\n'.join( lines )

    return json.dumps( value )


def render_json_payload( payload ):
    """Pretty-print JSON for ``--list-format=json`` (4-space Allman braces)."""
    return _dumps_allman( payload )
