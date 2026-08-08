#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.scms.git import Git


pytestmark = pytest.mark.unit


def test_clone_uses_progress_runner( monkeypatch, tmp_path ):
    seen = {}

    def fake_run( args_list, path=None ):
        seen['args'] = list( args_list )
        seen['path'] = path
        return ''

    monkeypatch.setattr( Git, '_run_with_progress', fake_run )
    dest = tmp_path / 'repo'
    Git.clone( 'https://example.com/org/widget.git', str( dest ), branch='main' )
    assert seen['args'][:3] == [ 'git', 'clone', '--progress' ]
    assert '--branch' in seen['args']
    assert 'main' in seen['args']
    assert str( dest ) in seen['args']


def test_fetch_uses_progress_runner( monkeypatch, tmp_path ):
    seen = {}

    def fake_run( args_list, path=None ):
        seen['args'] = list( args_list )
        seen['path'] = path
        return ''

    monkeypatch.setattr( Git, '_run_with_progress', fake_run )
    Git.fetch( str( tmp_path ) )
    assert seen['args'] == [ 'git', 'fetch', '--progress' ]
    assert seen['path'] == str( tmp_path )


def test_run_with_progress_tty_uses_controlling_terminal( monkeypatch ):
    import io

    calls = {}
    tty = io.StringIO()

    class FakeProcess( object ):
        def __init__( self ):
            self.stdout = io.StringIO( 'ok\n' )

        def wait( self ):
            return 0

    def fake_popen( args_list, **kwargs ):
        calls['args'] = list( args_list )
        calls['stderr'] = kwargs.get( 'stderr' )
        return FakeProcess()

    monkeypatch.setattr(
            'cuppa.utility.download.open_progress_stream',
            lambda: ( tty, True, True ),
    )
    monkeypatch.setattr( 'cuppa.scms.git.subprocess.Popen', fake_popen )
    result = Git._run_with_progress( [ 'git', 'fetch', '--progress' ], path='/tmp/repo' )
    assert result == 'ok'
    assert calls['stderr'] is tty
    assert calls['args'] == [ 'git', 'fetch', '--progress' ]
