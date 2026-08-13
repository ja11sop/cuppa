"""Regenerate C++ Profiles HTML and JSON from a saved build capture.

    python -m scripts.regenerate_profiles_report path/to/capture.txt \\
        --sconstruct-dir /path/to/project

The capture file should contain cuppa ``Progress( … )`` scope markers and Clang
Profiles diagnostics (``under profile '…'`` suffix), as written during a normal
``--cxx-profiles-report`` build. Scope is inferred from the Progress lines.
ANSI colour sequences (from ``tee`` on a colour terminal) are stripped automatically.

Use this to iterate on report templates without re-running a full compile.
Source files must still exist at the paths recorded in the capture so
``by-source/`` pages can be rendered.
"""

from __future__ import print_function

import argparse
import os
import sys

from cuppa.cpp.cxx_profiles_report import format_capture_summary, replay_profiles_capture
from cuppa.cpp.profiles_report.report_html import write_profiles_reports


def _build_env( arguments ):
    sconstruct_dir = os.path.abspath( arguments.sconstruct_dir )
    artifacts_root = arguments.artifacts_root
    if os.path.isabs( artifacts_root ):
        abs_artifacts_root = os.path.abspath( artifacts_root )
    else:
        abs_artifacts_root = os.path.join( sconstruct_dir, artifacts_root )

    env = {
        'sconstruct_dir': sconstruct_dir,
        'artifacts_root': artifacts_root,
        'abs_artifacts_root': abs_artifacts_root,
        'cxx_profiles_report': True,
        'cxx_profiles_report_link_style': arguments.link_style,
        'cxx_profiles_report_root': sconstruct_dir,
    }
    if arguments.report_dir:
        env[ 'cxx_profiles_report' ] = os.path.abspath( arguments.report_dir )
    return env


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument(
        'capture_file',
        help='Saved build output with Progress() markers and Profiles diagnostics',
    )
    parser.add_argument(
        '--sconstruct-dir',
        default=os.getcwd(),
        help='Project root (directory containing sconstruct); default: cwd',
    )
    parser.add_argument(
        '--artifacts-root',
        default='_artifacts',
        help='Project-relative artefacts root (default: _artifacts)',
    )
    parser.add_argument(
        '--report-dir',
        default='',
        help='Optional output directory (default: <artifacts-root>/cxx-profiles/)',
    )
    parser.add_argument(
        '--link-style',
        default='local',
        choices=( 'local', 'gitlab', 'github' ),
        help='Source link style (default: local)',
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Print the replayed capture summary before rendering',
    )
    arguments = parser.parse_args( argv )

    capture_path = os.path.abspath( arguments.capture_file )
    if not os.path.isfile( capture_path ):
        parser.error( 'capture file not found: {}'.format( capture_path ) )

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

    env = _build_env( arguments )
    result = write_profiles_reports( inventory, env )
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
