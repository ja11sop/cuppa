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
import shutil
import stat
import sys
import time
from collections import namedtuple


class StorageError( Exception ):
    pass


# tee, elbow, and the two continuations that sit under them, each the same width.
GLYPHS = ( "\u251c\u2500\u2500 ", "\u2514\u2500\u2500 ", "\u2502   ", "    " )
ASCII_GLYPHS = ( "+-- ", "`-- ", "|   ", "    " )

# Affirmative mark for a selected build row; ASCII where the console cannot encode it.
SELECTED_MARK = "\u2713"
ASCII_SELECTED_MARK = "*"

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


def selection_triple( status, encoding=None ):
    """Three-character selection: full ``✓✓✓``, partial ``-✓-``, none ``---`` (ASCII ``*``)."""
    mark = selected_mark( encoding )
    if status == 'full':
        return mark * 3
    if status == 'partial':
        return '-' + mark + '-'
    return '---'


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
    """Padded plain-text table: header, one row per entry. Columns are ``(key, heading)``."""
    keys = [ key for key, _heading in columns ]
    headings = [ heading for _key, heading in columns ]
    cells = [ headings ]
    for row in rows:
        cells.append( [ str( row.get( key, '' ) ) for key in keys ] )

    widths = [ max( len( cell[i] ) for cell in cells ) for i in range( len( keys ) ) ]
    lines = []
    for cell in cells:
        lines.append( "  ".join(
            value.ljust( widths[i] ) for i, value in enumerate( cell )
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


def render_json_payload( payload ):
    """Pretty-print a JSON object for ``--list-format=json``."""
    return json.dumps( payload, indent=2, sort_keys=True )
