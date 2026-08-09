#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Toolchain inventory — --list-toolchains
#-------------------------------------------------------------------------------

"""List discovered (PATH) and registered (managed) toolchains, then exit.

Text output is a ruled tree: section → family → version → driver → name(s).
A single driver may have several Cuppa names (for example ``gcc``, ``gcc15``, ``gcc153``).
"""

import os
import re
import sys
from collections import defaultdict

from cuppa.colourise import (
    as_emphasised,
    as_info,
    as_info_label,
    as_subdued,
)
from cuppa.log import logger
from cuppa.utility import storage


SECTION_DISCOVERED = 'discovered'
SECTION_REGISTERED = 'registered'

SIZE_WIDTH = 8
MIDDLE_WIDTH = 12
RULE = '-'
INDENT = '  '
HEADING_TITLE = 'TOOLCHAIN'
HEADING_HINT = 'family-version-driver-name(s)'


def add_toolchain_action_options( add_option ):
    add_option(
        '--list-toolchains', dest='list_toolchains', action='store_true',
        help="List discovered (PATH) and registered (managed) toolchains as a "
             "family → version → driver → name tree and exit",
    )


def process_toolchain_action_options( cuppa_env ):
    cuppa_env['list_toolchains'] = bool( cuppa_env.get_option( 'list_toolchains' ) )


def wants_toolchain_action( cuppa_env ):
    return bool( cuppa_env.get( 'list_toolchains' ) )


def _emphasised_info( text ):
    return as_emphasised( as_info( text ) )


def _driver_path( toolchain ):
    binary = None
    try:
        binary = toolchain.binary()
    except Exception:
        binary = None
    if not binary:
        try:
            binary = toolchain.values.get( 'CXX' )
        except Exception:
            binary = None
    if not binary:
        return None
    if os.path.isabs( binary ):
        return os.path.normpath( binary )
    cxx_path = getattr( toolchain, '_cxx_path', None )
    if cxx_path:
        candidate = os.path.join( cxx_path, os.path.basename( binary ) )
        if os.path.exists( candidate ):
            return os.path.normpath( os.path.abspath( candidate ) )
    if os.path.exists( binary ):
        found = storage.real_path( binary )
        if found and os.path.isfile( found ):
            return found
    try:
        import cuppa.build_platform as build_platform
        directory = build_platform.where_is( os.path.basename( binary ) )
        if directory:
            return os.path.normpath( os.path.join( directory, os.path.basename( binary ) ) )
    except Exception:
        pass
    return os.path.normpath( os.path.abspath( binary ) ) if binary else None


def _registration_kind( extract_root ):
    if not extract_root:
        return None
    try:
        from cuppa.toolchains import toolchain_archive
        meta = toolchain_archive.read_registration( extract_root )
        if meta:
            return meta.get( 'kind' )
    except Exception:
        return None
    return None


def _default_toolchain_name( cuppa_env ):
    try:
        platform = cuppa_env.get( 'platform' ) if hasattr( cuppa_env, 'get' ) else None
        if platform is None:
            platform = cuppa_env['platform']
        if platform is not None:
            return platform.default_toolchain()
    except Exception:
        return None
    return None


def _last_used_epoch_from_iso( iso_stamp ):
    if not iso_stamp:
        return None
    from datetime import datetime, timezone
    try:
        when = datetime.strptime(
                iso_stamp.replace( 'Z', '' ), '%Y-%m-%dT%H:%M:%S'
        ).replace( tzinfo=timezone.utc )
    except ValueError:
        return None
    return when.timestamp()


def _age_epoch_for_inventory_entry( entry, path ):
    """Match ``--list-dependencies``: prefer resolve-stamped last_used, else mtime."""
    if entry and entry.get( 'last_used_source' ) == 'resolve':
        epoch = _last_used_epoch_from_iso( entry.get( 'last_used' ) )
        if epoch is not None:
            return epoch
    try:
        return os.path.getmtime( path )
    except OSError:
        return None


