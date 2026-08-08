import io

import pytest

from scripts import github_helpers


pytestmark = pytest.mark.unit


class FakeGitHub( object ):

    def __init__( self, responses=None ):
        self.calls = []
        self.responses = list( responses or [] )

    def request( self, method, path, payload=None ):
        self.calls.append( ( method, path, payload ) )
        if self.responses:
            return self.responses.pop( 0 )
        if path.endswith( '/pulls' ) and method == 'POST':
            return 201, { 'number': 42, 'html_url': 'https://example.com/pr/42' }
        if path.endswith( '/labels' ):
            return 200, [ { 'name': label } for label in payload['labels'] ]
        return 404, {}


def test_repository_parses_ssh_and_https_remotes( monkeypatch ):
    monkeypatch.setattr(
        github_helpers, '_run_git',
        lambda *args: 'git@github.com:ja11sop/cuppa.git' if args[-1] == 'remote.origin.url' else '',
    )
    assert github_helpers.repository() == ( 'ja11sop', 'cuppa' )

    monkeypatch.setattr(
        github_helpers, '_run_git',
        lambda *args: 'https://github.com/ja11sop/cuppa.git',
    )
    assert github_helpers.repository() == ( 'ja11sop', 'cuppa' )


def test_repository_fails_when_origin_is_missing_or_unparseable( monkeypatch ):
    def fail( *args ):
        raise github_helpers.GitHubHelperError( 'no git' )
    monkeypatch.setattr( github_helpers, '_run_git', fail )
    with pytest.raises( github_helpers.GitHubHelperError, match='no git' ):
        github_helpers.repository()

    monkeypatch.setattr( github_helpers, '_run_git', lambda *args: 'not-a-github-remote' )
    with pytest.raises( github_helpers.GitHubHelperError, match='could not parse' ):
        github_helpers.repository()


def test_pull_request_status_uses_a_public_client_by_default( monkeypatch ):
    created = []

    class CapturingPublic( object ):
        @classmethod
        def public( cls ):
            client = FakeGitHub( responses=[
                ( 200, {
                    'number': 139,
                    'html_url': 'https://example.com/pr/139',
                    'state': 'open',
                    'mergeable_state': 'clean',
                    'head': { 'sha': 'abcdef0123456789' },
                } ),
                ( 200, { 'check_runs': [] } ),
            ] )
            created.append( client )
            return client

    monkeypatch.setattr( github_helpers, 'GitHub', CapturingPublic )
    monkeypatch.setattr(
        github_helpers, 'repository',
        lambda owner=None, repo=None: ( 'ja11sop', 'cuppa' ),
    )

    status = github_helpers.pull_request_status( number=139 )
    assert status.number == 139
    assert created, "status helpers must use GitHub.public(), not the sealed client"


def test_show_pull_request_uses_public_api_and_summarises( monkeypatch ):
    created = []

    class CapturingPublic( object ):
        @classmethod
        def public( cls ):
            client = FakeGitHub( responses=[
                ( 200, {
                    'number': 165,
                    'html_url': 'https://example.com/pr/165',
                    'title': 'Share download progress',
                    'body': '## Summary\n\nProgress bars.\n',
                    'state': 'open',
                    'draft': False,
                    'mergeable_state': 'unstable',
                    'labels': [ { 'name': 'impact:patch' } ],
                    'head': { 'ref': 'download_progress', 'sha': 'f8a68cb8deadbeef' },
                    'base': { 'ref': 'master' },
                } ),
            ] )
            created.append( client )
            return client

    monkeypatch.setattr( github_helpers, 'GitHub', CapturingPublic )
    monkeypatch.setattr(
        github_helpers, 'repository',
        lambda owner=None, repo=None: ( 'ja11sop', 'cuppa' ),
    )

    summary = github_helpers.show_pull_request( number=165 )
    assert created, "show-pr must use GitHub.public(), not the sealed client"
    assert summary['number'] == 165
    assert summary['labels'] == [ 'impact:patch' ]
    assert summary['head']['ref'] == 'download_progress'
    assert summary['head']['sha'].startswith( 'f8a68cb8' )
    assert 'Progress bars' in summary['body']

    rendered = github_helpers.format_pull_request( summary )
    assert 'PR #165' in rendered
    assert 'title: Share download progress' in rendered
    assert 'labels: impact:patch' in rendered
    assert 'head: download_progress @ f8a68cb8' in rendered
    assert 'Progress bars' in rendered


