#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   --list-available-reports — report kinds × toolchains on this system
#-------------------------------------------------------------------------------

import json

from cuppa.reports.available_reports_display import (
    REPORT_CATALOG,
    REPORT_DISPLAY_ORDER,
    render_available_reports_text,
    serialise_toolchains_by_family,
)
from cuppa.reports.registry import (
    abs_artefacts_root_from_env,
    rel_artefacts_root_from_env,
    report_kind_by_id,
    serialise_report_kinds,
)


def list_available_reports( cuppa_env, out ):
    """Print report kinds with supporting toolchains on this system and exit."""
    list_format = cuppa_env.get( 'list_format' ) or 'text'
    if list_format == 'json':
        payload = serialise_available_reports( cuppa_env )
        out.write( json.dumps( payload, indent=2, sort_keys=True ) )
        out.write( '\n' )
        return 0

    render_available_reports_text(
        cuppa_env,
        out,
        abs_artefacts_root_from_env( cuppa_env ),
        rel_artefacts_root_from_env( cuppa_env ),
    )
    return 0


def serialise_available_reports( env ):
    """Build JSON for ``--list-available-reports --list-format=json``."""
    payload = serialise_report_kinds( env, include_toolchains=False )
    rows = []
    for kind_id in REPORT_DISPLAY_ORDER:
        catalog = REPORT_CATALOG[ kind_id ]
        kind = report_kind_by_id( kind_id )
        row = None
        for existing in payload[ 'report_kinds' ]:
            if existing[ 'kind' ] == kind_id:
                row = dict( existing )
                break
        if row is None:
            continue
        row[ 'title' ] = catalog[ 'title' ]
        row[ 'cli' ] = catalog[ 'cli' ]
        row[ 'toolchains_by_family' ] = serialise_toolchains_by_family( env, kind_id )
        row[ 'supporting_toolchains' ] = [
            name
            for group in row[ 'toolchains_by_family' ]
            for name in group[ 'toolchains' ]
        ]
        if catalog.get( 'cli', {} ).get( 'note' ):
            note = catalog[ 'cli' ][ 'note' ]
            if isinstance( note, dict ):
                row[ 'note' ] = '{} {}'.format(
                    note.get( 'text', '' ),
                    note.get( 'emphasis', '' ),
                ).strip()
            else:
                row[ 'note' ] = note
        rows.append( row )
    payload[ 'report_kinds' ] = rows
    return payload
