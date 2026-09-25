#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Publisher forest listing and removal — --list-publishers / --remove-publishers
#-------------------------------------------------------------------------------

"""Inspect and reclaim git publisher trees under the in-force publisher root.

Sibling surface to ``--list-downloads`` / ``--remove-dependencies``: same storage-action
family and report conventions, different root (``publisher_lookup_root``), so containment
never crosses into ``dependencies_root``.
"""

from __future__ import annotations

import logging
import os
import sys

from cuppa.colourise import as_emphasised, as_error, as_info, as_info_label, as_subdued, as_warning
from cuppa.utility import storage

logger = logging.getLogger( __name__ )

INDENT = "  "


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


def collect_publisher_rows( cuppa_env ):
    """Return listing data for ``--list-publishers``."""
    from cuppa.package_managers import package_cascade
    from cuppa.develop import inspect, state_summary

    root = package_cascade.publisher_lookup_root( cuppa_env )
    develop_paths = _develop_realpaths( cuppa_env )
    rows = []
    skips = []
    total_bytes = 0

    if not os.path.isdir( root ):
        return {
                'publishers_root': root,
                'rows': rows,
                'total_bytes': 0,
                'tree_count': 0,
                'skips': skips,
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
        rows.append( {
                'name': name,
                'path': path,
                'real_path': real,
                'size_bytes': size_bytes,
                'size': storage.human_size( size_bytes ),
                'branch': (
                        "(detached)" if observed.detached
                        else ( observed.branch or "-" )
                ),
                'upstream': observed.upstream or "-",
                'state': state_summary( observed ),
                'scm': observed.scm or "-",
                'exists': bool( observed.exists ),
                'modified': bool( observed.modified ),
                'develop_linked': develop_linked,
                'status': 'develop' if develop_linked else 'ok',
        } )

    return {
            'publishers_root': root,
            'rows': rows,
            'total_bytes': total_bytes,
            'tree_count': len( rows ),
            'skips': skips,
    }


def write_list_publishers_report( out, data ):
    """Human-readable ``--list-publishers`` body."""
    root = data.get( 'publishers_root' )
    rows = data.get( 'rows' ) or []
    out.write( "\n" )
    out.write( "Publishers in {}\n".format(
            as_info( storage.display_path( root ) ) if root else '-'
    ) )

    if not rows:
        out.write( "{}(empty)\n".format( INDENT ) )
        out.write( "{}0 publisher trees, {} total\n".format(
                INDENT, storage.human_size( 0 ),
        ) )
        return

    columns = (
            ( 'status', 'STATUS' ),
            ( 'size', 'SIZE' ),
            ( 'name', 'PUBLISHER' ),
            ( 'branch', 'BRANCH' ),
            ( 'state', 'STATE' ),
            ( 'path', 'PATH' ),
    )
    table_rows = []
    for row in rows:
        table_rows.append( {
                'status': row.get( 'status' ) or 'ok',
                'size': row.get( 'size' ) or '-',
                'name': row.get( 'name' ) or '-',
                'branch': row.get( 'branch' ) or '-',
                'state': row.get( 'state' ) or '-',
                'path': storage.display_path( row.get( 'path' ) ),
        } )
    for line in storage.render_table( columns, table_rows ):
        out.write( INDENT + line + "\n" )

    out.write( "{}{} publisher {}, {} total\n".format(
            INDENT,
            data.get( 'tree_count' ) or 0,
            "tree" if ( data.get( 'tree_count' ) or 0 ) == 1 else "trees",
            storage.human_size( data.get( 'total_bytes' ) or 0 ),
    ) )
    if any( row.get( 'develop_linked' ) for row in rows ):
        out.write( "\n" )
        out.write(
                "STATUS develop means this forest path matches a configured develop= "
                "working copy — use --list-develop / --update-develop; "
                "--remove-publishers will skip it.\n"
        )


def list_publishers( construct, cuppa_env, out=None ):
    """``--list-publishers``. Always exits 0 unless a storage error is raised."""
    del construct  # resolve is not required; forest is disk-only
    out = out or sys.stdout
    list_format = cuppa_env.get( 'list_format' ) or 'text'
    if list_format != 'json':
        out.write( as_subdued( "Collating publishers tree..." ) + "\n" )
    data = collect_publisher_rows( cuppa_env )

    if list_format == 'json':
        payload = {
                'publishers_root': data.get( 'publishers_root' ),
                'tree_count': data.get( 'tree_count' ) or 0,
                'total_bytes': data.get( 'total_bytes' ) or 0,
                'entries': [
                        {
                                'name': row.get( 'name' ),
                                'path': row.get( 'path' ),
                                'size': row.get( 'size' ),
                                'size_bytes': row.get( 'size_bytes' ),
                                'branch': row.get( 'branch' ),
                                'upstream': row.get( 'upstream' ),
                                'state': row.get( 'state' ),
                                'scm': row.get( 'scm' ),
                                'status': row.get( 'status' ),
                                'develop_linked': bool( row.get( 'develop_linked' ) ),
                                'modified': bool( row.get( 'modified' ) ),
                        }
                        for row in ( data.get( 'rows' ) or [] )
                ],
        }
        out.write( storage.render_json_payload( payload ) + "\n" )
        return 0

    write_list_publishers_report( out, data )
    return 0


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
