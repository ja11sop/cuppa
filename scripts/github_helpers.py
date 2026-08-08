"""Higher-level GitHub operations for agents and maintenance, on top of ``github_api``.

``scripts.github_api`` is the credential and transport layer. This module is the place to add
repeated workflows — create a pull request, apply the ``impact:`` label, watch CI — so an agent
does not rewrite the same ``urllib`` call every time. Grow it when the same sequence appears
twice; do not invent helpers for a one-off.

Owner and repository always come from the local ``origin`` remote (or explicit ``--owner`` /
``--repo``). There is no baked-in default, so a checkout of a fork cannot silently talk to the
wrong repository.

Reads on a public repository use the anonymous API. ``show-pr`` (alias ``fetch-pr``),
``pr-status``, and ``watch-pr`` do not unseal the token. Writes (``create-pr``, ``update-pr``,
labelling) and CI log downloads (``fetch-ci-logs``) still go through the sealed credential.

Pushing a branch is still ``git push -u origin HEAD``.

Show pull request metadata (title, labels, body) without unsealing:

    python -m scripts.github_helpers show-pr --pr 165
    python -m scripts.github_helpers fetch-pr --pr 165 --json

Create a pull request from the current branch:

    python -m scripts.github_helpers create-pr \\
        --title "…" --body-file /tmp/pr.md --label impact:minor

Update an open pull request's title and/or body (current branch's PR, or ``--pr``):

    python -m scripts.github_helpers update-pr \\
        --pr 154 --title "…" --body-file /tmp/pr.md

After a push, watch the open pull request's checks until they finish (public read, no seal).
The default schedule waits **2 minutes**, polls once (catching quick lint / setup failures),
waits **another 8 minutes** (about when full CI usually finishes), then polls **every 2 minutes**.
That keeps anonymous API use low. Pass ``--interval N`` for a fixed delay instead. If the
public API rate-limits, ``watch-pr`` falls back to the sealed credential for later polls
(same schedule).

    python -m scripts.github_helpers watch-pr
    python -m scripts.github_helpers pr-status --pr 139

When a check fails, pull the job log excerpt with the sealed credential (Actions logs are not
public even on a public repository):

    python -m scripts.github_helpers fetch-ci-logs
    python -m scripts.github_helpers fetch-ci-logs --job integration-windows

    Or from Python:

    from scripts.github_helpers import (
        create_pull_request, show_pull_request, update_pull_request, watch_pull_request,
    )
    create_pull_request( title='…', body='…', labels=['impact:minor'] )
    show_pull_request( number=165 )
    update_pull_request( number=154, title='…', body='…' )
    watch_pull_request( number=139 )
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from collections import namedtuple

from scripts.github_api import CredentialError, GitHub


DEFAULT_BASE = 'master'
# Wait before 1st poll, wait before 2nd, then steady wait between later polls.
# Total time to the second poll is 2 + 8 = 10 minutes — near typical full CI duration.
DEFAULT_POLL_SCHEDULE_SECONDS = ( 120, 480, 120 )
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


class RateLimited( GitHubHelperError ):
    """Public (or authenticated) GitHub API returned a rate-limit response."""
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


def is_anonymous_client( github ):
    """True when ``github`` has no credential (public reads)."""
    return github is None or getattr( github, '_token', None ) is None


def is_rate_limit_response( status, payload ):
    """True for HTTP 429 or a 403 whose message mentions rate limiting."""
    if status == 429:
        return True
    if status != 403:
        return False
    if not isinstance( payload, dict ):
        return 'rate limit' in str( payload ).lower()
    message = str( payload.get( 'message' ) or '' ).lower()
    return 'rate limit' in message or 'secondary rate' in message


def iter_poll_delays( schedule=None, interval=None ):
    """Yield sleep durations *before* each successive status poll.

    Default schedule: 2 minutes, then 8 minutes, then every 2 minutes. Pass ``interval`` for a
    fixed delay before every poll (including the first), which replaces the schedule.
    """
    if interval is not None:
        if interval < 0:
            raise ValueError( "interval must be >= 0" )
        while True:
            yield interval
    delays = tuple( schedule or DEFAULT_POLL_SCHEDULE_SECONDS )
    if len( delays ) < 3:
        raise ValueError( "poll schedule needs at least three values (first, second, steady)" )
    yield delays[0]
    yield delays[1]
    steady = delays[2]
    while True:
        yield steady


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


def update_pull_request(
        number=None,
        title=None,
        body=None,
        labels=None,
        head=None,
        owner=None,
        repo=None,
        github=None,
):
    """Patch title and/or body on an open pull request; optionally add labels.

    ``number`` defaults to the open pull request for ``head`` (current branch). Returns the
    pull request dict from GitHub after the update.
    """
    if title is None and body is None and not labels:
        raise GitHubHelperError( "give at least one of title, body, or labels to update" )

    owner, repo = repository( owner, repo )
    client = github or GitHub()

    if number is None:
        found = find_open_pull_request( head=head, owner=owner, repo=repo )
        if found is None:
            raise GitHubHelperError(
                "no open pull request for branch [{}]; pass number=".format(
                    head or current_branch()
                )
            )
        number = found['number']

    pull = None
    payload = {}
    if title is not None:
        payload['title'] = title
    if body is not None:
        payload['body'] = body

    if payload:
        status, pull = client.request(
            'PATCH',
            '/repos/{}/{}/pulls/{}'.format( owner, repo, number ),
            payload,
        )
        if status >= 400:
            raise GitHubHelperError( "updating pull request {} failed ({}): {}".format(
                number, status, json.dumps( pull ) ) )

    if labels:
        label_status, labelled = client.request(
            'POST',
            '/repos/{}/{}/issues/{}/labels'.format( owner, repo, number ),
            { 'labels': list( labels ) },
        )
        if label_status >= 400:
            raise GitHubHelperError(
                "pull request {} was updated but labelling failed ({}): {}".format(
                    number, label_status, json.dumps( labelled ) )
            )

    if pull is None:
        status, pull = client.request(
            'GET',
            '/repos/{}/{}/pulls/{}'.format( owner, repo, number ),
        )
        if status >= 400:
            raise GitHubHelperError( "reading pull request {} failed ({}): {}".format(
                number, status, json.dumps( pull ) ) )

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
    if is_rate_limit_response( status, pulls ):
        raise RateLimited( "listing pull requests rate-limited ({}): {}".format(
            status, json.dumps( pulls ) ) )
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
            if is_rate_limit_response( status, pull ):
                raise RateLimited( "reading pull request {} rate-limited ({}): {}".format(
                    number, status, json.dumps( pull ) ) )
            raise GitHubHelperError( "reading pull request {} failed ({}): {}".format(
                number, status, json.dumps( pull ) ) )
        return pull

    pull = find_open_pull_request( head=head, owner=owner, repo=repo, github=client )
    if pull is None:
        raise GitHubHelperError(
            "no open pull request for branch [{}]; pass --pr".format( head or current_branch() )
        )
    return pull


def summarize_pull_request( pull ):
    """Stable fields agents need from a GitHub pull-request payload."""
    labels = [
        label.get( 'name' )
        for label in ( pull.get( 'labels' ) or [] )
        if label.get( 'name' )
    ]
    head = pull.get( 'head' ) or {}
    base = pull.get( 'base' ) or {}
    return {
        'number': pull.get( 'number' ),
        'url': pull.get( 'html_url' ) or '',
        'title': pull.get( 'title' ) or '',
        'state': pull.get( 'state' ) or '',
        'draft': bool( pull.get( 'draft' ) ),
        'mergeable_state': pull.get( 'mergeable_state' ) or '',
        'labels': labels,
        'head': {
            'ref': head.get( 'ref' ) or '',
            'sha': head.get( 'sha' ) or '',
        },
        'base': {
            'ref': base.get( 'ref' ) or '',
        },
        'body': pull.get( 'body' ) or '',
    }


def format_pull_request( summary ):
    """Human-readable ``show-pr`` output from :func:`summarize_pull_request`."""
    head = summary.get( 'head' ) or {}
    base = summary.get( 'base' ) or {}
    sha = head.get( 'sha' ) or ''
    short_sha = sha[:8] if sha else '-'
    labels = summary.get( 'labels' ) or []
    label_text = ', '.join( labels ) if labels else '-'
    lines = [
        "PR #{} {}".format( summary.get( 'number' ), summary.get( 'url' ) or '' ).rstrip(),
        "title: {}".format( summary.get( 'title' ) or '' ),
        "state={}  draft={}  mergeable_state={}".format(
            summary.get( 'state' ) or '-',
            'true' if summary.get( 'draft' ) else 'false',
            summary.get( 'mergeable_state' ) or '-',
        ),
        "labels: {}".format( label_text ),
        "head: {} @ {}".format( head.get( 'ref' ) or '-', short_sha ),
        "base: {}".format( base.get( 'ref' ) or '-' ),
    ]
    body = summary.get( 'body' ) or ''
    if body:
        lines.append( '---' )
        lines.append( body.rstrip( '\n' ) )
    return "\n".join( lines )


def show_pull_request( number=None, head=None, owner=None, repo=None, github=None ):
    """Pull request metadata (public API by default). Returns a summary dict."""
    owner, repo = repository( owner, repo )
    client = public_github( github )
    pull = resolve_pull_request(
        number=number, head=head, owner=owner, repo=repo, github=client
    )
    return summarize_pull_request( pull )


def _pull_with_auth_fallback( number=None, head=None, owner=None, repo=None, github=None, out=None ):
    """Return ``(summary, client)``, switching to the sealed token on rate limit."""
    out = out or sys.stdout
    client = public_github( github )
    try:
        return show_pull_request(
            number=number, head=head, owner=owner, repo=repo, github=client
        ), client
    except RateLimited:
        if not is_anonymous_client( client ):
            raise
        out.write(
            "public API rate-limited; retrying with sealed credential\n"
        )
        out.flush()
        client = GitHub()
        return show_pull_request(
            number=number, head=head, owner=owner, repo=repo, github=client
        ), client


def _check_runs_for( sha, owner, repo, github ):
    status, payload = github.request(
        'GET',
        '/repos/{}/{}/commits/{}/check-runs?per_page=100'.format( owner, repo, sha ),
    )
    if is_rate_limit_response( status, payload ):
        raise RateLimited( "reading check runs rate-limited ({}): {}".format(
            status, json.dumps( payload ) ) )
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
    """Where the pull request's checks stand right now (public API by default)."""
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


