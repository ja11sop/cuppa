#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency removal — --remove-dependencies / --remove-all-dependencies
#-------------------------------------------------------------------------------

"""Remove selected dependency trees under ``dependencies_root`` (Slice D).

Does not touch downloads, develop working copies, or build artefacts. Selection follows the
same toolchain / variant / location-match options as writing the trees. See
``design/plans/removal-options.md`` §4.13.
"""

from __future__ import annotations

import os
import sys
from collections import namedtuple

from cuppa.colourise import (
    as_emphasised,
    as_error,
    as_info,
    as_subdued,
    as_warning,
)
from cuppa.core import dependency_inventory, dependency_storage
from cuppa.core.storage_actions import dry_run
from cuppa.utility import storage


INDENT = '  '
RULE = '-'
SIZE_WIDTH = 8
REMARK_WIDTH = 9

RemovalTarget = namedtuple(
    'RemovalTarget',
    [ 'dependency', 'path', 'qualifier', 'tool_variant', 'storage_type', 'size_bytes' ],
)

Leftover = namedtuple(
    'Leftover',
    [ 'dependency', 'path', 'qualifier', 'tool_variant', 'size_bytes', 'label' ],
)

DevelopSkip = namedtuple(
    'DevelopSkip',
    [ 'dependency', 'path', 'reason' ],
)


def parse_dependency_names( spec ):
    """Split a comma-separated ``--remove-dependencies`` value into names."""
    if not spec:
        return []
    if isinstance( spec, ( list, tuple ) ):
        spec = spec[0] if spec else ''
    names = []
    for part in str( spec ).split( ',' ):
        name = part.strip()
        if name:
            names.append( name )
    return names


def known_dependency_names( cuppa_env ):
    """Registry keys available for naming (and for unknown-name errors)."""
    factories = cuppa_env.get( 'dependencies' ) or {}
    return sorted( factories.keys() )


def resolve_requested_names( cuppa_env ):
    """Return ``(names, error_message)`` for the current remove flags.

    Unknown names produce an error listing known keys. ``--remove-all-dependencies`` with no
    default dependencies yields an empty list (caller prints nothing-to-remove).
    """
    if cuppa_env.get( 'remove_all_dependencies' ):
        return list( dependency_storage.default_dependency_names( cuppa_env ) ), None

    names = parse_dependency_names( cuppa_env.get( 'remove_dependencies' ) )
    if not names:
        return [], "no dependency names given (use --remove-dependencies=name or --remove-all-dependencies)"

    known = known_dependency_names( cuppa_env )
    known_set = set( known )
    unknown = [ name for name in names if name not in known_set ]
    if unknown:
        return [], (
            "unknown dependenc{}: {}; known: {}".format(
                'y' if len( unknown ) == 1 else 'ies',
                ', '.join( unknown ),
                ', '.join( known ) or 'none',
            )
        )
    # Preserve order, drop duplicates.
    seen = set()
    ordered = []
    for name in names:
        if name not in seen:
            seen.add( name )
            ordered.append( name )
    return ordered, None


def _dependencies_root( cuppa_env ):
    root = cuppa_env.get( 'dependencies_root' )
    if not root:
        raise storage.StorageError( "dependencies_root is not set" )
    return os.path.abspath( os.path.expanduser( root ) )


def _refuse_suspicious_dependencies_root( root, sconstruct_dir ):
    if storage.is_suspicious_root( root ):
        raise storage.StorageError(
            "refusing to remove under suspicious dependencies root [{}]".format( root )
        )
    if sconstruct_dir and storage.real_path( root ) == storage.real_path( sconstruct_dir ):
        raise storage.StorageError(
            "refusing to remove under the sconstruct directory [{}]".format( root )
        )


def _measure_bytes( path ):
    if not os.path.isdir( path ):
        return 0
    try:
        return int( storage.directory_stats( path ).bytes )
    except ( OSError, storage.StorageError ):
        return 0


def _path_label( dependency, qualifier, tool_variant ):
    parts = [ dependency ]
    if qualifier:
        parts.append( str( qualifier ) )
    if tool_variant:
        parts.append( str( tool_variant ) )
    return ' / '.join( parts )


