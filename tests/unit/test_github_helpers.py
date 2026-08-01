import pytest

from scripts import github_helpers


pytestmark = pytest.mark.unit


class FakeGitHub( object ):

    def __init__( self ):
        self.calls = []

    def request( self, method, path, payload=None ):
        self.calls.append( ( method, path, payload ) )
        if path.endswith( '/pulls' ):
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