def test_show_pr_command_json( monkeypatch, capsys ):
    monkeypatch.setattr(
        github_helpers, 'show_pull_request',
        lambda **kwargs: {
            'number': 165,
            'url': 'https://example.com/pr/165',
            'title': 'Share download progress',
            'state': 'open',
            'draft': False,
            'mergeable_state': 'clean',
            'labels': [ 'impact:patch' ],
            'head': { 'ref': 'download_progress', 'sha': 'abc12345' },
            'base': { 'ref': 'master' },
            'body': 'body text',
        },
    )
    code = github_helpers.main( [ 'show-pr', '--pr', '165', '--json' ] )
    assert code == 0
    payload = __import__( 'json' ).loads( capsys.readouterr().out )
    assert payload['number'] == 165
    assert payload['labels'] == [ 'impact:patch' ]


def test_fetch_pr_alias_dispatches( monkeypatch, capsys ):
    monkeypatch.setattr(
        github_helpers, '_pull_with_auth_fallback',
        lambda **kwargs: ( {
            'number': 1,
            'url': 'https://example.com/pr/1',
            'title': 'T',
            'state': 'open',
            'draft': False,
            'mergeable_state': 'clean',
            'labels': [],
            'head': { 'ref': 'b', 'sha': 'deadbeef' },
            'base': { 'ref': 'master' },
            'body': '',
        }, object() ),
    )
    code = github_helpers.main( [ 'fetch-pr', '--pr', '1' ] )
    assert code == 0
    assert 'PR #1' in capsys.readouterr().out


def test_create_pull_request_opens_and_labels( monkeypatch ):
    monkeypatch.setattr( github_helpers, 'current_branch', lambda: 'feature' )
    client = FakeGitHub()

    pull = github_helpers.create_pull_request(
        title = 'A change',
        body = 'Why',
        labels = [ 'impact:minor' ],
        github = client,
    )

    assert pull['html_url'] == 'https://example.com/pr/42'
    assert client.calls[0][0] == 'POST'
    assert client.calls[0][1].endswith( '/pulls' )
    assert client.calls[0][2]['head'] == 'feature'
    assert client.calls[0][2]['base'] == 'master'
    assert client.calls[1][1].endswith( '/issues/42/labels' )
    assert client.calls[1][2] == { 'labels': [ 'impact:minor' ] }


def test_create_pull_request_reports_api_failure():
    class Failing( object ):
        def request( self, method, path, payload=None ):
            return 422, { 'message': 'Validation Failed' }

    with pytest.raises( github_helpers.GitHubHelperError, match='422' ):
        github_helpers.create_pull_request(
            title = 'A change',
            body = 'Why',
            head = 'feature',
            github = Failing(),
        )


def test_update_pull_request_patches_title_and_body( monkeypatch ):
    monkeypatch.setattr(
        github_helpers, 'repository',
        lambda owner=None, repo=None: ( 'ja11sop', 'cuppa' ),
    )
    client = FakeGitHub( responses=[
        ( 200, {
            'number': 154,
            'html_url': 'https://example.com/pr/154',
            'title': 'New title',
            'body': 'New body',
        } ),
    ] )

    pull = github_helpers.update_pull_request(
        number = 154,
        title = 'New title',
        body = 'New body',
        github = client,
    )

    assert pull['html_url'] == 'https://example.com/pr/154'
    assert client.calls[0][0] == 'PATCH'
    assert client.calls[0][1].endswith( '/pulls/154' )
    assert client.calls[0][2] == { 'title': 'New title', 'body': 'New body' }


