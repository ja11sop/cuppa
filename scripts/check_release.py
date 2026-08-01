"""Release gate: a tag must name a released version whose notes are written and dated.

    python -m scripts.check_release --tag v1.4.0

This is the check that a release is never cut from a development version.
"""

import argparse
import sys

from scripts import changelog


def check( tag, version, text ):
    found = list( changelog.problems( version, text ) )

    if changelog.is_development( version ):
        found.append( "cuppa/VERSION [{}] is a development version. Run: python -m "
                      "scripts.finish_release".format( version ) )
    else:
        expected_tag = "v{}".format( version )
        if tag and tag != expected_tag:
            found.append( "tag [{}] does not match cuppa/VERSION [{}]; expected [{}]".format(
                tag, version, expected_tag ) )

    sections = changelog.parse_sections( text )
    if sections:
        top = sections[0]
        if not top.released:
            found.append( "CHANGELOG.md section [{}] is still marked '{}'".format(
                top.name, changelog.UNRELEASED ) )
        elif not changelog.section_has_entries( text, top ):
            found.append( "CHANGELOG.md section [{}] has no entries".format( top.name ) )

    return found


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument( '--tag', default='', help="the tag being released, for example v1.4.0" )
    arguments = parser.parse_args( argv )

    version = changelog.read_version()
    found = check( arguments.tag, version, changelog.read_changelog() )

    if found:
        print( "Release check failed for [{}]:".format( arguments.tag or version ) )
        for problem in found:
            print( "  - {}".format( problem ) )
        return 1

    print( "Release check passed for [{}]".format( arguments.tag or version ) )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
