#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Toolchain inventory — --list-toolchains
#-------------------------------------------------------------------------------

"""List discovered (PATH) and registered (managed) toolchains, then exit."""

import os
import sys

from cuppa.colourise import as_info_label, as_notice, as_subdued
from cuppa.log import logger
from cuppa.utility import storage


SECTION_DISCOVERED = 'Discovered'
SECTION_REGISTERED = 'Registered'


def add_toolchain_action_options( add_option ):
    add_option(
        '--list-toolchains', dest='list_toolchains', action='store_true',
        help="List discovered (PATH) and registered (managed) toolchains with driver "
             "paths and exit",
    )


def process_toolchain_action_options( cuppa_env ):
    cuppa_env['list_toolchains'] = bool( cuppa_env.get_option( 'list_toolchains' ) )


def wants_toolchain_action( cuppa_env ):
    return bool( cuppa_env.get( 'list_toolchains' ) )


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
    # Prefer the known install bin dir when Cuppa recorded it
    cxx_path = getattr( toolchain, '_cxx_path', None )
    if cxx_path:
        candidate = os.path.join( cxx_path, os.path.basename( binary ) )
        if os.path.exists( candidate ):
            return os.path.normpath( os.path.abspath( candidate ) )
    found = storage.real_path( binary ) if os.path.exists( binary ) else None
    if found and os.path.isfile( found ):
        return found
    # Fall back to which-style absolute path when possible
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


def row_from_toolchain( name, toolchain ):
    """Build one inventory row dict from a registered toolchain object."""
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
    return {
        'section': section,
        'name': name,
        'family': family,
        'version': version,
        'driver_path': _driver_path( toolchain ),
        'storage_path': storage_path,
        'kind': kind,
    }


def collect_toolchain_rows( cuppa_env ):
    """Return ``{SECTION_DISCOVERED: [...], SECTION_REGISTERED: [...]}`` sorted by name."""
    toolchains = cuppa_env.get( 'toolchains' ) or {}
    discovered = []
    registered = []
    for name, toolchain in toolchains.items():
        row = row_from_toolchain( name, toolchain )
        if row['section'] == SECTION_REGISTERED:
            registered.append( row )
        else:
            discovered.append( row )
    discovered.sort( key=lambda row: row['name'] )
    registered.sort( key=lambda row: row['name'] )
    return {
        SECTION_DISCOVERED: discovered,
        SECTION_REGISTERED: registered,
    }


def _pad( text, width ):
    return storage.pad_visible( text if text is not None else '', width )


def _render_text( sections, out ):
    columns = ( 'NAME', 'FAMILY', 'VERSION', 'DRIVER', 'STORAGE' )
    all_rows = []
    for section_name in ( SECTION_DISCOVERED, SECTION_REGISTERED ):
        for row in sections.get( section_name, [] ):
            all_rows.append( [
                    row.get( 'name' ) or '',
                    row.get( 'family' ) or '',
                    row.get( 'version' ) or '',
                    row.get( 'driver_path' ) or '',
                    row.get( 'storage_path' ) or '',
            ] )

    widths = [ len( c ) for c in columns ]
    for cells in all_rows:
        for index, cell in enumerate( cells ):
            widths[index] = max( widths[index], storage.visible_len( cell ) )

    for section_name in ( SECTION_DISCOVERED, SECTION_REGISTERED ):
        out.write( "{}\n".format( as_notice( section_name ) ) )
        section_rows = sections.get( section_name, [] )
        if not section_rows:
            out.write( "(none)\n\n" )
            continue
        out.write( "  ".join(
                _pad( columns[i], widths[i] ) for i in range( len( columns ) )
        ) + "\n" )
        for row in section_rows:
            cells = [
                    row.get( 'name' ) or '',
                    row.get( 'family' ) or '',
                    row.get( 'version' ) or '',
                    row.get( 'driver_path' ) or '',
                    row.get( 'storage_path' ) or '',
            ]
            out.write( "  ".join(
                    _pad( cells[i], widths[i] ) for i in range( len( columns ) )
            ) + "\n" )
        out.write( "\n" )

    out.write( as_subdued(
            "Force-wipe / removal of toolchain dependencies applies only to Registered "
            "rows (managed installs under dependencies_root/toolchains/). "
            "Discovered PATH compilers are not Cuppa-owned.\n"
    ) )


def list_toolchains( cuppa_env, out=None ):
    """Print discovered and registered toolchains. Returns an exit status."""
    out = out or sys.stdout
    sections = collect_toolchain_rows( cuppa_env )

    if cuppa_env.get( 'list_format' ) == 'json':
        payload = {
            'sections': [
                {
                    'name': SECTION_DISCOVERED,
                    'toolchains': sections[SECTION_DISCOVERED],
                },
                {
                    'name': SECTION_REGISTERED,
                    'toolchains': sections[SECTION_REGISTERED],
                },
            ],
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