def _status_with_auth_fallback( number=None, head=None, owner=None, repo=None, github=None, out=None ):
    """Return ``(PullRequestStatus, client)``, switching to the sealed token on rate limit."""
    out = out or sys.stdout
    client = public_github( github )
    try:
        return pull_request_status(
            number=number, head=head, owner=owner, repo=repo, github=client
        ), client
    except RateLimited:
        if not is_anonymous_client( client ):
            raise
        out.write(
            "public API rate-limited; retrying with sealed credential "
            "(same poll schedule)\n"
        )
        out.flush()
        client = GitHub()
        return pull_request_status(
            number=number, head=head, owner=owner, repo=repo, github=client
        ), client


def watch_pull_request(
        number=None,
        head=None,
        owner=None,
        repo=None,
        github=None,
        interval=None,
        schedule=None,
        timeout=DEFAULT_WATCH_TIMEOUT,
        out=None,
        sleep=time.sleep,
        clock=time.monotonic,
):
    """Poll until checks finish. Returns ``(exit_code, PullRequestStatus)``.

    Sleeps *before* each poll. Default schedule: 2 minutes, then 8 minutes, then every
    2 minutes. Pass ``interval`` for a fixed delay instead. On public rate limits, falls back
    to the sealed credential and keeps that client for later polls.
    """
    out = out or sys.stdout
    deadline = clock() + timeout
    last = None
    client = github
    delays = iter_poll_delays( schedule=schedule, interval=interval )

    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            out.write( "timed out after {}s while checks were still pending\n".format( timeout ) )
            out.flush()
            return EXIT_TIMEOUT, last

        delay = next( delays )
        sleep( min( delay, remaining ) )

        remaining = deadline - clock()
        if remaining < 0 and last is not None:
            out.write( "timed out after {}s while checks were still pending\n".format( timeout ) )
            out.flush()
            return EXIT_TIMEOUT, last

        last, client = _status_with_auth_fallback(
            number=number, head=head, owner=owner, repo=repo, github=client, out=out
        )
        out.write( format_pull_request_status( last ) + "\n" )
        out.flush()

        if last.outcome != 'pending':
            return exit_code_for( last.outcome ), last


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


