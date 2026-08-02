#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency inventory — advisory per-entry JSON under dependencies_root
#-------------------------------------------------------------------------------

"""Per-entry inventory files under ``<dependencies_root>/.cuppa-inventory/``.

The inventory informs listings (size, last used, ownership). It never authorises deletion —
every path is re-checked on disk before removal.
"""

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone

from cuppa.log import logger
from cuppa.colourise import as_warning
from cuppa.utility import storage


INVENTORY_DIR_NAME = '.cuppa-inventory'

# Sampled sizing: walk at most this many files, then estimate the remainder.
SAMPLE_FILE_LIMIT = 4000
# Trees larger than this (by sampled estimate) keep method "sampled" until --exact-sizes.
SAMPLE_BYTE_THRESHOLD = 64 * 1024 * 1024


def inventory_dir( dependencies_root ):
    return os.path.join( os.path.expanduser( dependencies_root ), INVENTORY_DIR_NAME )


def entry_key_for_path( path ):
    """Stable filename for an inventory entry (not the dependency name — paths can collide)."""
    digest = hashlib.sha256( storage.real_path( path ).encode( 'utf-8' ) ).hexdigest()[:16]
    base = os.path.basename( path.rstrip( os.sep ) ) or 'entry'
    safe = ''.join( c if c.isalnum() or c in '-_@.' else '_' for c in base )[:48]
    return '{}_{}'.format( safe, digest )


def _utc_now():
    return datetime.now( timezone.utc ).strftime( '%Y-%m-%dT%H:%M:%SZ' )


def _entry_path( dependencies_root, key ):
    return os.path.join( inventory_dir( dependencies_root ), key + '.json' )


def load_entry( dependencies_root, key ):
    path = _entry_path( dependencies_root, key )
    try:
        with open( path, encoding='utf-8' ) as handle:
            return json.load( handle )
    except FileNotFoundError:
        return None
    except ( OSError, ValueError, TypeError ) as error:
        logger.warn( "Ignoring corrupt inventory entry [{}]: {}".format(
                as_warning( path ), as_warning( str( error ) )
        ) )
        return None


def load_all_entries( dependencies_root ):
    """Load every readable inventory entry. Corrupt files are skipped (one row lost)."""
    root = inventory_dir( dependencies_root )
    if not os.path.isdir( root ):
        return []
    entries = []
    for name in sorted( os.listdir( root ) ):
        if not name.endswith( '.json' ):
            continue
        key = name[:-5]
        entry = load_entry( dependencies_root, key )
        if entry:
            entry['_key'] = key
            entries.append( entry )
    return entries


def write_entry( dependencies_root, entry, key=None ):
    """Atomically write one inventory entry. Returns the key used."""
    path = entry.get( 'path' )
    if not path:
        raise storage.StorageError( "inventory entry has no path" )
    # Inventory tracks dependency trees; paths must sit under dependencies_root.
    # (Develop copies are never inventoried here.)
    if not storage.is_contained( path, dependencies_root ):
        raise storage.StorageError(
            "inventory path [{}] is outside dependencies_root [{}]".format(
                    path, dependencies_root
            )
        )

    key = key or entry_key_for_path( path )
    directory = inventory_dir( dependencies_root )
    os.makedirs( directory, exist_ok=True )
    target = _entry_path( dependencies_root, key )
    payload = dict( entry )
    payload.pop( '_key', None )

    fd, temporary = tempfile.mkstemp( prefix='.inv-', suffix='.tmp', dir=directory )
    try:
        with os.fdopen( fd, 'w', encoding='utf-8' ) as handle:
            json.dump( payload, handle, indent=2, sort_keys=True )
            handle.write( '\n' )
        os.replace( temporary, target )
    except Exception:
        try:
            os.unlink( temporary )
        except OSError:
            pass
        raise
    return key


def delete_entry_for_path( dependencies_root, path ):
    key = entry_key_for_path( path )
    target = _entry_path( dependencies_root, key )
    try:
        os.unlink( target )
    except FileNotFoundError:
        pass


def _tree_mtime( path ):
    try:
        return os.path.getmtime( path )
    except OSError:
        return 0


