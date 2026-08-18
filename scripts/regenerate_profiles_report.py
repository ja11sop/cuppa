"""Regenerate C++ Profiles HTML from a saved capture or report JSON.

From a build capture (legacy, best-effort under parallel ``tee``)::

    python -m scripts.regenerate_profiles_report path/to/capture.txt \\
        --sconstruct-dir /path/to/project

From a saved report JSON (recommended for template iteration)::

    python -m scripts.regenerate_profiles_report \\
        --from-json _artefacts/cxx-profiles/cxx-profiles-index.json \\
        --sconstruct-dir /path/to/project

Capture replay infers scope from cuppa ``Progress( … )`` markers and parses
Clang Profiles diagnostics. Parallel or interleaved console output can mis-parse
paths; prefer ``--from-json`` when a report was produced by a live build.

``--from-json`` reads the versioned ``cxx-profiles-index.json`` written by
``--cxx-profiles-report`` and re-renders HTML deterministically. When
``--sconstruct-dir`` is omitted, session fields are taken from JSON ``metadata``.
Source files must still exist on disk for ``by-source/`` pages unless
``--skip-source-pages`` is set.
"""

from __future__ import print_function

import argparse
import os
import sys

from cuppa.cpp.cxx_profiles_report import format_capture_summary, replay_profiles_capture
from cuppa.cpp.profiles_report.report_html import write_profiles_reports, write_profiles_reports_from_json
from cuppa.cpp.profiles_report.report_json import env_from_report_metadata, load_report_model
from cuppa.reports.link_style import REPORT_LINK_STYLES


def _regenerate_from_capture( arguments ):
    capture_path = os.path.abspath( arguments.input_file )
    if not os.path.isfile( capture_path ):
        raise argparse.ArgumentTypeError(
            'capture file not found: {}'.format( capture_path ),
        )

    with open( capture_path, encoding='utf-8', errors='replace' ) as handle:
        inventory, unscoped = replay_profiles_capture( handle )

    if inventory.total_references() == 0:
        print( 'No Profiles violations found in capture.', file=sys.stderr )
        if unscoped:
            print( 'Unscoped diagnostics: {}'.format( unscoped ), file=sys.stderr )
        return 1

    if arguments.summary or unscoped:
        print( format_capture_summary( inventory, unscoped ) )
        if unscoped:
            print( 'warning: {} unscoped diagnostic(s)'.format( unscoped ), file=sys.stderr )

    env = env_from_report_metadata( {}, arguments )
    return write_profiles_reports( inventory, env )


def _regenerate_from_json( arguments ):
    json_path = os.path.abspath( arguments.input_file )
    if not os.path.isfile( json_path ):
        raise argparse.ArgumentTypeError(
            'report JSON not found: {}'.format( json_path ),
        )

    _model, metadata, _extras = load_report_model( json_path )
    env = env_from_report_metadata( metadata, arguments )
    from cuppa.cpp.profiles_report.anonymise import metadata_is_anonymised, set_env_anonymised

    anonymised = bool( getattr( arguments, 'anonymised', False ) ) or metadata_is_anonymised( metadata )
    if anonymised:
        set_env_anonymised( env )
    if anonymised and not arguments.report_dir:
        json_dir = os.path.dirname( json_path )
        env[ 'cxx_profiles_report' ] = json_dir or os.path.abspath( os.getcwd() )
    skip_source_pages = arguments.skip_source_pages or anonymised
    if getattr( arguments, 'anonymised', False ) and not metadata_is_anonymised( metadata ):
        print(
            'warning: --anonymised set but JSON metadata.anonymised is false',
            file=sys.stderr,
        )
    return write_profiles_reports_from_json(
        json_path,
        env,
        skip_source_pages=skip_source_pages,
        write_json=arguments.write_json,
    )


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument(
        'input_file',
        help='Saved build capture, or cxx-profiles-index.json with --from-json',
    )
    parser.add_argument(
        '--from-json',
        action='store_true',
        help='Re-render from a saved cxx-profiles-index.json (recommended)',
    )
    parser.add_argument(
        '--sconstruct-dir',
        default=None,
        help='Project root (directory containing sconstruct); default: cwd, or JSON metadata with --from-json',
    )
    parser.add_argument(
        '--artefacts-root',
        default='_artefacts',
        help='Project-relative artefacts root (default: _artefacts)',
    )
    parser.add_argument(
        '--artifacts-root',
        default=None,
        help='US spelling alias for --artefacts-root',
    )
    parser.add_argument(
        '--report-dir',
        default='',
        help='Optional output directory (default: <artefacts-root>/cxx-profiles/)',
    )
    parser.add_argument(
        '--reports-link-style',
        default=None,
        choices=list( REPORT_LINK_STYLES ),
        help='Source link style for this regen run (default: JSON metadata or local)',
    )
    parser.add_argument(
        '--link-style',
        default=None,
        choices=list( REPORT_LINK_STYLES ),
        help='Deprecated alias for --reports-link-style',
    )
    parser.add_argument(
        '--cxx-profiles-report-link-style',
        default=None,
        choices=list( REPORT_LINK_STYLES ),
        help='Profiles-only link style override for this regen run',
    )
    parser.add_argument(
        '--skip-source-pages',
        action='store_true',
        help='Omit by-source/ marked-up source pages (JSON regen only)',
    )
    parser.add_argument(
        '--anonymised',
        action='store_true',
        dest='anonymised',
        help='Regenerate from anonymised JSON (implies --skip-source-pages; suppresses file hrefs)',
    )
    parser.add_argument(
        '--anonymized',
        action='store_true',
        dest='anonymised',
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--write-json',
        action='store_true',
        help='Rewrite cxx-profiles-index.json with current schema (JSON regen only)',
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Print the replayed capture summary before rendering (capture only)',
    )
    arguments = parser.parse_args( argv )

    try:
        if arguments.from_json:
            result = _regenerate_from_json( arguments )
        else:
            result = _regenerate_from_capture( arguments )
    except ValueError as error:
        print( error, file=sys.stderr )
        return 1

    if result is None:
        print( 'Report generation returned no output.', file=sys.stderr )
        return 1

    report_dir = os.path.dirname( result[ 'index_path' ] )
    print( 'Wrote Profiles report under {}'.format( report_dir ) )
    print( '  index: {}'.format( result[ 'index_path' ] ) )
    print( '  scopes: {}'.format( len( result[ 'scope_paths' ] ) ) )
    print( '  source pages: {}'.format( len( result[ 'source_paths' ] ) ) )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
