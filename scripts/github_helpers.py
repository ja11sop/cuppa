"""Higher-level GitHub operations for agents and maintenance, on top of ``github_api``.

``scripts.github_api`` is the credential and transport layer. This module is the place to add
repeated write workflows — create a pull request, apply the ``impact:`` label — so an agent does
not rewrite the same ``urllib`` call every time. Grow it when the same sequence appears twice;
do not invent helpers for a one-off.

Pushing a branch is still ``git push -u origin HEAD``. These helpers only cover the GitHub API
surface that needs the sealed token.

Create a pull request from the current branch:

    python -m scripts.github_helpers create-pr \\
        --title "…" --body-file /tmp/pr.md --label impact:minor

Or from Python:

    from scripts.github_helpers import create_pull_request
    create_pull_request( title='…', body='…', labels=['impact:minor'] )
"""

import argparse
import json
import re
import subprocess
import sys

from scripts.github_api import CredentialError, GitHub


DEFAULT_OWNER = 'ja11sop'
DEFAULT_REPO = 'cuppa'
DEFAULT_BASE = 'master'


class GitHubHelperError( Exception ):
    pass


def _run_git( *arguments ):
    try:
        return subprocess.run(
            [ 'git', *arguments ],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            check = True,
            text = True,
        ).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise GitHubHelperError( error.stderr.strip() or str( error ) )


def current_branch():
    return _run_git( 'rev-parse', '--abbrev-ref', 'HEAD' )


def repository( owner=None, repo=None ):
    """``owner/repo`` for API paths.

    Explicit arguments win. Otherwise the ``origin`` remote is parsed when it looks like this
    repository; falling back to the defaults keeps the helpers usable outside a checkout.
    """
    if owner and repo:
        return owner, repo

    try:
        url = _run_git( 'config', '--get', 'remote.origin.url' )
    except GitHubHelperError:
        return owner or DEFAULT_OWNER, repo or DEFAULT_REPO

    match = re.search( r'[:/]([^/]+)/([^/]+?)(?:\.git)?$', url )
    if match:
        return match.group( 1 ), match.group( 2 )
    return owner or DEFAULT_OWNER, repo or DEFAULT_REPO


def create_pull_request(
        title,
        body,
        head=None,
        base=DEFAULT_BASE,
        labels=None,
        owner=None,
        repo=None,
        github=None,
):
    """Open a pull request and optionally label it. Returns the pull request dict from GitHub."""
    owner, repo = repository( owner, repo )
    head = head or current_branch()
    client = github or GitHub()

    status, pull = client.request(
        'POST',
        '/repos/{}/{}/pulls'.format( owner, repo ),
        {
            'title': title,
            'body': body,
            'head': head,
            'base': base,
        },
    )
    if status >= 400:
        raise GitHubHelperError( "creating the pull request failed ({}): {}".format(
            status, json.dumps( pull ) ) )

    if labels:
        number = pull['number']
        label_status, labelled = client.request(
            'POST',
            '/repos/{}/{}/issues/{}/labels'.format( owner, repo, number ),
            { 'labels': list( labels ) },
        )
        if label_status >= 400:
            raise GitHubHelperError(
                "pull request {} was created but labelling failed ({}): {}".format(
                    pull.get( 'html_url' ), label_status, json.dumps( labelled ) )
            )

    return pull


def _read_body( arguments ):
    if arguments.body_file:
        with open( arguments.body_file, encoding='utf-8' ) as body_file:
            return body_file.read()
    if arguments.body is not None:
        return arguments.body
    raise GitHubHelperError( "give --body or --body-file" )


def create_pr_command( arguments ):
    pull = create_pull_request(
        title = arguments.title,
        body = _read_body( arguments ),
        head = arguments.head,
        base = arguments.base,
        labels = arguments.label,
        owner = arguments.owner,
        repo = arguments.repo,
    )
    print( pull['html_url'] )
    return 0


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    commands = parser.add_subparsers( dest='command' )

    create = commands.add_parser( 'create-pr', help="open a pull request for the current branch" )
    create.add_argument( '--title', required=True )
    create.add_argument( '--body', default=None, help="pull request body text" )
    create.add_argument( '--body-file', help="read the body from this file instead" )
    create.add_argument( '--head', help="head branch (default: current branch)" )
    create.add_argument( '--base', default=DEFAULT_BASE )
    create.add_argument(
        '--label', action='append', default=[],
        help="label to apply; repeat for more than one (for example --label impact:minor)",
    )
    create.add_argument( '--owner' )
    create.add_argument( '--repo' )

    arguments = parser.parse_args( argv )
    if not arguments.command:
        parser.print_help()
        return 1

    try:
        if arguments.command == 'create-pr':
            return create_pr_command( arguments )
    except ( CredentialError, GitHubHelperError ) as error:
        print( error, file=sys.stderr )
        return 1

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit( main() )