FAILURE_LINE_MARKERS = (
    'FAILED ',
    'ERROR ',
    'AssertionError',
    'PermissionError',
    'Traceback (most recent call last)',
    'E       ',
    ' short test summary ',
)


def _workflow_run_for_sha( sha, owner, repo, github ):
    status, payload = github.request(
        'GET',
        '/repos/{}/{}/actions/runs?head_sha={}&per_page=10'.format( owner, repo, sha ),
    )
    if status >= 400:
        raise GitHubHelperError( "listing workflow runs failed ({}): {}".format(
            status, json.dumps( payload ) ) )
    runs = payload.get( 'workflow_runs' ) or []
    if not runs:
        raise GitHubHelperError( "no workflow runs for commit {}".format( sha[:8] ) )
    # Prefer the newest completed failure when several workflows exist; else newest.
    failed = [ run for run in runs if run.get( 'conclusion' ) in FAILED_CONCLUSIONS ]
    return ( failed or runs )[0]


def _job_name_filters( status, job=None ):
    """Substring filters for zip members / job folders from failed checks or ``--job``."""
    if job:
        return [ job ]
    failed = [
        check.name for check in status.checks
        if check.status == 'completed' and check.conclusion in FAILED_CONCLUSIONS
    ]
    if not failed:
        raise GitHubHelperError(
            "no failed checks on PR #{} (outcome={}); pass --job to pick a job".format(
                status.number, status.outcome
            )
        )
    return failed