def _sibling_leftovers( root, target, remove_reals ):
    """Other on-disk trees for the same identity that the current selection did not hit."""
    leftovers = []
    real = storage.real_path( target.path )
    try:
        relative = os.path.relpath( real, root )
    except ValueError:
        return leftovers
    parts = [ p for p in relative.split( os.sep ) if p and p != '.' ]
    if not parts:
        return leftovers

    if target.storage_type == 'gitlab' and len( parts ) >= 3:
        package, version = parts[1], parts[2]
        try:
            top_names = os.listdir( root )
        except OSError:
            return leftovers
        for name in sorted( top_names ):
            if not dependency_storage.looks_like_tool_variant_dir( name ):
                continue
            candidate = os.path.join( root, name, package, version )
            if not os.path.isdir( candidate ):
                continue
            cand_real = storage.real_path( candidate )
            if cand_real in remove_reals or cand_real == real:
                continue
            leftovers.append( Leftover(
                dependency=target.dependency,
                path=candidate,
                qualifier=version,
                tool_variant=name,
                size_bytes=_measure_bytes( candidate ),
                label=_path_label( target.dependency, version, name ),
            ) )
        return leftovers

    if target.storage_type == 'conan' and len( parts ) >= 3 and parts[0] == 'conan':
        # conan/<name>/<fingerprint> — leave other fingerprints for the same name.
        dep_name = parts[1]
        parent = os.path.join( root, 'conan', dep_name )
        if not os.path.isdir( parent ):
            return leftovers
        try:
            fingerprints = os.listdir( parent )
        except OSError:
            return leftovers
        for fingerprint in sorted( fingerprints ):
            candidate = os.path.join( parent, fingerprint )
            if not os.path.isdir( candidate ):
                continue
            cand_real = storage.real_path( candidate )
            if cand_real in remove_reals or cand_real == real:
                continue
            leftovers.append( Leftover(
                dependency=target.dependency,
                path=candidate,
                qualifier=fingerprint[:16],
                tool_variant=None,
                size_bytes=_measure_bytes( candidate ),
                label=_path_label( target.dependency, fingerprint[:16], None ),
            ) )
        return leftovers

    # Location / archive (and unknown top-level): siblings share the stem (name before @).
    if dependency_storage.looks_like_tool_variant_dir( parts[0] ):
        return leftovers
    top = parts[0]
    stem, _qual = dependency_storage.split_location_folder_name( top )
    try:
        top_names = os.listdir( root )
    except OSError:
        return leftovers
    for name in sorted( top_names ):
        other_stem, other_qual = dependency_storage.split_location_folder_name( name )
        if other_stem != stem:
            continue
        candidate = os.path.join( root, name )
        if not os.path.isdir( candidate ):
            continue
        cand_real = storage.real_path( candidate )
        if cand_real in remove_reals or cand_real == real:
            continue
        leftovers.append( Leftover(
            dependency=target.dependency,
            path=candidate,
            qualifier=other_qual,
            tool_variant=None,
            size_bytes=_measure_bytes( candidate ),
            label=_path_label( target.dependency, other_qual or '@', None ),
        ) )
    return leftovers


def collect_removal_plan( construct, cuppa_env, names ):
    """Build remove targets, leftovers, develop skips, and resolve skips for ``names``."""
    root = _dependencies_root( cuppa_env )
    owned, skips = dependency_storage.resolve_named_dependencies(
            construct, cuppa_env, names
    )

    develop_skips = []
    targets = []
    seen_remove = set()

    for item in owned:
        if item.category == 'develop' or item.develop:
            develop_skips.append( DevelopSkip(
                dependency=item.dependency,
                path=item.path,
                reason='develop working copy is never removed',
            ) )
            continue
        if item.category not in ( 'dependencies', 'cached' ):
            continue
        if not item.path:
            continue
        path = os.path.abspath( os.path.expanduser( item.path ) )
        if not os.path.lexists( path ):
            continue
        real = storage.real_path( path )
        if real in seen_remove:
            continue
        # Containment before we measure or delete.
        storage.ensure_contained( path, root, what="dependency path" )
        if os.path.islink( path ):
            raise storage.StorageError(
                "refusing to remove through symlink [{}]".format( path )
            )
        seen_remove.add( real )
        targets.append( RemovalTarget(
            dependency=item.dependency,
            path=path,
            qualifier=item.qualifier,
            tool_variant=item.tool_variant,
            storage_type=item.storage_type,
            size_bytes=_measure_bytes( path ),
        ) )

    leftovers = []
    leftover_seen = set()
    for target in targets:
        for leftover in _sibling_leftovers( root, target, seen_remove ):
            real = storage.real_path( leftover.path )
            if real in leftover_seen:
                continue
            leftover_seen.add( real )
            leftovers.append( leftover )

    # Deepest paths first so parents prune cleanly.
    targets.sort( key=lambda item: item.path.count( os.sep ), reverse=True )
    return {
        'root': root,
        'targets': targets,
        'leftovers': leftovers,
        'develop_skips': develop_skips,
        'skips': skips,
    }