def test_update_pull_request_finds_open_pr_when_number_omitted( monkeypatch ):
    monkeypatch.setattr( github_helpers, 'current_branch', lambda: 'feature' )
    monkeypatch.setattr(
        github_helpers, 'repository',
        lambda owner=None, repo=None: ( 'ja11sop', 'cuppa' ),
    )
    monkeypatch.setattr(
        github_helpers, 'find_open_pull_request',
        lambda **kwargs: { 'number': 99, 'html_url': 'https://example.com/pr/99' },
    )
    client = FakeGitHub( responses=[
        ( 200, { 'number': 99, 'html_url': 'https://example.com/pr/99' } ),
    ] )

    pull = github_helpers.update_pull_request(
        title = 'Only title',
        github = client,
    )
    assert pull['number'] == 99
    assert client.calls[0][2] == { 'title': 'Only title' }


def test_update_pull_request_requires_something_to_change():
    with pytest.raises( github_helpers.GitHubHelperError, match='at least one' ):
        github_helpers.update_pull_request( number=1, github=FakeGitHub() )


def test_outcome_for_pending_success_and_failure():
    pending = [ github_helpers.CheckRun( 'unit', 'in_progress', None, '' ) ]
    assert github_helpers.outcome_for( pending ) == 'pending'
    assert github_helpers.outcome_for( [] ) == 'pending'

    ok = [
        github_helpers.CheckRun( 'unit', 'completed', 'success', '' ),
        github_helpers.CheckRun( 'docs', 'completed', 'skipped', '' ),
    ]
    assert github_helpers.outcome_for( ok ) == 'success'

    bad = [
        github_helpers.CheckRun( 'unit', 'completed', 'success', '' ),
        github_helpers.CheckRun( 'integration', 'completed', 'failure', '' ),
    ]
    assert github_helpers.outcome_for( bad ) == 'failure'


def test_pull_request_status_summarises_checks( monkeypatch ):
    monkeypatch.setattr( github_helpers, 'current_branch', lambda: 'feature' )
    client = FakeGitHub( responses=[
        ( 200, [ {
            'number': 139,
            'html_url': 'https://example.com/pr/139',
            'state': 'open',
            'mergeable_state': 'unstable',
            'head': { 'sha': 'abcdef0123456789' },
        } ] ),
        ( 200, {
            'check_runs': [
                {
                    'name': 'unit',
                    'status': 'completed',
                    'conclusion': 'success',
                    'html_url': 'https://example.com/unit',
                },
                {
                    'name': 'integration',
                    'status': 'in_progress',
                    'conclusion': None,
                    'html_url': 'https://example.com/integration',
                },
            ]
        } ),
    ] )

    status = github_helpers.pull_request_status( github=client )
    assert status.number == 139
    assert status.outcome == 'pending'
    assert [ check.name for check in status.checks ] == [ 'integration', 'unit' ]

    rendered = github_helpers.format_pull_request_status( status )
    assert 'PR #139' in rendered
    assert 'outcome=pending' in rendered
    assert 'integration' in rendered and 'in_progress' in rendered