def _inventory_by_path( cuppa_env ):
    """Realpath → inventory entry under dependencies_root (empty if unavailable)."""
    dependencies_root = None
    try:
        dependencies_root = cuppa_env.get( 'dependencies_root' )
    except Exception:
        dependencies_root = None
    if not dependencies_root:
        return {}
    try:
        from cuppa.core import dependency_inventory
    except Exception:
        return {}
    mapping = {}
    try:
        for entry in dependency_inventory.load_all_entries( dependencies_root ):
            path = entry.get( 'path' )
            if not path:
                continue
            try:
                real = storage.real_path( path )
            except Exception:
                real = os.path.normpath( path )
            mapping[real] = entry
    except Exception:
        return {}
    return mapping


def _stats_for_storage_path( storage_path, inventory_by_path ):
    """Return ``(size_bytes, last_used_epoch)`` for a registered extract.

    Prefer the dependency inventory (same source as ``--list-dependencies``), then
    fall back to measuring the directory.
    """
    if not storage_path:
        return None, None
    try:
        real = storage.real_path( storage_path )
    except Exception:
        real = os.path.normpath( storage_path )

    entry = ( inventory_by_path or {} ).get( real )
    size_bytes = None
    last_used_epoch = None
    if entry:
        size_info = entry.get( 'size' ) or {}
        if size_info.get( 'bytes' ) is not None:
            size_bytes = int( size_info['bytes'] )
        last_used_epoch = _age_epoch_for_inventory_entry( entry, real )

    if size_bytes is None and os.path.isdir( storage_path ):
        try:
            from cuppa.core import dependency_inventory
            measured = dependency_inventory.measure_size( storage_path, exact=False )
            if measured and measured.get( 'bytes' ) is not None:
                size_bytes = int( measured['bytes'] )
        except Exception:
            try:
                size_bytes = storage.directory_stats( storage_path ).bytes
            except Exception:
                size_bytes = None

    if last_used_epoch is None and os.path.exists( storage_path ):
        try:
            last_used_epoch = os.path.getmtime( storage_path )
        except OSError:
            last_used_epoch = None

    return size_bytes, last_used_epoch


def _version_sort_key( version ):
    text = str( version or '' )
    parts = []
    for piece in text.replace( '_', '.' ).split( '.' ):
        if piece.isdigit():
            parts.append( int( piece ) )
        else:
            match = re.match( r'(\d+)', piece )
            parts.append( int( match.group( 1 ) ) if match else 0 )
    return tuple( parts )


def row_from_toolchain( name, toolchain, default_name=None, inventory_by_path=None ):
    """Build one flat inventory row from a toolchain object."""
    storage_path = getattr( toolchain, '_toolchain_dep_root', None ) or None
    section = SECTION_REGISTERED if storage_path else SECTION_DISCOVERED
    family = None
    version = None
    try:
        family = toolchain.family()
    except Exception:
        family = None
    try:
        version = toolchain.version()
    except Exception:
        version = None
    kind = _registration_kind( storage_path ) if storage_path else None
    family = family or 'unknown'
    # Per-family default name is the bare family token (``gcc``, ``clang``, …).
    is_default = ( name == family )
    size_bytes = None
    last_used_epoch = None
    if storage_path:
        size_bytes, last_used_epoch = _stats_for_storage_path(
                storage_path, inventory_by_path or {}
        )
    return {
        'section': section,
        'name': name,
        'family': family,
        'version': str( version ) if version is not None else 'unknown',
        'driver_path': _driver_path( toolchain ),
        'storage_path': storage_path,
        'kind': kind,
        'is_default': is_default,
        'size_bytes': size_bytes,
        'last_used_epoch': last_used_epoch,
    }


