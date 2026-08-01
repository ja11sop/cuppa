"""Pull request gate: the target version must match the declared impact of the change.

    python -m scripts.check_version_bump --base-ref origin/master --labels "impact:minor,docs"

The impact label states intent; this checks the number agrees with it, so a feature cannot ship
as a patch by accident. `impact:none` is for changes with no release impact at all.
"""

import argparse
import subprocess
import sys

from packaging.version import InvalidVersion, Version

from scripts import changelog


LABEL_PREFIX = 'impact:'


def impact_from_labels( labels ):
    impacts = [
        label[ len( LABEL_PREFIX ) : ].strip()
        for label in labels
        if label.strip().startswith( LABEL_PREFIX )
    ]
    if not impacts:
        raise ValueError(
            "no {}<{}> label on this pull request. Add one so the version bump can be "
            "checked".format( LABEL_PREFIX, '|'.join( changelog.IMPACTS ) )
        )
    if len( impacts ) > 1:
        raise ValueError( "several impact labels [{}]; there should be exactly "
                          "one".format( ", ".join( impacts ) ) )
    if impacts[0] not in changelog.IMPACTS:
        raise ValueError( "unknown impact [{}]; expected one of {}".format(
            impacts[0], ", ".join( changelog.IMPACTS ) ) )
    return impacts[0]


def version_at( ref ):
    try:
        output = subprocess.check_output(
            [ 'git', 'show', "{}:cuppa/VERSION".format( ref ) ],
            stderr = subprocess.STDOUT
        )
    except ( subprocess.CalledProcessError, OSError ) as error:
        raise ValueError( "could not read cuppa/VERSION at [{}]: {}".format( ref, error ) )
    return output.decode( 'utf-8' ).strip()


def check( version, text, base_version, impact ):
    found = list( changelog.problems( version, text ) )
    if found:
        return found

    target = changelog.release_version( version )
    sections = changelog.parse_sections( text )
    last_released = changelog.last_released_version( sections )

    try:
        base_target = changelog.release_version( base_version )
    except InvalidVersion:
        return [ "the base version [{}] is not valid".format( base_version ) ]

    if target < base_target:
        found.append( "cuppa/VERSION [{}] is below the base branch version [{}]".format(
            version, base_version ) )

    if impact == 'none':
        if last_released and target < last_released:
            found.append( "cuppa/VERSION [{}] is below the last released version [{}]".format(
                version, last_released ) )
        return found

    if last_released is None:
        return found

    required = changelog.expected_version( last_released, impact )
    if target < required:
        found.append(
            "a {} change on top of [{}] needs at least [{}], but cuppa/VERSION is [{}]. "
            "Run: python -m scripts.start_release {}".format(
                impact, last_released, required, version, required )
        )

    if not Version( version ).is_devrelease:
        found.append( "cuppa/VERSION [{}] is not a development version. A branch assembling a "
                      "release should carry [{}]".format(
                          version, changelog.development_version( version ) ) )

    in_progress = changelog.in_progress_section( sections )
    if in_progress is None:
        found.append( "CHANGELOG.md has no '## [{}] - {}' section to write entries "
                      "into".format( target, changelog.UNRELEASED ) )
    elif not changelog.section_has_entries( text, in_progress ):
        found.append( "CHANGELOG.md section [{}] has no entries. A {} change should describe "
                      "itself".format( in_progress.name, impact ) )

    return found


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument( '--base-ref', default='origin/master',
                         help="the branch being merged into" )
    parser.add_argument( '--labels', default='',
                         help="comma separated pull request labels" )
    arguments = parser.parse_args( argv )

    try:
        impact = impact_from_labels( arguments.labels.split( ',' ) )
        base_version = version_at( arguments.base_ref )
    except ValueError as error:
        print( "Version check failed: {}".format( error ) )
        return 1

    version = changelog.read_version()
    found = check( version, changelog.read_changelog(), base_version, impact )

    if found:
        print( "Version check failed for an [{}] change "
               "(base [{}], branch [{}]):".format( impact, base_version, version ) )
        for problem in found:
            print( "  - {}".format( problem ) )
        return 1

    print( "Version check passed: [{}] change, base [{}], branch [{}]".format(
        impact, base_version, version ) )
    return 0


if __name__ == '__main__':
    sys.exit( main() )
