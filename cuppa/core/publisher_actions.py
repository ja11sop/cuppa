#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Publisher forest listing and removal — --list-publishers / --remove-publishers
#-------------------------------------------------------------------------------

"""Inspect and reclaim git publisher trees under the in-force publisher root.

Sibling storage-action flags to ``--list-downloads`` / ``--remove-dependencies`` (different
root + containment). The list report matches ``--list-develop`` chrome (ruled STATUS table,
judgement tree, update hint) with an added SIZE column for reclaim.
"""

from __future__ import annotations

import logging
import os
import sys
from collections import namedtuple

from cuppa.colourise import as_emphasised, as_error, as_info, as_info_label, as_subdued, as_warning
from cuppa.utility import storage
from cuppa.utility.storage import (
        WIDEST_PROSE,
        emphasised_count_phrase,
        format_severity_count_brackets,
        highlight_values,
        wrapped,
)

logger = logging.getLogger( __name__ )

INDENT = "  "
RULE = "-"

COLUMNS = ( "STATUS", "SIZE", "PUBLISHER", "BRANCH", "UPSTREAM", "STATE", "PATH" )

PublisherEntry = namedtuple(
        'PublisherEntry',
        [ 'copy', 'severity', 'notes', 'status', 'size', 'size_bytes', 'develop_linked' ],
)


def add_publisher_action_options( add_option ):
    add_option(
            '--list-publishers', dest='list_publishers', action='store_true',
            help="List publisher working copies under the in-force publisher root "
                 "(--publisher-root, else <storage-root>/publishers) and exit",
    )
    add_option(
            '--remove-publishers', dest='remove_publishers', type='string', nargs=1,
            action='store',
            help="Remove named publisher trees under the in-force publisher root "
                 "(comma-separated folder names), then exit",
    )
    add_option(
            '--remove-all-publishers', dest='remove_all_publishers', action='store_true',
            help="Remove every publisher tree under the in-force publisher root, then exit",
    )


def process_publisher_action_options( cuppa_env ):
    cuppa_env['list_publishers'] = bool( cuppa_env.get_option( 'list_publishers' ) )
    cuppa_env['remove_all_publishers'] = bool( cuppa_env.get_option( 'remove_all_publishers' ) )
    remove = cuppa_env.get_option( 'remove_publishers' )
    if isinstance( remove, ( list, tuple ) ):
        remove = remove[0] if remove else None
    cuppa_env['remove_publishers'] = remove


def wants_publisher_action( cuppa_env ):
    return bool(
            cuppa_env.get( 'list_publishers' )
            or cuppa_env.get( 'remove_publishers' )
            or cuppa_env.get( 'remove_all_publishers' )
    )


def _looks_like_publisher_tree( path: str ) -> bool:
    if not os.path.isdir( path ) or os.path.islink( path ):
        return False
    if os.path.isdir( os.path.join( path, '.git' ) ):
        return True
    if os.path.isfile( os.path.join( path, 'sconstruct' ) ):
        return True
    if os.path.isfile( os.path.join( path, 'cuppa-publish.json' ) ):
        return True
    return False


def _develop_realpaths( cuppa_env ) -> set[str]:
    """Configured develop= locations that must never be removed via publishers."""
    paths: set[str] = set()
    try:
        from cuppa import develop
        copies, _without = develop.survey( cuppa_env )
    except Exception:
        return paths
    for copy in copies:
        if not copy.path or not os.path.exists( copy.path ):
            continue
        try:
            paths.add( storage.real_path( copy.path ) )
        except OSError:
            continue
    return paths


def _branch_context( cuppa_env ):
    """Tip branch context for develop-style classify; defaults when unset in unit tests."""
    from cuppa import develop
    current = cuppa_env.get( 'current_branch' ) or 'master'
    default = cuppa_env.get( 'location_default_branch' ) or 'master'
    try:
        base = develop.effective_base_branch( cuppa_env )
    except Exception:
        base = default
    if not base:
        base = default
    return current, default, base


