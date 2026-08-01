"""Open a release cycle: point `cuppa/VERSION` and `CHANGELOG.md` at the version being assembled.

    python -m scripts.start_release 1.4.0

Run this in the first commit of a workstream so every changelog entry that follows lands under
the version it will ship in.
"""

import argparse
import sys

from packaging.version import InvalidVersion, Version

from scripts import changelog


SUBSECTIONS = ( 'Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security' )


def open_section( text, target, previous ):
    sections = changelog.parse_sections( text )
    in_progress = changelog.in_progress_section( sections )

    if in_progress:
        lines = text.splitlines()
        lines[ in_progress.start ] = "## [{}] - {}".format( target, changelog.UNRELEASED )
        text = "\n".join( lines ) + "\n"
        text = changelog.rename_link( text, in_progress.name, str( target ) )
    else:
        lines = text.splitlines()
        insert_at = sections[0].start if sections else len( lines )
        block = [ "## [{}] - {}".format( target, changelog.UNRELEASED ), '' ]
        for name in SUBSECTIONS:
            block.extend( [ "### {}".format( name ), '' ] )
        lines[ insert_at : insert_at ] = block
        text = "\n".join( lines ) + "\n"

    return changelog.set_link(
        text,
        str( target ),
        changelog.compare_link( target, previous, released=False )
    )


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument( 'version', help="the version being assembled, for example 1.4.0" )
    arguments = parser.parse_args( argv )

    try:
        target = Version( arguments.version )
    except InvalidVersion:
        print( "[{}] is not a valid version".format( arguments.version ) )
        return 1

    if target.is_devrelease:
        print( "Give the release version, not the development version: "
               "{}".format( target.base_version ) )
        return 1

    text = changelog.read_changelog()
    last_released = changelog.last_released_version( changelog.parse_sections( text ) )

    if last_released and target <= last_released:
        print( "[{}] is not above the last released version [{}]".format( target, last_released ) )
        return 1

    changelog.write_changelog( open_section( text, target, last_released ) )
    changelog.write_version( changelog.development_version( str( target ) ) )

    found = changelog.problems()
    if found:
        print( "Opened [{}] but the result is inconsistent:".format( target ) )
        for problem in found:
            print( "  - {}".format( problem ) )
        return 1

    print( "Opened [{}]".format( target ) )
    print( "  cuppa/VERSION  {}".format( changelog.read_version() ) )
    print( "  CHANGELOG.md   ## [{}] - {}".format( target, changelog.UNRELEASED ) )
    print( "Write entries into that section as you go; run scripts.finish_release to release." )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