def collect_toolchain_rows( cuppa_env ):
    """Return flat rows grouped by section, sorted by name within each section."""
    toolchains = cuppa_env.get( 'toolchains' ) or {}
    default_name = _default_toolchain_name( cuppa_env )
    inventory_by_path = _inventory_by_path( cuppa_env )
    discovered = []
    registered = []
    for name, toolchain in toolchains.items():
        row = row_from_toolchain(
                name, toolchain,
                default_name=default_name,
                inventory_by_path=inventory_by_path,
        )
        if row['section'] == SECTION_REGISTERED:
            registered.append( row )
        else:
            discovered.append( row )
    discovered.sort( key=lambda row: row['name'] )
    registered.sort( key=lambda row: row['name'] )
    return {
        SECTION_DISCOVERED: discovered,
        SECTION_REGISTERED: registered,
        '_platform_default_name': default_name,
    }

def session_name_by_extract_path( cuppa_env ):
    """Map real extract path → Cuppa ``--toolchains=`` session name."""
    mapping = {}
    for name, toolchain in ( cuppa_env.get( 'toolchains' ) or {} ).items():
        dep_root = getattr( toolchain, '_toolchain_dep_root', None )
        if not dep_root:
            continue
        try:
            mapping[storage.real_path( dep_root )] = name
        except Exception:
            mapping[os.path.normpath( dep_root )] = name
    return mapping


def attach_toolchain_session_names( rows, cuppa_env ):
    """Set ``toolchain_session_name`` on toolchain list-deps rows when known."""
    by_path = session_name_by_extract_path( cuppa_env )
    if not by_path:
        return rows
    for row in rows:
        if row.get( 'type' ) != 'toolchain':
            continue
        path = row.get( 'path' )
        if not path:
            continue
        try:
            real = storage.real_path( path )
        except Exception:
            real = os.path.normpath( path )
        session = by_path.get( real )
        if session:
            row['toolchain_session_name'] = session
    return rows


def build_toolchain_tree( rows, platform_default_name=None ):
    """Nest flat rows into family → version → driver → names."""
    by_family = defaultdict( list )
    for row in rows:
        by_family[row['family']].append( row )

    families = []
    for family in sorted( by_family.keys() ):
        family_rows = by_family[family]
        by_version = defaultdict( list )
        for row in family_rows:
            by_version[row['version']].append( row )

        versions = []
        for version in sorted( by_version.keys(), key=_version_sort_key, reverse=True ):
            version_rows = by_version[version]
            by_driver = defaultdict( list )
            for row in version_rows:
                driver = row.get( 'driver_path' ) or '(unknown driver)'
                by_driver[driver].append( row )

            drivers = []
            owns_default = False
            for driver in sorted( by_driver.keys() ):
                name_rows = by_driver[driver]
                names = []
                default_names = []
                other_names = []
                for row in sorted( name_rows, key=lambda item: item['name'] ):
                    entry = {
                        'name': row['name'],
                        'is_default': bool( row.get( 'is_default' ) ),
                        'size_bytes': row.get( 'size_bytes' ),
                        'last_used_epoch': row.get( 'last_used_epoch' ),
                        'storage_path': row.get( 'storage_path' ),
                        'kind': row.get( 'kind' ),
                    }
                    if entry['is_default']:
                        default_names.append( entry )
                        owns_default = True
                    else:
                        other_names.append( entry )
                names.extend( other_names )
                names.extend( default_names )
                drivers.append( {
                    'driver_path': driver,
                    'names': names,
                    'size_bytes': _rollup_size( names ),
                    'last_used_epoch': _rollup_epoch( names ),
                } )

            versions.append( {
                'version': version,
                'owns_default': owns_default,
                'drivers': drivers,
                'size_bytes': _rollup_size( drivers ),
                'last_used_epoch': _rollup_epoch( drivers ),
            } )

        # Platform-default family label only when this section actually contains the
        # platform default *name* (e.g. bare ``gcc``), not merely the same family.
        has_platform_default_name = bool(
                platform_default_name
                and any( row['name'] == platform_default_name for row in family_rows )
        )

        families.append( {
            'family': family,
            'is_platform_default': has_platform_default_name,
            'versions': versions,
            'size_bytes': _rollup_size( versions ),
            'last_used_epoch': _rollup_epoch( versions ),
        } )

    return {
        'families': families,
        'size_bytes': _rollup_size( families ),
        'last_used_epoch': _rollup_epoch( families ),
    }