def collect_publisher_rows( cuppa_env ):
    """Return listing data for ``--list-publishers`` (copies + sizes + develop-linked)."""
    from cuppa.package_managers import package_cascade
    from cuppa.develop import (
            NOTE,
            STATUS_FOR,
            classify,
            inspect,
            update_action,
            worst,
    )

    root = package_cascade.publisher_lookup_root( cuppa_env )
    develop_paths = _develop_realpaths( cuppa_env )
    current_branch, default_branch, base_branch = _branch_context( cuppa_env )
    entries = []
    copies = []
    total_bytes = 0

    if not os.path.isdir( root ):
        return {
                'publishers_root': root,
                'entries': entries,
                'copies': copies,
                'rows': [],  # compat for remove_publishers
                'total_bytes': 0,
                'tree_count': 0,
                'worst_severity': 'ok',
                'would_update': [],
                'current_branch': current_branch,
                'default_branch': default_branch,
                'base_branch': base_branch,
        }

    try:
        names = sorted( os.listdir( root ) )
    except OSError as error:
        raise storage.StorageError(
                "cannot list publisher root [{}]: {}".format( root, error )
        ) from error

    for name in names:
        if name.startswith( '.' ):
            continue
        path = os.path.join( root, name )
        if not _looks_like_publisher_tree( path ):
            continue
        try:
            real = storage.real_path( path )
        except OSError:
            real = path
        observed = inspect( name, path )
        size_bytes = int( storage.directory_size( path ) or 0 )
        total_bytes += size_bytes
        develop_linked = real in develop_paths
        classification = classify(
                observed, current_branch, default_branch, base_branch=base_branch,
        )
        notes = list( classification.notes )
        severity = classification.severity
        if develop_linked:
            notes.append(
                    "matches a configured develop= path; use --list-develop / "
                    "--update-develop for that working copy, and --remove-publishers "
                    "will skip it"
            )
            severity = worst( [ severity, NOTE ] )
        entry = PublisherEntry(
                copy=observed,
                severity=severity,
                notes=notes,
                status=STATUS_FOR[severity],
                size=storage.human_size( size_bytes ),
                size_bytes=size_bytes,
                develop_linked=develop_linked,
        )
        entries.append( entry )
        copies.append( observed )

    would_update = [
            copy.name for copy in copies if update_action( copy ).act
    ]

    # Flat rows for remove_publishers / older callers.
    rows = [
            {
                    'name': entry.copy.name,
                    'path': entry.copy.path,
                    'real_path': (
                            storage.real_path( entry.copy.path )
                            if entry.copy.path and os.path.exists( entry.copy.path )
                            else entry.copy.path
                    ),
                    'size_bytes': entry.size_bytes,
                    'size': entry.size,
                    'branch': (
                            "(detached)" if entry.copy.detached
                            else ( entry.copy.branch or "-" )
                    ),
                    'upstream': entry.copy.upstream or "-",
                    'state': entry.status,
                    'status': entry.status,
                    'develop_linked': entry.develop_linked,
                    'modified': bool( entry.copy.modified ),
                    'scm': entry.copy.scm or "-",
                    'exists': bool( entry.copy.exists ),
            }
            for entry in entries
    ]

    return {
            'publishers_root': root,
            'entries': entries,
            'copies': copies,
            'rows': rows,
            'total_bytes': total_bytes,
            'tree_count': len( entries ),
            'worst_severity': worst( [ e.severity for e in entries ] ) if entries else 'ok',
            'would_update': would_update,
            'current_branch': current_branch,
            'default_branch': default_branch,
            'base_branch': base_branch,
    }


def _row_cells( entry: PublisherEntry ):
    from cuppa.develop import state_summary
    from cuppa.utility.storage import display_path
    copy = entry.copy
    return (
            entry.status,
            entry.size or "-",
            copy.name,
            copy.detached and "(detached)" or ( copy.branch or "-" ),
            copy.upstream or "-",
            state_summary( copy ),
            display_path( copy.path ),
    )


def _plain_table_lines( entries ):
    rows = [ COLUMNS ] + [ _row_cells( entry ) for entry in entries ]
    widths = [ max( len( row[column] ) for row in rows ) for column in range( len( COLUMNS ) ) ]
    return [
            INDENT + "  ".join(
                    value.ljust( width ) for value, width in zip( row, widths )
            ).rstrip()
            for row in rows
    ]


def _table_width( entries ):
    return max( len( line ) for line in _plain_table_lines( entries ) )


def _emphasis( severity, text ):
    from cuppa.develop import COLOUR_FOR, NOTE, OK
    coloured = COLOUR_FOR[severity]( text )
    return as_subdued( coloured ) if severity in ( OK, NOTE ) else coloured


def _render_ruled_table( entries ):
    rows = _plain_table_lines( entries )
    rule = as_subdued( INDENT + RULE * ( _table_width( entries ) - len( INDENT ) ) )
    lines = [ rule, rows[0], rule ]
    for entry, row in zip( entries, rows[1:] ):
        lines.append( _emphasis( entry.severity, row ) )
    lines.append( rule )
    return lines


