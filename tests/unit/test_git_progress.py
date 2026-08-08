#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io

import pytest

from cuppa.colourise import colouriser
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


def test_pump_git_progress_subdues_and_rewrites():
    was = colouriser.use_colour
    colouriser.enable()
    try:
        src = io.BytesIO( b'Receiving objects:  50% (1/2)\rReceiving objects: 100% (2/2)\n' )
        dest = io.StringIO()
        collected = []
        Git._pump_git_progress( src, dest, collected, rewrite=True )
        text = dest.getvalue()
        assert text.count( '\r' ) >= 1
        assert '\x1b[' in text  # subdued / dim sequence when colour is on
        assert 'Receiving objects:  50%' in collected[0]
        assert 'Receiving objects: 100%' in collected[1]
    finally:
        colouriser.use_colour = was


def test_pump_git_progress_ci_uses_newlines():
    src = io.BytesIO( b'Receiving objects:  50% (1/2)\rReceiving objects: 100% (2/2)\n' )
    dest = io.StringIO()
    collected = []
    Git._pump_git_progress( src, dest, collected, rewrite=False )
    text = dest.getvalue()
    assert '\r' not in text
    assert text.count( '\n' ) >= 2


def test_run_with_progress_pipes_stderr( monkeypatch ):
    calls = {}
    tty = io.StringIO()

    class FakeStdout( object ):
        def read( self ):
            return b'ok\n'

    class FakeStderr( object ):
        def read( self, size=-1 ):
            return b''

    class FakeProcess( object ):
        def __init__( self ):
            self.stdout = FakeStdout()
            self.stderr = FakeStderr()

        def wait( self ):
            return 0

    def fake_popen( args_list, **kwargs ):
        calls['args'] = list( args_list )
        calls['stdout'] = kwargs.get( 'stdout' )
        calls['stderr'] = kwargs.get( 'stderr' )
        return FakeProcess()

    monkeypatch.setattr(
            'cuppa.utility.download.open_progress_stream',
            lambda: ( tty, True, True ),
    )
    monkeypatch.setattr( 'cuppa.scms.git.subprocess.Popen', fake_popen )
    result = Git._run_with_progress( [ 'git', 'fetch', '--progress' ], path='/tmp/repo' )
    assert result == 'ok'
    assert calls['stdout'] is not None
    assert calls['stderr'] is not None
    assert calls['args'] == [ 'git', 'fetch', '--progress' ]