def build_toolchain_sections( cuppa_env ):
    """Return ordered section dicts ready for text or JSON rendering."""
    flat = collect_toolchain_rows( cuppa_env )
    platform_default_name = flat.pop( '_platform_default_name', None )
    sections = []
    for name in ( SECTION_DISCOVERED, SECTION_REGISTERED ):
        tree = build_toolchain_tree(
                flat.get( name ) or [],
                platform_default_name=platform_default_name,
        )
        sections.append( {
            'name': name,
            'families': tree['families'],
            'size_bytes': tree['size_bytes'],
            'last_used_epoch': tree['last_used_epoch'],
        } )
    return sections


def _rollup_size( items ):
    total = 0
    saw = False
    for item in items:
        value = item.get( 'size_bytes' )
        if value is None:
            continue
        saw = True
        total += int( value )
    return total if saw else None


def _rollup_epoch( items ):
    newest = None
    for item in items:
        epoch = item.get( 'last_used_epoch' )
        if epoch is None:
            continue
        newest = epoch if newest is None else max( newest, epoch )
    return newest


def _size_cell( size_bytes, muted=False ):
    if size_bytes is None:
        text = '--'
    else:
        text = storage.human_size( size_bytes ) or '--'
    text = text.rjust( SIZE_WIDTH )
    return as_subdued( text ) if muted else text


def _age_cell( epoch, muted=False ):
    if epoch is None:
        text = '--'
    else:
        text = storage.relative_age( epoch ) or '--'
    text = storage.pad_visible( text, MIDDLE_WIDTH )
    return as_subdued( text ) if muted else text


def _ruled_line( width ):
    return as_subdued( RULE * width )


def _colour_family( text, is_platform_default=False ):
    if is_platform_default:
        return _emphasised_info( text )
    return as_emphasised( text )


def _colour_version( text, owns_default ):
    if owns_default:
        return _emphasised_info( text )
    return as_emphasised( text )


def _colour_name( text, is_default ):
    if is_default:
        return _emphasised_info( text )
    return as_info( text )


def _colour_driver( path ):
    return storage.display_path( path ) if path else path


