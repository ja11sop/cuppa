"""Emit the CHANGELOG body for a released version (for GitHub Releases).

    python -m scripts.release_notes --tag v1.4.0
    python -m scripts.release_notes --version 1.4.0 -o release-notes.md
"""

import argparse
import sys

from scripts import changelog


def notes_for( text, version_name ):
    """Markdown body of the ``## [version]`` section, or None if missing."""
    sections = changelog.parse_sections( text )
    for section in sections:
        if section.name == version_name:
            body = "\n".join( changelog.section_body( text, section ) ).strip()
            return body or None
    return None


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument( '--tag', default='', help="release tag, for example v1.4.0" )
    parser.add_argument( '--version', default='', help="version without the v prefix" )
    parser.add_argument( '-o', '--output', help="write to this file instead of stdout" )
    arguments = parser.parse_args( argv )

    version = arguments.version
    if arguments.tag:
        if not arguments.tag.startswith( 'v' ):
            print( "tag [{}] must start with 'v'".format( arguments.tag ), file=sys.stderr )
            return 1
        version = arguments.tag[1:]
    if not version:
        version = str( changelog.release_version( changelog.read_version() ) )

    notes = notes_for( changelog.read_changelog(), version )
    if notes is None:
        print( "CHANGELOG.md has no section for [{}]".format( version ), file=sys.stderr )
        return 1

    if arguments.output:
        with open( arguments.output, 'w', encoding='utf-8' ) as handle:
            handle.write( notes )
            handle.write( '\n' )
    else:
        print( notes )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
