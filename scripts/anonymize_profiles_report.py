"""Anonymize a saved C++ Profiles report JSON for sharing.

Typical workflow::

    python -m scripts.anonymize_profiles_report \\
        --in _artifacts/cxx-profiles/cxx-profiles-index.json \\
        --out _artifacts/cxx-profiles/cxx-profiles-index.anonymized.json

Then regenerate HTML without source pages::

    python -m scripts.regenerate_profiles_report \\
        --from-json _artifacts/cxx-profiles/cxx-profiles-index.anonymized.json \\
        --anonymized
"""

from __future__ import print_function

import argparse
import json
import os
import sys

from cuppa.cpp.profiles_report.anonymize import anonymize_report_document


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument(
        '--in',
        dest='input_path',
        required=True,
        help='Input cxx-profiles-index.json from a real build',
    )
    parser.add_argument(
        '--out',
        dest='output_path',
        required=True,
        help='Output anonymized JSON path',
    )
    parser.add_argument(
        '--mapping-out',
        default=None,
        help='Optional sidecar mapping (original → anonymized paths); keep local only',
    )
    parser.add_argument(
        '--dictionary',
        default=None,
        help='Optional synonym dictionary JSON (default: built-in offline map)',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-anonymize input that already has metadata.anonymized',
    )
    arguments = parser.parse_args( argv )

    input_path = os.path.abspath( arguments.input_path )
    output_path = os.path.abspath( arguments.output_path )
    if not os.path.isfile( input_path ):
        print( 'Input report JSON not found: {}'.format( input_path ), file=sys.stderr )
        return 1

    with open( input_path, encoding='utf-8' ) as handle:
        data = json.load( handle )

    dictionary = None
    if arguments.dictionary:
        with open( arguments.dictionary, encoding='utf-8' ) as handle:
            dictionary = json.load( handle )

    mapping = {} if arguments.mapping_out else None
    try:
        payload = anonymize_report_document(
            data,
            dictionary=dictionary,
            mapping=mapping,
            force=arguments.force,
        )
    except ValueError as error:
        print( error, file=sys.stderr )
        return 1

    output_dir = os.path.dirname( output_path )
    if output_dir:
        os.makedirs( output_dir, exist_ok=True )

    with open( output_path, 'w', encoding='utf-8' ) as handle:
        json.dump( payload, handle, indent=2, sort_keys=True )
        handle.write( '\n' )

    if arguments.mapping_out:
        mapping_path = os.path.abspath( arguments.mapping_out )
        mapping_dir = os.path.dirname( mapping_path )
        if mapping_dir:
            os.makedirs( mapping_dir, exist_ok=True )
        with open( mapping_path, 'w', encoding='utf-8' ) as handle:
            json.dump( mapping, handle, indent=2, sort_keys=True )
            handle.write( '\n' )
        print( 'Wrote mapping sidecar {}'.format( mapping_path ) )

    print( 'Wrote anonymized report JSON {}'.format( output_path ) )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