def _member_matches( name, filters ):
    lowered = name.lower().replace( '\\', '/' )
    for needle in filters:
        token = needle.lower().replace( ' ', '-' )
        if token in lowered or needle.lower() in lowered:
            return True
    return False


def _interesting_log_lines( text ):
    lines = text.splitlines()
    interesting = []
    for index, line in enumerate( lines ):
        # Drop the leading GitHub Actions timestamp / stream prefix when present.
        body = re.sub( r'^\d{4}-\d{2}-\d{2}T[^\s]+\s+', '', line )
        if any( marker in body for marker in FAILURE_LINE_MARKERS ):
            interesting.append( body )
            continue
        # Keep a little context after pytest failure headers.
        if body.strip().startswith( '____' ) and 'test_' in body:
            interesting.append( body )
    # Deduplicate while preserving order (run zip often duplicates job + step files).
    seen = set()
    unique = []
    for line in interesting:
        if line in seen:
            continue
        seen.add( line )
        unique.append( line )
    return unique


def fetch_ci_logs(
        number=None,
        head=None,
        owner=None,
        repo=None,
        job=None,
        run_id=None,
        output_dir=None,
        full=False,
        github=None,
        public=None,
        out=None,
):
    """Download Actions logs for failed checks (or ``--job``) and print failure excerpts.

    Status discovery uses the public API. The log zip requires the sealed credential — GitHub
    returns 403 for anonymous log downloads even on public repositories.
    """
    out = out or sys.stdout
    owner, repo = repository( owner, repo )
    public_client = public_github( public )
    status = pull_request_status(
        number=number, head=head, owner=owner, repo=repo, github=public_client
    )
    filters = _job_name_filters( status, job=job )

    if run_id is None:
        run = _workflow_run_for_sha( status.head_sha, owner, repo, public_client )
        run_id = run['id']
        out.write( "workflow run {} ({})  head={}\n".format(
            run_id,
            run.get( 'conclusion' ) or run.get( 'status' ),
            status.head_sha[:8],
        ) )
    else:
        out.write( "workflow run {}\n".format( run_id ) )
    out.write( "jobs: {}\n".format( ', '.join( filters ) ) )
    out.flush()

    auth = github or GitHub()
    code, payload = auth.download(
        '/repos/{}/{}/actions/runs/{}/logs'.format( owner, repo, run_id )
    )
    if code >= 400:
        message = payload.get( 'message' ) if isinstance( payload, dict ) else payload
        raise GitHubHelperError(
            "downloading logs failed ({}): {}. "
            "Fine-grained tokens need Actions read permission for this repository.".format(
                code, message
            )
        )
    if not isinstance( payload, ( bytes, bytearray ) ):
        raise GitHubHelperError( "expected a zip archive, got {}".format( type( payload ) ) )

    if output_dir:
        os.makedirs( output_dir, exist_ok=True )
        zip_path = os.path.join( output_dir, 'run-{}-logs.zip'.format( run_id ) )
        with open( zip_path, 'wb' ) as handle:
            handle.write( payload )
        out.write( "saved {}\n".format( zip_path ) )

    with zipfile.ZipFile( io.BytesIO( payload ) ) as archive:
        members = [ name for name in archive.namelist() if _member_matches( name, filters ) ]
        if not members:
            raise GitHubHelperError(
                "no log members matched {}; archive has: {}".format(
                    filters, ', '.join( archive.namelist()[:20] )
                )
            )
        # Prefer the integration/test step files over setup noise.
        preferred = [
            name for name in members
            if re.search( r'(?i)(test|integration|pytest)', os.path.basename( name ) )
        ]
        selected = preferred or members
        for name in selected:
            text = archive.read( name ).decode( 'utf-8', 'replace' )
            out.write( "\n=== {} ===\n".format( name ) )
            if full:
                out.write( text )
                if not text.endswith( '\n' ):
                    out.write( '\n' )
                continue
            excerpt = _interesting_log_lines( text )
            if not excerpt:
                out.write( "(no failure markers; pass --full for the whole file)\n" )
                continue
            for line in excerpt:
                out.write( line + '\n' )
    out.flush()
    return EXIT_SUCCESS


