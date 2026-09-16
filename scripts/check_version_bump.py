"""Pull request gate: the target version must match the declared impact of the change.

    python -m scripts.check_version_bump --base-ref origin/master --labels "impact:minor,docs"
    python -m scripts.check_version_bump --base-ref origin/master --pull-request 303

The impact label states intent; this checks the number agrees with it, so a feature cannot ship
as a patch by accident. `impact:none` is for changes with no release impact at all.

`--pull-request` reads the labels live instead of trusting a webhook payload. See
:func:`labels_from_api` for why that matters.
"""

import argparse
import os
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


def labels_from_api( number, repository=None ):
    """Labels as they are now, rather than as a webhook payload froze them.

    A pull request cannot be created with labels — neither ``POST /pulls`` nor the GraphQL
    ``createPullRequest`` mutation takes them — so ``create-pr`` labels in a second call, and
    the ``opened`` event payload is sealed without the label. That payload never catches up,
    even though the label lands seconds later and long before a runner starts. Reading live
    sees it; a pull request that genuinely carries no impact label still reads empty and is
    still refused.
    """
    from scripts.github_api import GitHub

    slug = repository or os.environ.get( 'GITHUB_REPOSITORY' )
    if not slug or '/' not in slug:
        raise ValueError(
            "could not tell which repository to read; pass --repository owner/name"
        )

    # The ephemeral Actions job token, not the sealed workstation credential. Anonymous reads
    # would do for a public repository, but shared runner addresses exhaust that rate limit.
    credential = ( os.environ.get( 'GITHUB_TOKEN' ) or '' ).strip()
    github = GitHub( credential=credential ) if credential else GitHub.public()

    status, body = github.request(
        'GET', '/repos/{}/pulls/{}'.format( slug, number )
    )
    if status != 200:
        raise ValueError( "could not read labels for pull request [{}]: HTTP {} {}".format(
            number, status, ( body or {} ).get( 'message', '' ) ) )
    return [
        label['name'] for label in ( body.get( 'labels' ) or [] ) if label.get( 'name' )
    ]


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
                         help="comma separated pull request labels (event payload fallback)" )
    parser.add_argument( '--pull-request', default=None,
                         help="pull request number; its labels are read live from the API" )
    parser.add_argument( '--repository', default=None,
                         help="owner/name for --pull-request; defaults to $GITHUB_REPOSITORY" )
    arguments = parser.parse_args( argv )

    labels = [ label for label in arguments.labels.split( ',' ) if label.strip() ]
    if arguments.pull_request:
        try:
            labels = labels_from_api( arguments.pull_request, arguments.repository )
            print( "Labels read from the API: {}".format( ", ".join( labels ) or '-' ) )
        except ( ValueError, OSError ) as error:
            print( "Could not read labels from the API, using the event payload: "
                   "{}".format( error ) )

    try:
        impact = impact_from_labels( labels )
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
