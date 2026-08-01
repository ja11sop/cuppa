"""Higher-level GitHub operations for agents and maintenance, on top of ``github_api``.

``scripts.github_api`` is the credential and transport layer. This module is the place to add
repeated workflows — create a pull request, apply the ``impact:`` label, watch CI — so an agent
does not rewrite the same ``urllib`` call every time. Grow it when the same sequence appears
twice; do not invent helpers for a one-off.

Owner and repository always come from the local ``origin`` remote (or explicit ``--owner`` /
``--repo``). There is no baked-in default, so a checkout of a fork cannot silently talk to the
wrong repository.

Reads on a public repository use the anonymous API. ``pr-status`` and ``watch-pr`` do not unseal
the token. Writes (``create-pr``, labelling) still go through the sealed credential.

Pushing a branch is still ``git push -u origin HEAD``.

Create a pull request from the current branch:

    python -m scripts.github_helpers create-pr \\
        --title "…" --body-file /tmp/pr.md --label impact:minor

After a push, watch the open pull request's checks until they finish (public read, no seal):

    python -m scripts.github_helpers watch-pr
    python -m scripts.github_helpers pr-status --pr 139

Or from Python:

    from scripts.github_helpers import create_pull_request, watch_pull_request
    create_pull_request( title='…', body='…', labels=['impact:minor'] )
    watch_pull_request( number=139 )
"""

import argparse
import json
import re
import subprocess
import sys
import time
from collections import namedtuple

from scripts.github_api import CredentialError, GitHub


DEFAULT_BASE = 'master'
DEFAULT_POLL_SECONDS = 180
DEFAULT_WATCH_TIMEOUT = 3600

# Exit codes for pr-status / watch-pr so agents can branch without parsing prose.
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_PENDING = 2
EXIT_TIMEOUT = 3

# A check counts as a failure for our purposes when GitHub marks it unsuccessful.
FAILED_CONCLUSIONS = frozenset( {
    'failure', 'cancelled', 'timed_out', 'action_required', 'stale', 'startup_failure',
} )


class GitHubHelperError( Exception ):
    pass


PullRequestStatus = namedtuple(
    'PullRequestStatus',
    [ 'number', 'url', 'head_sha', 'state', 'mergeable_state', 'checks', 'outcome' ],
)

CheckRun = namedtuple( 'CheckRun', [ 'name', 'status', 'conclusion', 'url' ] )


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
    """``owner/repo`` for API paths, taken from the local ``origin`` remote.

    Explicit arguments win when both are given. Otherwise ``origin`` must be configured and parse
    as a GitHub owner/repo URL — there is no fallback name, so a missing or exotic remote fails
    loudly instead of talking to the wrong repository.
    """
    if owner and repo:
        return owner, repo
    if owner or repo:
        raise GitHubHelperError( "give both --owner and --repo, or neither" )

    url = _run_git( 'config', '--get', 'remote.origin.url' )
    match = re.search( r'[:/]([^/]+)/([^/]+?)(?:\.git)?$', url )
    if not match:
        raise GitHubHelperError(
            "could not parse owner/repo from origin remote [{}]".format( url )
        )
    return match.group( 1 ), match.group( 2 )


def public_github( github=None ):
    """Client for public reads. Reuses ``github`` when the caller already has one."""
    return github if github is not None else GitHub.public()


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


def find_open_pull_request( head=None, owner=None, repo=None, github=None ):
    """The open pull request for ``head`` (default: current branch), or None."""
    owner, repo = repository( owner, repo )
    head = head or current_branch()
    client = public_github( github )

    status, pulls = client.request(
        'GET',
        '/repos/{}/{}/pulls?state=open&head={}:{}'.format( owner, repo, owner, head ),
    )
    if status >= 400:
        raise GitHubHelperError( "listing pull requests failed ({}): {}".format(
            status, json.dumps( pulls ) ) )
    if not pulls:
        return None
    return pulls[0]


def resolve_pull_request( number=None, head=None, owner=None, repo=None, github=None ):
    """A pull request by number, or the open one for the current branch."""
    owner, repo = repository( owner, repo )
    client = public_github( github )

    if number is not None:
        status, pull = client.request(
            'GET',
            '/repos/{}/{}/pulls/{}'.format( owner, repo, number ),
        )
        if status >= 400:
            raise GitHubHelperError( "reading pull request {} failed ({}): {}".format(
                number, status, json.dumps( pull ) ) )
        return pull

    pull = find_open_pull_request( head=head, owner=owner, repo=repo, github=client )
    if pull is None:
        raise GitHubHelperError(
            "no open pull request for branch [{}]; pass --pr".format( head or current_branch() )
        )
    return pull


def _check_runs_for( sha, owner, repo, github ):
    status, payload = github.request(
        'GET',
        '/repos/{}/{}/commits/{}/check-runs?per_page=100'.format( owner, repo, sha ),
    )
    if status >= 400:
        raise GitHubHelperError( "reading check runs failed ({}): {}".format(
            status, json.dumps( payload ) ) )

    checks = []
    for run in payload.get( 'check_runs', [] ):
        checks.append( CheckRun(
            name = run.get( 'name' ) or '(unnamed)',
            status = run.get( 'status' ) or 'queued',
            conclusion = run.get( 'conclusion' ),
            url = ( run.get( 'html_url' ) or run.get( 'details_url' ) or '' ),
        ) )
    return sorted( checks, key=lambda check: check.name.lower() )