def _read_body( arguments, required=True ):
    if getattr( arguments, 'body_file', None ):
        with open( arguments.body_file, encoding='utf-8' ) as body_file:
            return body_file.read()
    if getattr( arguments, 'body', None ) is not None:
        return arguments.body
    if required:
        raise GitHubHelperError( "give --body or --body-file" )
    return None


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


def update_pr_command( arguments ):
    pull = update_pull_request(
        number = arguments.pr,
        title = arguments.title,
        body = _read_body( arguments, required=False ),
        labels = arguments.label or None,
        head = arguments.head,
        owner = arguments.owner,
        repo = arguments.repo,
    )
    print( pull['html_url'] )
    return 0


def pr_status_command( arguments ):
    github = GitHub() if arguments.auth else None
    status, _client = _status_with_auth_fallback(
        number = arguments.pr,
        head = arguments.head,
        owner = arguments.owner,
        repo = arguments.repo,
        github = github,
    )
    print( format_pull_request_status( status ) )
    return exit_code_for( status.outcome )


def show_pr_command( arguments ):
    github = GitHub() if arguments.auth else None
    summary, _client = _pull_with_auth_fallback(
        number = arguments.pr,
        head = arguments.head,
        owner = arguments.owner,
        repo = arguments.repo,
        github = github,
    )
    if arguments.json:
        print( json.dumps( summary, indent=2, sort_keys=True ) )
    else:
        print( format_pull_request( summary ) )
    return 0