def _summary_line( entries, total_bytes ):
    from cuppa.develop import ERROR, NOTE, OK, WARNING, plural
    counts = { OK: 0, NOTE: 0, WARNING: 0, ERROR: 0 }
    for entry in entries:
        counts[entry.severity] += 1
    head = emphasised_count_phrase( len( entries ), "publisher tree" )
    brackets = format_severity_count_brackets(
            errors=counts[ERROR],
            warnings=counts[WARNING],
            notes=counts[NOTE],
    )
    return "{}: {}; {}; {} total".format(
            head,
            brackets,
            plural( counts[OK], "ok" ),
            storage.human_size( total_bytes ),
    )


def _update_suggestion( would_update ):
    if not would_update:
        return None
    return (
            "Of these, --update-publishers would fast-forward {} ({}) as of your last "
            "fetch; it fetches first, so it may find more".format(
                    len( would_update ),
                    ", ".join( "[{}]".format( name ) for name in would_update ),
            )
    )


def write_list_publishers_report( out, data ):
    """Human-readable ``--list-publishers`` body (develop chrome + SIZE)."""
    from cuppa.develop import render_judgements

    root = data.get( 'publishers_root' )
    entries = data.get( 'entries' ) or []
    out.write( "\n" )
    out.write( "Publishers in {}\n".format(
            as_info( storage.display_path( root ) ) if root else '-'
    ) )
    out.write( "\n" )

    if not entries:
        out.write( "{}(empty)\n".format( INDENT ) )
        out.write( "{}0 publisher trees, {} total\n".format(
                INDENT, storage.human_size( 0 ),
        ) )
        return

    for line in _render_ruled_table( entries ):
        out.write( line + "\n" )

    out.write( "\n" )
    out.write( _summary_line( entries, data.get( 'total_bytes' ) or 0 ) + "\n" )

    # Adapt PublisherEntry to the shape render_judgements expects (Entry with .copy.name).
    judgement_entries = [
            type( 'E', (), {
                    'copy': entry.copy,
                    'severity': entry.severity,
                    'notes': entry.notes,
                    'status': entry.status,
            } )()
            for entry in entries
    ]
    width = min( _table_width( entries ), WIDEST_PROSE )
    for line in render_judgements( judgement_entries, width ):
        out.write( line + "\n" )

    out.write( "\n" )
    out.write( "Ahead and behind are relative to your last fetch; no remote was contacted\n" )

    advice = _update_suggestion( data.get( 'would_update' ) or [] )
    if advice:
        for piece in wrapped( advice, width ):
            out.write( highlight_values( piece, as_info ) + "\n" )

    if any( entry.develop_linked for entry in entries ):
        out.write( "\n" )
        out.write(
                "A note of develop-linked means this forest path matches a configured "
                "develop= working copy — prefer --list-develop / --update-develop for "
                "that copy; --remove-publishers will skip it.\n"
        )


def list_publishers( construct, cuppa_env, out=None ):
    """``--list-publishers``. Non-zero when any forest tree has error severity."""
    del construct  # forest is disk-only
    from cuppa.develop import ERROR

    out = out or sys.stdout
    list_format = cuppa_env.get( 'list_format' ) or 'text'
    data = collect_publisher_rows( cuppa_env )

    if list_format == 'json':
        from cuppa.develop import state_summary
        payload = {
                'publishers_root': data.get( 'publishers_root' ),
                'tree_count': data.get( 'tree_count' ) or 0,
                'total_bytes': data.get( 'total_bytes' ) or 0,
                'current_branch': data.get( 'current_branch' ),
                'default_branch': data.get( 'default_branch' ),
                'base_branch': data.get( 'base_branch' ),
                'would_update': list( data.get( 'would_update' ) or [] ),
                'worst_severity': data.get( 'worst_severity' ) or 'ok',
                'entries': [
                        {
                                'name': entry.copy.name,
                                'path': entry.copy.path,
                                'display_path': storage.display_path( entry.copy.path ),
                                'size': entry.size,
                                'size_bytes': entry.size_bytes,
                                'exists': bool( entry.copy.exists ),
                                'is_working_copy': bool( entry.copy.is_working_copy ),
                                'scm': entry.copy.scm,
                                'branch': entry.copy.branch,
                                'detached': bool( entry.copy.detached ),
                                'upstream': entry.copy.upstream,
                                'ahead': entry.copy.ahead,
                                'behind': entry.copy.behind,
                                'modified': entry.copy.modified,
                                'severity': entry.severity,
                                'status': entry.status,
                                'state': state_summary( entry.copy ),
                                'notes': list( entry.notes ),
                                'develop_linked': bool( entry.develop_linked ),
                        }
                        for entry in ( data.get( 'entries' ) or [] )
                ],
        }
        out.write( storage.render_json_payload( payload ) + "\n" )
        return 1 if data.get( 'worst_severity' ) == ERROR else 0

    write_list_publishers_report( out, data )
    return 1 if data.get( 'worst_severity' ) == ERROR else 0