def outcome_for( checks ):
    """``pending``, ``success``, or ``failure`` for a set of check runs."""
    if not checks:
        return 'pending'
    if any( check.status != 'completed' for check in checks ):
        return 'pending'
    if any( check.conclusion in FAILED_CONCLUSIONS for check in checks ):
        return 'failure'
    # success, neutral, and skipped are all fine to merge past.
    return 'success'


def pull_request_status( number=None, head=None, owner=None, repo=None, github=None ):
    """Where the pull request's checks stand right now (public API; no sealed token)."""
    owner, repo = repository( owner, repo )
    client = public_github( github )
    pull = resolve_pull_request(
        number=number, head=head, owner=owner, repo=repo, github=client
    )
    sha = pull['head']['sha']
    checks = _check_runs_for( sha, owner, repo, client )
    return PullRequestStatus(
        number = pull['number'],
        url = pull.get( 'html_url' ) or '',
        head_sha = sha,
        state = pull.get( 'state' ) or '',
        mergeable_state = pull.get( 'mergeable_state' ) or '',
        checks = checks,
        outcome = outcome_for( checks ),
    )


def format_pull_request_status( status ):
    lines = [
        "PR #{} {}  head={}  mergeable_state={}  outcome={}".format(
            status.number,
            status.url,
            status.head_sha[:8],
            status.mergeable_state or '-',
            status.outcome,
        )
    ]
    if not status.checks:
        lines.append( "  (no check runs yet)" )
        return "\n".join( lines )

    width = max( len( check.name ) for check in status.checks )
    for check in status.checks:
        detail = check.conclusion if check.status == 'completed' else check.status
        lines.append( "  {:<{}}  {}".format( check.name, width, detail ) )
    return "\n".join( lines )


def exit_code_for( outcome ):
    if outcome == 'success':
        return EXIT_SUCCESS
    if outcome == 'failure':
        return EXIT_FAILURE
    return EXIT_PENDING


def watch_pull_request(
        number=None,
        head=None,
        owner=None,
        repo=None,
        github=None,
        interval=DEFAULT_POLL_SECONDS,
        timeout=DEFAULT_WATCH_TIMEOUT,
        out=None,
        sleep=time.sleep,
        clock=time.monotonic,
):
    """Poll until checks finish. Returns ``(exit_code, PullRequestStatus)``."""
    out = out or sys.stdout
    deadline = clock() + timeout
    last = None

    while True:
        last = pull_request_status(
            number=number, head=head, owner=owner, repo=repo, github=github
        )
        out.write( format_pull_request_status( last ) + "\n" )
        out.flush()

        if last.outcome != 'pending':
            return exit_code_for( last.outcome ), last

        remaining = deadline - clock()
        if remaining <= 0:
            out.write( "timed out after {}s while checks were still pending\n".format( timeout ) )
            out.flush()
            return EXIT_TIMEOUT, last

        sleep( min( interval, remaining ) )


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


def pr_status_command( arguments ):
    status = pull_request_status(
        number = arguments.pr,
        head = arguments.head,
        owner = arguments.owner,
        repo = arguments.repo,
    )
    print( format_pull_request_status( status ) )
    return exit_code_for( status.outcome )


def watch_pr_command( arguments ):
    code, _ = watch_pull_request(
        number = arguments.pr,
        head = arguments.head,
        owner = arguments.owner,
        repo = arguments.repo,
        interval = arguments.interval,
        timeout = arguments.timeout,
    )
    return code


def _add_pr_selection_arguments( parser ):
    parser.add_argument( '--pr', type=int, help="pull request number (default: open PR for branch)" )
    parser.add_argument( '--head', help="branch used to find an open pull request" )
    parser.add_argument( '--owner' )
    parser.add_argument( '--repo' )


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

    status = commands.add_parser( 'pr-status', help="show check status once and exit" )
    _add_pr_selection_arguments( status )

    watch = commands.add_parser(
        'watch-pr',
        help="poll check status until the pull request finishes (or times out)",
    )
    _add_pr_selection_arguments( watch )
    watch.add_argument(
        '--interval', type=int, default=DEFAULT_POLL_SECONDS,
        help="seconds between polls (default {} = 3 minutes)".format( DEFAULT_POLL_SECONDS ),
    )
    watch.add_argument(
        '--timeout', type=int, default=DEFAULT_WATCH_TIMEOUT,
        help="give up after this many seconds (default {})".format( DEFAULT_WATCH_TIMEOUT ),
    )

    arguments = parser.parse_args( argv )
    if not arguments.command:
        parser.print_help()
        return 1

    try:
        if arguments.command == 'create-pr':
            return create_pr_command( arguments )
        if arguments.command == 'pr-status':
            return pr_status_command( arguments )
        if arguments.command == 'watch-pr':
            return watch_pr_command( arguments )
    except ( CredentialError, GitHubHelperError ) as error:
        print( error, file=sys.stderr )
        return 1

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit( main() )