def measure_size( path, exact=False ):
    """Return ``{bytes, measured, method}`` for a dependency tree."""
    if not os.path.exists( path ):
        return { 'bytes': 0, 'measured': _utc_now(), 'method': 'exact' }

    if exact:
        stats = storage.directory_stats( path )
        return {
            'bytes': stats.bytes,
            'measured': _utc_now(),
            'method': 'exact',
        }

    total = 0
    files = 0
    truncated = False
    for root, _dirs, names in os.walk( path, followlinks=False ):
        for name in names:
            files += 1
            if files > SAMPLE_FILE_LIMIT:
                truncated = True
                break
            file_path = os.path.join( root, name )
            try:
                total += os.lstat( file_path ).st_size
            except OSError:
                pass
        if truncated:
            break

    method = 'exact'
    if truncated and files > 1:
        # Estimate remaining from mean size of the sample.
        mean = total / float( files - 1 )
        # Rough multiplier: assume similar density for the rest of the tree depth.
        # Prefer over-estimate slightly by scaling with a walk of directories.
        dir_count = 0
        for _root, dirs, _names in os.walk( path, followlinks=False ):
            dir_count += 1
            if dir_count > SAMPLE_FILE_LIMIT:
                break
        scale = max( 1.0, dir_count / max( 1.0, ( files / 20.0 ) ) )
        total = int( total * max( 1.15, min( scale, 8.0 ) ) )
        method = 'sampled'
    elif total >= SAMPLE_BYTE_THRESHOLD and files >= SAMPLE_FILE_LIMIT // 2:
        method = 'sampled'

    return {
        'bytes': int( total ),
        'measured': _utc_now(),
        'method': method,
    }


def size_needs_refresh( entry, path ):
    size = entry.get( 'size' ) or {}
    measured = size.get( 'measured' )
    if not measured:
        return True
    try:
        # Compare tree mtime to measured stamp.
        measured_epoch = datetime.strptime(
                measured.replace( 'Z', '' ), '%Y-%m-%dT%H:%M:%S'
        ).replace( tzinfo=timezone.utc ).timestamp()
    except ValueError:
        return True
    return _tree_mtime( path ) > measured_epoch + 1.0


def touch_entry(
        dependencies_root,
        path,
        *,
        kind,
        dependency,
        qualifier=None,
        tool_variant=None,
        downloads=None,
        sconstruct_dir=None,
        exact_sizes=False,
        refresh_size=True,
):
    """Create or update an inventory entry for ``path`` and return it."""
    key = entry_key_for_path( path )
    entry = load_entry( dependencies_root, key ) or {}
    now = _utc_now()
    if 'first_seen' not in entry:
        entry['first_seen'] = now
    entry['path'] = storage.real_path( path ) if os.path.exists( path ) else path
    entry['kind'] = kind
    entry['dependency'] = dependency
    entry['qualifier'] = qualifier
    entry['tool_variant'] = tool_variant
    entry['downloads'] = list( downloads or entry.get( 'downloads' ) or [] )
    entry['last_used'] = now
    used_by = dict( entry.get( 'used_by' ) or {} )
    if sconstruct_dir:
        used_by[ storage.real_path( sconstruct_dir ) ] = now
    entry['used_by'] = used_by

    if refresh_size and (
            exact_sizes
            or 'size' not in entry
            or size_needs_refresh( entry, path )
    ):
        entry['size'] = measure_size( path, exact=exact_sizes )
    elif 'size' not in entry:
        entry['size'] = measure_size( path, exact=exact_sizes )

    write_entry( dependencies_root, entry, key=key )
    entry['_key'] = key
    return entry


def format_age( iso_stamp ):
    """Human age for LAST USED, or ``-`` when missing."""
    if not iso_stamp:
        return '-'
    try:
        when = datetime.strptime(
                iso_stamp.replace( 'Z', '' ), '%Y-%m-%dT%H:%M:%S'
        ).replace( tzinfo=timezone.utc )
    except ValueError:
        return '-'
    # relative_age expects a filesystem mtime epoch.
    return storage.relative_age( when.timestamp() )


def format_size_cell( size_info ):
    """Human size with a leading ``~`` when sampled."""
    if not size_info:
        return '-'
    text = storage.human_size( int( size_info.get( 'bytes' ) or 0 ) )
    if size_info.get( 'method' ) == 'sampled':
        return '~' + text
    return text