def _render_section_tree( section, out, tee, elbow, pipe, gap ):
    families = section.get( 'families' ) or []
    out.write( "{size}  {age}{indent}{label}\n".format(
            size=_size_cell( section.get( 'size_bytes' ), muted=False ),
            age=_age_cell( section.get( 'last_used_epoch' ), muted=False ),
            indent=INDENT,
            label=section['name'],
    ) )
    if not families:
        out.write( "{size}  {age}{indent}(none)\n".format(
                size=' ' * SIZE_WIDTH,
                age=' ' * MIDDLE_WIDTH,
                indent=INDENT,
        ) )
        return

    out.write( "{size}  {age}{indent}{connector}\n".format(
            size=' ' * SIZE_WIDTH,
            age=' ' * MIDDLE_WIDTH,
            indent=INDENT,
            connector=as_subdued( pipe.rstrip() ),
    ) )

    for family_index, family in enumerate( families ):
        family_last = family_index == len( families ) - 1
        family_branch = elbow if family_last else tee
        family_prefix = gap if family_last else pipe
        family_label = family['family']
        if family.get( 'is_platform_default' ):
            family_label = '{} (default)'.format( family_label )
        out.write( "{size}  {age}{indent}{branch} {label}\n".format(
                size=_size_cell( family.get( 'size_bytes' ), muted=False ),
                age=_age_cell( family.get( 'last_used_epoch' ), muted=False ),
                indent=INDENT,
                branch=as_subdued( family_branch ),
                label=_colour_family(
                        family_label, family.get( 'is_platform_default' )
                ),
        ) )
        versions = family.get( 'versions' ) or []
        if versions:
            out.write( "{size}  {age}{indent}{prefix}{pipe_char}\n".format(
                    size=' ' * SIZE_WIDTH,
                    age=' ' * MIDDLE_WIDTH,
                    indent=INDENT,
                    prefix=as_subdued( family_prefix ),
                    pipe_char=as_subdued( pipe.rstrip() ),
            ) )

        for version_index, version in enumerate( versions ):
            version_last = version_index == len( versions ) - 1
            version_branch = elbow if version_last else tee
            version_prefix = gap if version_last else pipe
            out.write( "{size}  {age}{indent}{prefix}{branch} {label}\n".format(
                    size=_size_cell( version.get( 'size_bytes' ), muted=True ),
                    age=_age_cell( version.get( 'last_used_epoch' ), muted=True ),
                    indent=INDENT,
                    prefix=as_subdued( family_prefix ),
                    branch=as_subdued( version_branch ),
                    label=_colour_version( version['version'], version.get( 'owns_default' ) ),
            ) )

            drivers = version.get( 'drivers' ) or []
            for driver_index, driver in enumerate( drivers ):
                driver_last = driver_index == len( drivers ) - 1
                driver_branch = elbow if driver_last else tee
                driver_prefix = gap if driver_last else pipe
                out.write( "{size}  {age}{indent}{prefix}{vprefix}{branch} {label}\n".format(
                        size=_size_cell( driver.get( 'size_bytes' ), muted=False ),
                        age=_age_cell( driver.get( 'last_used_epoch' ), muted=False ),
                        indent=INDENT,
                        prefix=as_subdued( family_prefix ),
                        vprefix=as_subdued( version_prefix ),
                        branch=as_subdued( driver_branch ),
                        label=_colour_driver( driver['driver_path'] ),
                ) )

                names = driver.get( 'names' ) or []
                for name_index, name in enumerate( names ):
                    name_last = name_index == len( names ) - 1
                    name_branch = elbow if name_last else tee
                    label = name['name']
                    if name.get( 'is_default' ):
                        label = '{} (default)'.format( label )
                    out.write( "{size}  {age}{indent}{prefix}{vprefix}{dprefix}{branch} {label}\n".format(
                            size=_size_cell( name.get( 'size_bytes' ), muted=True ),
                            age=_age_cell( name.get( 'last_used_epoch' ), muted=True ),
                            indent=INDENT,
                            prefix=as_subdued( family_prefix ),
                            vprefix=as_subdued( version_prefix ),
                            dprefix=as_subdued( driver_prefix ),
                            branch=as_subdued( name_branch ),
                            label=_colour_name( label, name.get( 'is_default' ) ),
                    ) )


def _count_names( sections ):
    count = 0
    for section in sections:
        for family in section.get( 'families' ) or []:
            for version in family.get( 'versions' ) or []:
                for driver in version.get( 'drivers' ) or []:
                    count += len( driver.get( 'names' ) or [] )
    return count


def _section_size_bytes( section ):
    return section.get( 'size_bytes' )


