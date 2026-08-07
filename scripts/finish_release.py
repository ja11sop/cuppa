"""Close a release cycle: date the changelog section and drop the development marker.

    python -m scripts.finish_release
    python -m scripts.finish_release --date 2026-08-14

Leaves the tree ready to tag. The release gate in CI checks the same things this produces.
"""

import argparse
import re
import sys

from scripts import changelog


_SUBSECTION = re.compile( r'^### .+$' )


def prune_empty_subsections( lines, start, end ):
    """Drop `### Added` style headings that gained no entries, newest release conventions."""
    kept = []
    index = start + 1
    while index < end:
        line = lines[index]
        if _SUBSECTION.match( line ):
            following = index + 1
            has_entries = False
            while following < end and not _SUBSECTION.match( lines[following] ):
                if lines[following].strip():
                    has_entries = True
                following += 1
            if not has_entries:
                index = following
                continue
        kept.append( line )
        index += 1

    while kept and not kept[-1].strip():
        kept.pop()
    kept.append( '' )
    return lines[ : start + 1 ] + kept + lines[ end : ]


def close_section( text, target, date ):
    sections = changelog.parse_sections( text )
    in_progress = changelog.in_progress_section( sections )
    if in_progress is None:
        raise SystemExit( "CHANGELOG.md has no unreleased section to close" )

    lines = text.splitlines()
    lines = prune_empty_subsections( lines, in_progress.start, in_progress.end )
    lines[ in_progress.start ] = "## [{}] - {}".format( target, date )
    text = "\n".join( lines ) + "\n"

    previous = changelog.last_released_version( changelog.parse_sections( text ) )
    previous_released = [
        version for version in
        [ section.version for section in changelog.released_sections(
            changelog.parse_sections( text ) ) ]
        if version and version < target
    ]
    previous = max( previous_released ) if previous_released else previous

    return changelog.set_link(
        text,
        str( target ),
        changelog.compare_link( target, previous, released=True )
    )


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument( '--date', default=changelog.today(),
                         help="release date, defaults to today" )
    arguments = parser.parse_args( argv )

    version = changelog.read_version()
    if not changelog.is_development( version ):
        print( "cuppa/VERSION is [{}], which is already a release version".format( version ) )
        return 1

    target = changelog.release_version( version )
    text = changelog.read_changelog()
    sections = changelog.parse_sections( text )
    in_progress = changelog.in_progress_section( sections )

    if in_progress is None:
        print( "CHANGELOG.md has no unreleased section to close" )
        return 1
    if not changelog.section_has_entries( text, in_progress ):
        print( "CHANGELOG.md section [{}] has no entries; a release needs release "
               "notes".format( in_progress.name ) )
        return 1

    changelog.write_changelog( close_section( text, target, arguments.date ) )
    changelog.write_version( str( target ) )

    found = changelog.problems()
    if found:
        print( "Closed [{}] but the result is inconsistent:".format( target ) )
        for problem in found:
            print( "  - {}".format( problem ) )
        return 1

    print( "Closed [{}] - {}".format( target, arguments.date ) )
    print( "Next: commit and merge this PR, then Actions → release → publish" )
    print( "  (or: git tag -a v{version} -m 'cuppa {version}' && git push origin v{version})"
           .format( version=target ) )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
