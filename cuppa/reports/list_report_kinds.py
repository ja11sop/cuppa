#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   --list-report-kinds — catalogue built-in report kinds under the artefacts root
#-------------------------------------------------------------------------------

import json

from cuppa.colourise import as_emphasised, as_info, as_subdued
from cuppa.reports.registry import (
    REPORT_KINDS,
    abs_artefacts_root_from_env,
    default_report_dir_for_kind,
    rel_artefacts_root_from_env,
    serialise_report_kinds,
)


def list_report_kinds( cuppa_env, out ):
    """Print registered report kinds and exit."""
    list_format = cuppa_env.get( 'list_format' ) or 'text'
    if list_format == 'json':
        payload = serialise_report_kinds( cuppa_env )
        out.write( json.dumps( payload, indent=2, sort_keys=True ) )
        out.write( '\n' )
        return 0

    abs_root = abs_artefacts_root_from_env( cuppa_env )
    rel_root = rel_artefacts_root_from_env( cuppa_env )
    out.write(
        'Artefacts root: {} ({})\n\n'.format(
            as_info( abs_root ),
            as_subdued( rel_root ),
        ),
    )
    out.write( 'Report kinds (built-in; not a scan of files on disk):\n\n' )

    for kind in REPORT_KINDS:
        if kind.under_artefacts_root and kind.default_subdir:
            location = '{}/'.format( kind.default_subdir )
            default_dir = default_report_dir_for_kind( cuppa_env, kind )
            out.write(
                '  {}  {}\n'.format(
                    as_emphasised( location.ljust( 16 ) ),
                    kind.label,
                ),
            )
            out.write(
                '                 Default: {}\n'.format( as_subdued( default_dir ) ),
            )
        else:
            out.write(
                '  {}  {}\n'.format(
                    as_emphasised( '(varies)'.ljust( 16 ) ),
                    kind.label,
                ),
            )
        if kind.cli_flags:
            out.write(
                '                 CLI: {}\n'.format(
                    as_subdued( ', '.join( kind.cli_flags ) ),
                ),
            )
        out.write(
            '                 Method: env.{}()\n'.format( kind.env_method ),
        )
        out.write(
            '                 Clean: {}\n'.format( as_subdued( kind.clean_via ) ),
        )
        if kind.notes:
            out.write(
                '                 Note: {}\n'.format( as_subdued( kind.notes ) ),
            )
        out.write( '\n' )

    out.write(
        'Full artefact-tree removal (--remove-artefacts) is not implemented yet; '
        'see removal-options Phase 6.\n',
    )
    return 0