def _rule_line( width ):
    return INDENT + ( RULE * max( width, 20 ) )


def _format_size( size_bytes ):
    return storage.human_size( size_bytes ).rjust( SIZE_WIDTH )


def _write_removed_table( out, targets, outcomes_by_path, planning ):
    """Compact table of removal candidates with REMARK removed / failed / would remove."""
    if not targets:
        return

    rows = []
    for target in sorted(
            targets,
            key=lambda item: (
                item.dependency,
                item.qualifier or '',
                item.tool_variant or '',
                item.path,
            ),
    ):
        outcome = outcomes_by_path.get( storage.real_path( target.path ), {} )
        result = outcome.get( 'result', 'removed' if planning else 'pending' )
        if planning and result == 'removed':
            remark = 'would rm'
        elif result == 'removed':
            remark = 'removed'
        elif result == 'failed':
            remark = 'failed'
        else:
            remark = result
        rows.append( ( target, remark ) )

    # Body width: size + spaces + remark + spaces + dependency label.
    labels = []
    for target, remark in rows:
        label = target.dependency
        if target.qualifier:
            label = "{}  {}".format( label, target.qualifier )
        if target.tool_variant:
            label = "{}  {}".format( label, target.tool_variant )
        labels.append( label )
    width = max(
        len( _rule_line( 0 ) ),
        SIZE_WIDTH + 2 + REMARK_WIDTH + 2 + max( ( len( x ) for x in labels ), default=10 ) + 2,
        len( INDENT + "SIZE".rjust( SIZE_WIDTH ) + "  " + "REMARK".ljust( REMARK_WIDTH ) + "  DEPENDENCY" ),
    )

    out.write( _rule_line( width - len( INDENT ) ) + "\n" )
    out.write( "{}{}  {}  {}\n".format(
            INDENT,
            "SIZE".rjust( SIZE_WIDTH ),
            "REMARK".ljust( REMARK_WIDTH ),
            "DEPENDENCY",
    ) )
    out.write( _rule_line( width - len( INDENT ) ) + "\n" )
    for ( target, remark ), label in zip( rows, labels ):
        remark_text = remark
        if remark == 'failed':
            remark_text = as_error( remark.ljust( REMARK_WIDTH ) )
        elif remark in ( 'removed', 'would rm' ):
            remark_text = as_info( remark.ljust( REMARK_WIDTH ) )
        else:
            remark_text = remark.ljust( REMARK_WIDTH )
        out.write( "{}{}  {}  {}\n".format(
                INDENT,
                as_subdued( _format_size( target.size_bytes ) ),
                remark_text,
                label,
        ) )
    out.write( _rule_line( width - len( INDENT ) ) + "\n" )


def _write_leftovers( out, leftovers ):
    if not leftovers:
        return
    total = sum( item.size_bytes for item in leftovers )
    unit = "tree" if len( leftovers ) == 1 else "trees"
    out.write( "\n" )
    out.write( "Leaving {} {} ({}) for other selections:\n".format(
            len( leftovers ),
            unit,
            storage.human_size( total ),
    ) )
    # Group by dependency for readability.
    by_dep = {}
    for item in leftovers:
        by_dep.setdefault( item.dependency, [] ).append( item )
    for dependency in sorted( by_dep ):
        items = by_dep[dependency]
        bits = []
        for item in items:
            detail = item.qualifier or '-'
            if item.tool_variant:
                detail = "{} / {}".format( detail, item.tool_variant )
            bits.append( "{} ({})".format( detail, storage.human_size( item.size_bytes ) ) )
        out.write( "  {}: {}\n".format( dependency, ', '.join( bits ) ) )


def _write_develop_skips( out, develop_skips ):
    if not develop_skips:
        return
    out.write( "\n" )
    out.write( "Skipped develop working copies (never removed):\n" )
    for item in develop_skips:
        out.write( "  {}: {}\n".format(
                item.dependency,
                storage.display_path( item.path ),
        ) )