def _render_text( sections, out ):
    tee, elbow, pipe, gap = storage.glyphs()
    heading = "{size}  {age}{indent}{title} {hint}".format(
            size='SIZE'.rjust( SIZE_WIDTH ),
            age=storage.pad_visible( 'LAST USED', MIDDLE_WIDTH ),
            indent=INDENT,
            title=HEADING_TITLE,
            hint=as_subdued( HEADING_HINT ),
    )
    width = max( storage.visible_len( heading ), 80 )

    out.write( INDENT + _ruled_line( width ) + "\n" )
    out.write( INDENT + heading + "\n" )
    out.write( INDENT + _ruled_line( width ) + "\n" )

    for index, section in enumerate( sections ):
        if index > 0:
            out.write( INDENT + _ruled_line( width ) + "\n" )
        buffer = []

        class _Capture( object ):
            def write( self, text ):
                buffer.append( text )

        _render_section_tree( section, _Capture(), tee, elbow, pipe, gap )
        for chunk in buffer:
            for line in chunk.splitlines( True ):
                out.write( INDENT + line )

    out.write( INDENT + _ruled_line( width ) + "\n" )

    by_name = { section['name']: section for section in sections }
    discovered = by_name.get( SECTION_DISCOVERED ) or {}
    registered = by_name.get( SECTION_REGISTERED ) or {}
    name_count = _count_names( sections )
    discovered_bytes = _section_size_bytes( discovered )
    registered_bytes = _section_size_bytes( registered )
    total_bytes = None
    for value in ( discovered_bytes, registered_bytes ):
        if value is None:
            continue
        total_bytes = value if total_bytes is None else total_bytes + value

    def _size_or_none( value ):
        if value is None:
            return 'none'
        return storage.human_size( value ) or 'none'

    out.write( "{}{} toolchains, {} total ({} discovered, {} registered)\n".format(
            INDENT,
            name_count,
            _size_or_none( total_bytes ),
            _size_or_none( discovered_bytes ),
            _size_or_none( registered_bytes ),
    ) )

    out.write( "\n" )
    out.write( "To remove registered toolchains review with:\n\n" )
    out.write( as_emphasised(
            "cuppa -Q -D -n --force-wipe-dependencies=[toolchain]*"
    ) + "\n\n" )
    out.write( "Drop -n and re-run after confirming.\n\n" )
    out.write(
            "Force-wipe removal of toolchains applies only to registered toolchains. "
            "Discovered toolchains are not Cuppa-owned.\n"
    )


def _section_to_json( section ):
    families = []
    for family in section.get( 'families' ) or []:
        versions = []
        for version in family.get( 'versions' ) or []:
            drivers = []
            for driver in version.get( 'drivers' ) or []:
                drivers.append( {
                    'driver_path': driver['driver_path'],
                    'display_path': storage.display_path( driver['driver_path'] ),
                    'size_bytes': driver.get( 'size_bytes' ),
                    'last_used_epoch': driver.get( 'last_used_epoch' ),
                    'names': [
                        {
                            'name': name['name'],
                            'is_default': bool( name.get( 'is_default' ) ),
                            'size_bytes': name.get( 'size_bytes' ),
                            'last_used_epoch': name.get( 'last_used_epoch' ),
                            'storage_path': name.get( 'storage_path' ),
                            'kind': name.get( 'kind' ),
                        }
                        for name in driver.get( 'names' ) or []
                    ],
                } )
            versions.append( {
                'version': version['version'],
                'owns_default': bool( version.get( 'owns_default' ) ),
                'size_bytes': version.get( 'size_bytes' ),
                'last_used_epoch': version.get( 'last_used_epoch' ),
                'drivers': drivers,
            } )
        families.append( {
            'family': family['family'],
            'is_platform_default': bool( family.get( 'is_platform_default' ) ),
            'size_bytes': family.get( 'size_bytes' ),
            'last_used_epoch': family.get( 'last_used_epoch' ),
            'versions': versions,
        } )
    return {
        'name': section['name'],
        'size_bytes': section.get( 'size_bytes' ),
        'last_used_epoch': section.get( 'last_used_epoch' ),
        'families': families,
    }


def list_toolchains( cuppa_env, out=None ):
    """Print discovered and registered toolchains. Returns an exit status."""
    out = out or sys.stdout
    sections = build_toolchain_sections( cuppa_env )

    if cuppa_env.get( 'list_format' ) == 'json':
        payload = {
            'sections': [ _section_to_json( section ) for section in sections ],
            'wipe_applies_to': SECTION_REGISTERED,
        }
        out.write( storage.render_json_payload( payload ) )
        out.write( "\n" )
        return 0

    _render_text( sections, out )
    return 0


def run( cuppa_env, out=None ):
    out = out or sys.stdout
    if cuppa_env.get( 'list_toolchains' ):
        logger.info( as_info_label(
                "Running in LIST TOOLCHAINS mode, no building will be attempted" ) )
        return list_toolchains( cuppa_env, out=out )
    return 0