def watch_pr_command( arguments ):
    github = GitHub() if arguments.auth else None
    code, _ = watch_pull_request(
        number = arguments.pr,
        head = arguments.head,
        owner = arguments.owner,
        repo = arguments.repo,
        github = github,
        interval = arguments.interval,
        timeout = arguments.timeout,
    )
    return code


def fetch_ci_logs_command( arguments ):
    return fetch_ci_logs(
        number = arguments.pr,
        head = arguments.head,
        owner = arguments.owner,
        repo = arguments.repo,
        job = arguments.job,
        run_id = arguments.run_id,
        output_dir = arguments.output_dir,
        full = arguments.full,
    )


def _add_pr_selection_arguments( parser ):
    parser.add_argument( '--pr', type=int, help="pull request number (default: open PR for branch)" )
    parser.add_argument( '--head', help="branch used to find an open pull request" )
    parser.add_argument( '--owner' )
    parser.add_argument( '--repo' )
    parser.add_argument(
        '--auth', action='store_true',
        help="use the sealed credential instead of the public API (also used automatically "
             "when the public API rate-limits)",
    )


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

    update = commands.add_parser(
        'update-pr',
        help="update title and/or body on an open pull request (sealed token)",
    )
    update.add_argument( '--pr', type=int, help="pull request number (default: open PR for head)" )
    update.add_argument( '--title', help="new pull request title" )
    update.add_argument( '--body', default=None, help="new pull request body text" )
    update.add_argument( '--body-file', help="read the new body from this file instead" )
    update.add_argument( '--head', help="head branch used to find the open PR (default: current)" )
    update.add_argument(
        '--label', action='append', default=[],
        help="label to add; repeat for more than one",
    )
    update.add_argument( '--owner' )
    update.add_argument( '--repo' )

    status = commands.add_parser( 'pr-status', help="show check status once and exit" )
    _add_pr_selection_arguments( status )

    show = commands.add_parser(
        'show-pr',
        aliases=[ 'fetch-pr' ],
        help="show pull request title, labels, and body (public API)",
    )
    _add_pr_selection_arguments( show )
    show.add_argument(
        '--json', action='store_true',
        help="print a JSON summary instead of the human-readable form",
    )

    watch = commands.add_parser(
        'watch-pr',
        help="poll check status until the pull request finishes (or times out)",
    )
    _add_pr_selection_arguments( watch )
    watch.add_argument(
        '--interval', type=int, default=None,
        help="fixed seconds before every poll (default: schedule 120, then 480, then every 120)",
    )
    watch.add_argument(
        '--timeout', type=int, default=DEFAULT_WATCH_TIMEOUT,
        help="give up after this many seconds (default {})".format( DEFAULT_WATCH_TIMEOUT ),
    )

    logs = commands.add_parser(
        'fetch-ci-logs',
        help="download Actions logs for failed checks (sealed token; not public)",
    )
    _add_pr_selection_arguments( logs )
    logs.add_argument(
        '--job',
        help="job / check name substring (default: all failed checks from pr-status)",
    )
    logs.add_argument( '--run-id', type=int, help="workflow run id (default: newest for PR head)" )
    logs.add_argument(
        '--output-dir',
        help="also save the raw run log zip under this directory",
    )
    logs.add_argument(
        '--full', action='store_true',
        help="print matched log files in full instead of failure excerpts",
    )

    arguments = parser.parse_args( argv )
    if not arguments.command:
        parser.print_help()
        return 1

    try:
        if arguments.command == 'create-pr':
            return create_pr_command( arguments )
        if arguments.command == 'update-pr':
            return update_pr_command( arguments )
        if arguments.command == 'pr-status':
            return pr_status_command( arguments )
        if arguments.command in ( 'show-pr', 'fetch-pr' ):
            return show_pr_command( arguments )
        if arguments.command == 'watch-pr':
            return watch_pr_command( arguments )
        if arguments.command == 'fetch-ci-logs':
            return fetch_ci_logs_command( arguments )
    except ( CredentialError, GitHubHelperError ) as error:
        print( error, file=sys.stderr )
        return 1

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit( main() )