def test_watch_pull_request_returns_when_checks_finish( monkeypatch ):
    monkeypatch.setattr( github_helpers, 'current_branch', lambda: 'feature' )
    monkeypatch.setattr(
        github_helpers, 'repository',
        lambda owner=None, repo=None: ( 'ja11sop', 'cuppa' ),
    )
    pending = github_helpers.PullRequestStatus(
        number=139,
        url='https://example.com/pr/139',
        head_sha='abcdef01',
        state='open',
        mergeable_state='unstable',
        checks=[ github_helpers.CheckRun( 'unit', 'in_progress', None, '' ) ],
        outcome='pending',
    )
    success = pending._replace(
        checks=[ github_helpers.CheckRun( 'unit', 'completed', 'success', '' ) ],
        outcome='success',
        mergeable_state='clean',
    )
    states = [ pending, success ]
    seen_numbers = []

    def fake_status( **kwargs ):
        seen_numbers.append( kwargs.get( 'number' ) )
        return states.pop( 0 )

    monkeypatch.setattr( github_helpers, 'pull_request_status', fake_status )
    monkeypatch.setattr(
        github_helpers, 'resolve_pull_request',
        lambda **kwargs: { 'number': 139 },
    )

    sleeps = []
    out = io.StringIO()
    code, last = github_helpers.watch_pull_request(
        interval=1,
        timeout=60,
        out=out,
        sleep=lambda seconds: sleeps.append( seconds ),
        clock=lambda: 0 if len( sleeps ) == 0 else 10,
    )

    assert code == github_helpers.EXIT_SUCCESS
    assert last.outcome == 'success'
    # Sleep before each poll (fixed --interval): pending then success.
    assert sleeps == [ 1, 1 ]
    assert seen_numbers == [ 139, 139 ]
    assert 'outcome=pending' in out.getvalue()
    assert 'outcome=success' in out.getvalue()


def test_watch_pull_request_pins_number_despite_branch_change( monkeypatch ):
    monkeypatch.setattr(
        github_helpers, 'repository',
        lambda owner=None, repo=None: ( 'ja11sop', 'cuppa' ),
    )
    branches = [ 'show_pr_helper', 'download_progress' ]
    monkeypatch.setattr( github_helpers, 'current_branch', lambda: branches[0] )
    monkeypatch.setattr(
        github_helpers, 'resolve_pull_request',
        lambda **kwargs: { 'number': 166 },
    )

    polls = []

    def fake_status( **kwargs ):
        polls.append( kwargs.get( 'number' ) )
        # Simulate another agent checking out a different PR branch mid-watch.
        branches[0] = 'download_progress'
        return github_helpers.PullRequestStatus(
            number=kwargs['number'],
            url='https://example.com/pr/{}'.format( kwargs['number'] ),
            head_sha='abcdef01',
            state='open',
            mergeable_state='clean',
            checks=[ github_helpers.CheckRun( 'unit', 'completed', 'success', '' ) ],
            outcome='success',
        )

    monkeypatch.setattr( github_helpers, 'pull_request_status', fake_status )
    out = io.StringIO()
    code, last = github_helpers.watch_pull_request(
        interval=1,
        timeout=60,
        out=out,
        sleep=lambda seconds: None,
        clock=lambda: 0,
    )
    assert code == github_helpers.EXIT_SUCCESS
    assert last.number == 166
    assert polls == [ 166 ]


def test_watch_pull_request_times_out( monkeypatch ):
    monkeypatch.setattr(
        github_helpers, 'repository',
        lambda owner=None, repo=None: ( 'ja11sop', 'cuppa' ),
    )
    monkeypatch.setattr(
        github_helpers, 'pull_request_status',
        lambda **kwargs: github_helpers.PullRequestStatus(
            number=139,
            url='https://example.com/pr/139',
            head_sha='abcdef01',
            state='open',
            mergeable_state='unstable',
            checks=[ github_helpers.CheckRun( 'unit', 'queued', None, '' ) ],
            outcome='pending',
        ),
    )

    out = io.StringIO()
    now = [ 0 ]

    def clock():
        return now[0]

    def sleep( seconds ):
        now[0] += seconds

    code, last = github_helpers.watch_pull_request(
        number=139,
        interval=5,
        timeout=5,
        out=out,
        sleep=sleep,
        clock=clock,
    )

    assert code == github_helpers.EXIT_TIMEOUT
    assert last.outcome == 'pending'
    assert 'timed out' in out.getvalue()