def _write_verify( out ):
    out.write( "\n" )
    out.write( "Verify with:\n\n" )
    out.write( as_emphasised( "cuppa -Q -D --list-dependencies" ) + "\n" )


def remove_dependencies( construct, cuppa_env, out=None ):
    """Remove named (or all default) dependency trees for the current selection."""
    out = out or sys.stdout
    names, error = resolve_requested_names( cuppa_env )
    if error:
        out.write( "error: {}\n".format( error ) )
        return 1

    root = _dependencies_root( cuppa_env )
    _refuse_suspicious_dependencies_root( root, cuppa_env.get( 'sconstruct_dir' ) )

    plan = collect_removal_plan( construct, cuppa_env, names )
    targets = plan['targets']
    leftovers = plan['leftovers']
    develop_skips = plan['develop_skips']
    planning = dry_run( cuppa_env )

    if not targets:
        out.write( "nothing to remove" )
        if names:
            out.write( " for {} under the current selection".format(
                    ', '.join( names )
            ) )
        out.write( " under {}\n".format( storage.display_path( root ) ) )
        _write_leftovers( out, leftovers )
        _write_develop_skips( out, develop_skips )
        if leftovers or develop_skips:
            _write_verify( out )
        return 0

    planned_bytes = sum( item.size_bytes for item in targets )
    unit = "dependency tree" if len( targets ) == 1 else "dependency trees"
    announce = "{} {} {} ({}) under {}".format(
            "Would remove" if planning else "Removing",
            as_emphasised( str( len( targets ) ) ),
            unit,
            as_emphasised( storage.human_size( planned_bytes ) ),
            as_info( storage.display_path( root ) ),
    )
    out.write( announce + "\n" )
    if planning:
        out.write( as_subdued( "(dry run; pass without -n to remove)" ) + "\n" )
    out.write( "\n" )

    outcomes_by_path = {}
    failures = []
    removed_bytes = 0
    removed_count = 0

    for target in targets:
        real = storage.real_path( target.path )
        if planning:
            outcomes_by_path[real] = { 'result': 'removed' }
            removed_bytes += target.size_bytes
            removed_count += 1
            continue
        try:
            storage.ensure_contained( target.path, root, what="dependency path" )
            if os.path.islink( target.path ):
                raise storage.StorageError(
                    "refusing to remove through symlink [{}]".format( target.path )
                )
            if not os.path.lexists( target.path ):
                raise storage.StorageError( "not found (possibly already deleted)" )
            storage.remove_path( target.path, dry_run=False )
            storage.prune_empty_parents( os.path.dirname( target.path ), root )
            outcomes_by_path[real] = { 'result': 'removed' }
            removed_bytes += target.size_bytes
            removed_count += 1
            try:
                dependency_inventory.delete_entry_for_path( root, target.path )
            except Exception:
                pass
        except storage.StorageError as error:
            reason = str( error )
            already_gone = "already deleted" in reason.lower() or "not found" in reason.lower()
            severity = 'warning' if already_gone else 'error'
            outcomes_by_path[real] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': target.dependency,
                'path': target.path,
                'reason': reason,
                'severity': severity,
            } )
        except OSError as error:
            reason = str( error )
            outcomes_by_path[real] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': target.dependency,
                'path': target.path,
                'reason': reason,
                'severity': 'error',
            } )

    _write_removed_table( out, targets, outcomes_by_path, planning )
    _write_leftovers( out, leftovers )
    _write_develop_skips( out, develop_skips )

    if failures:
        out.write( "\n" )
        out.write( as_warning( "Not all requested dependency trees could be removed:" ) + "\n" )
        for item in failures:
            colour = as_error if item['severity'] == 'error' else as_warning
            out.write( "  {}: {}\n".format(
                    colour( item['dependency'] ),
                    item['reason'],
            ) )

    out.write( "\n" )
    if planning:
        out.write( "Would remove {} {} freeing up {} of disk space.\n".format(
                removed_count,
                "tree" if removed_count == 1 else "trees",
                storage.human_size( removed_bytes ),
        ) )
    else:
        out.write( "Removed {} {} freeing up {} of disk space.\n".format(
                removed_count,
                "tree" if removed_count == 1 else "trees",
                storage.human_size( removed_bytes ),
        ) )
    _write_verify( out )

    hard_errors = [ item for item in failures if item['severity'] == 'error' ]
    return 1 if hard_errors else 0