def _parse_names( raw ) -> list[str]:
    if not raw:
        return []
    return [ part.strip() for part in str( raw ).split( ',' ) if part.strip() ]


def remove_publishers( construct, cuppa_env, out=None ):
    """``--remove-publishers`` / ``--remove-all-publishers``."""
    del construct
    out = out or sys.stdout
    dry_run = False
    getter = getattr( cuppa_env, 'get_option', None )
    if callable( getter ):
        dry_run = bool( getter( 'no_exec' ) )
    else:
        dry_run = bool( cuppa_env.get( 'no_exec' ) )
    data = collect_publisher_rows( cuppa_env )
    root = data.get( 'publishers_root' )
    if not root or storage.is_suspicious_root( root ):
        out.write( "error: refusing to remove under publisher root [{}]\n".format(
                root or '-',
        ) )
        return 1
    by_name = { row['name']: row for row in ( data.get( 'rows' ) or [] ) }

    if cuppa_env.get( 'remove_all_publishers' ):
        targets = list( data.get( 'rows' ) or [] )
    else:
        wanted = _parse_names( cuppa_env.get( 'remove_publishers' ) )
        targets = []
        missing = []
        for name in wanted:
            row = by_name.get( name )
            if row:
                targets.append( row )
            else:
                missing.append( name )
        for name in missing:
            out.write( "error: no publisher tree named [{}] under {}\n".format(
                    name, storage.display_path( root ),
            ) )
        if missing:
            return 1

    if not targets:
        out.write( "Nothing to remove under {}\n".format(
                storage.display_path( root ),
        ) )
        return 0

    out.write( "\n" )
    if dry_run:
        out.write( "{} {}\n".format(
                as_info_label( "Dry run" ),
                "showing what --remove-publishers would delete",
        ) )

    removed = 0
    skipped = 0
    freed = 0
    for row in targets:
        path = row['path']
        name = row['name']
        try:
            storage.ensure_contained( path, root, what="publisher tree" )
        except storage.StorageError as error:
            out.write( "error: {}\n".format( error ) )
            return 1
        if row.get( 'develop_linked' ):
            out.write( "{} skipping [{}] — matches a configured develop= path\n".format(
                    as_warning( "warn:" ), name,
            ) )
            skipped += 1
            continue
        verb = "Would remove" if dry_run else "Removing"
        out.write( "{} {} ({}) at {}\n".format(
                verb,
                as_emphasised( name ),
                row.get( 'size' ) or '-',
                storage.display_path( path ),
        ) )
        storage.remove_path( path, dry_run=dry_run )
        removed += 1
        freed += int( row.get( 'size_bytes' ) or 0 )

    out.write( "\n" )
    out.write( "{}{} publisher {}, {} {}\n".format(
            INDENT,
            removed,
            "tree" if removed == 1 else "trees",
            storage.human_size( freed ),
            "would free" if dry_run else "freed",
    ) )
    if skipped:
        out.write( "{}{} skipped (develop-linked)\n".format( INDENT, skipped ) )
    out.write( "\nVerify with --list-publishers:\n\n" )
    out.write( as_emphasised( "cuppa -Q -D --list-publishers" ) + "\n" )
    return 0


def run( construct, cuppa_env, out=None ):
    """Dispatch publisher list/remove. Returns an exit status."""
    out = out or sys.stdout
    try:
        if cuppa_env.get( 'remove_all_publishers' ) or cuppa_env.get( 'remove_publishers' ):
            logger.info( as_info_label(
                    "Running in REMOVE PUBLISHERS mode, no building will be attempted"
            ) )
            return remove_publishers( construct, cuppa_env, out=out )

        if cuppa_env.get( 'list_publishers' ):
            logger.info( as_info_label(
                    "Running in LIST PUBLISHERS mode, no building will be attempted"
            ) )
            return list_publishers( construct, cuppa_env, out=out )
    except storage.StorageError as error:
        logger.error( as_error( str( error ) ) )
        out.write( "error: {}\n".format( error ) )
        return 1
    return 0
