"""Replay a saved Profiles build capture through the parser.

    python -m scripts.replay_profiles_capture path/to/profile_output.txt

The capture file should contain cuppa ``Progress( … )`` scope markers and Clang
Profiles diagnostics (``under profile '…'`` suffix). Scope is inferred from the
Progress lines; only the capture file path needs to be supplied.
"""

import argparse
import sys

from cuppa.cpp.cxx_profiles_report import format_capture_summary, replay_profiles_capture


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument(
        'capture_file',
        help='Saved build output with Progress() markers and Profiles diagnostics',
    )
    arguments = parser.parse_args( argv )

    with open( arguments.capture_file, encoding='utf-8', errors='replace' ) as handle:
        inventory, unscoped = replay_profiles_capture( handle )

    print( format_capture_summary( inventory, unscoped ) )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
