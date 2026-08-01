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


def test_repository_falls_back_when_git_is_unavailable( monkeypatch ):
    def fail( *args ):
        raise github_helpers.GitHubHelperError( 'no git' )
    monkeypatch.setattr( github_helpers, '_run_git', fail )
    assert github_helpers.repository() == ( 'ja11sop', 'cuppa' )


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
    monkeypatch.setattr(
        github_helpers, 'pull_request_status',
        lambda **kwargs: states.pop( 0 ),
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
    assert sleeps == [ 1 ]
    assert 'outcome=pending' in out.getvalue()
    assert 'outcome=success' in out.getvalue()


def test_watch_pull_request_times_out( monkeypatch ):
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
