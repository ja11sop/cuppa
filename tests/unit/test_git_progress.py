#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io
import logging

import pytest

from cuppa.colourise import colouriser
from cuppa.log import logger
from cuppa.scms.git import Git


pytestmark = pytest.mark.unit


def test_clone_uses_progress_runner( monkeypatch, tmp_path ):
    seen = {}

    def fake_run( args_list, path=None, **kwargs ):
        seen['args'] = list( args_list )
        seen['path'] = path
        return ''

    monkeypatch.setattr( Git, '_progress_enabled', classmethod( lambda cls: True ) )
    monkeypatch.setattr( Git, '_run_with_progress', fake_run )
    dest = tmp_path / 'repo'
    Git.clone( 'https://example.com/org/widget.git', str( dest ), branch='main' )
    assert seen['args'][:3] == [ 'git', 'clone', '--progress' ]
    assert '--branch' in seen['args']
    assert 'main' in seen['args']
    assert str( dest ) in seen['args']


def test_fetch_uses_progress_runner( monkeypatch, tmp_path ):
    seen = {}

    def fake_run( args_list, path=None, **kwargs ):
        seen['args'] = list( args_list )
        seen['path'] = path
        seen['kwargs'] = kwargs
        return ''

    monkeypatch.setattr( Git, '_progress_enabled', classmethod( lambda cls: True ) )
    monkeypatch.setattr( Git, '_run_with_progress', fake_run )
    Git.fetch( str( tmp_path ) )
    assert seen['args'] == [ 'git', 'fetch', '--progress' ]
    assert seen['path'] == str( tmp_path )


def test_fetch_passes_status_line_options( monkeypatch, tmp_path ):
    seen = {}

    def fake_run( args_list, path=None, **kwargs ):
        seen['kwargs'] = kwargs
        return ''

    monkeypatch.setattr( Git, '_progress_enabled', classmethod( lambda cls: True ) )
    monkeypatch.setattr( Git, '_run_with_progress', fake_run )
    stream = object()
    Git.fetch(
            str( tmp_path ), progress=True, line_prefix='Fetching [w] (1/2) · ',
            progress_stream=stream,
    )
    assert seen['kwargs']['line_prefix'] == 'Fetching [w] (1/2) · '
    assert seen['kwargs']['progress_stream'] is stream
    assert seen['kwargs']['single_line'] is True
    assert seen['kwargs']['owns_stream'] is False


def test_clone_skips_progress_when_quiet( monkeypatch, tmp_path ):
    seen = {}

    def fake_execute( command, path=None ):
        seen['command'] = command
        seen['path'] = path
        return ''

    def boom( *args, **kwargs ):
        raise AssertionError( '_run_with_progress should not run when quiet' )

    monkeypatch.setattr( Git, '_progress_enabled', classmethod( lambda cls: False ) )
    monkeypatch.setattr( Git, 'execute_command', fake_execute )
    monkeypatch.setattr( Git, '_run_with_progress', boom )
    dest = tmp_path / 'repo'
    Git.clone( 'https://example.com/org/widget.git', str( dest ), branch='main' )
    assert seen['command'].startswith( 'git clone' )
    assert '--progress' not in seen['command']
    assert '--branch' in seen['command']
    assert 'main' in seen['command']


def test_fetch_skips_progress_when_quiet( monkeypatch, tmp_path ):
    seen = {}

    def fake_execute( command, path=None ):
        seen['command'] = command
        seen['path'] = path
        return ''

    def boom( *args, **kwargs ):
        raise AssertionError( '_run_with_progress should not run when quiet' )

    monkeypatch.setattr( Git, '_progress_enabled', classmethod( lambda cls: False ) )
    monkeypatch.setattr( Git, 'execute_command', fake_execute )
    monkeypatch.setattr( Git, '_run_with_progress', boom )
    Git.fetch( str( tmp_path ) )
    assert seen['command'] == 'git fetch'
    assert seen['path'] == str( tmp_path )


def test_progress_enabled_follows_logger_level():
    was = logger.level
    try:
        logger.setLevel( logging.INFO )
        assert Git._progress_enabled()
        logger.setLevel( logging.WARNING )
        assert not Git._progress_enabled()
    finally:
        logger.setLevel( was )


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


def test_pump_git_progress_single_line_keeps_prefix():
    was = colouriser.use_colour
    colouriser.enable()
    try:
        src = io.BytesIO( b'Receiving objects:  50%\rReceiving objects: 100%\n' )
        dest = io.StringIO()
        collected = []
        Git._pump_git_progress(
                src, dest, collected, rewrite=True,
                line_prefix='Fetching [widget] (1/2) · ', single_line=True,
        )
        text = dest.getvalue()
        assert '\n' not in text
        assert text.count( '\r' ) >= 2
        assert 'Fetching [widget] (1/2) · Receiving objects:  50%' in text
        assert 'Fetching [widget] (1/2) · Receiving objects: 100%' in text
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


def test_is_tags_fetch_failure_matches_quiet_and_clobber():
    assert Git.is_tags_fetch_failure( "git fetch --tags -q exited with 1" )
    assert Git.is_tags_fetch_failure(
            "git fetch --tags exited with 1: would clobber existing tag"
    )
    assert not Git.is_tags_fetch_failure( "git fetch exited with 1" )
    assert not Git.is_tags_fetch_failure( "network unreachable" )


def test_fetch_tags_force_is_quiet_by_default( monkeypatch, tmp_path ):
    seen = {}

    def fake_execute( command, path=None ):
        seen['command'] = command
        seen['path'] = path
        return ''

    def boom( *args, **kwargs ):
        raise AssertionError( '_run_with_progress should not run when quiet' )

    monkeypatch.setattr( Git, 'execute_command', fake_execute )
    monkeypatch.setattr( Git, '_run_with_progress', boom )
    Git.fetch_tags_force( str( tmp_path ) )
    assert seen['command'] == 'git fetch --tags --force'
    assert seen['path'] == str( tmp_path )


def test_fetch_tags_force_uses_progress_when_requested( monkeypatch, tmp_path ):
    seen = {}

    def fake_run( args_list, path=None, **kwargs ):
        seen['args'] = list( args_list )
        seen['path'] = path
        return ''

    def boom( *args, **kwargs ):
        raise AssertionError( 'quiet execute_command should not run' )

    monkeypatch.setattr( Git, '_run_with_progress', fake_run )
    monkeypatch.setattr( Git, 'execute_command', boom )
    Git.fetch_tags_force( str( tmp_path ), progress=True )
    assert seen['args'] == [ 'git', 'fetch', '--tags', '--force', '--progress' ]
    assert seen['path'] == str( tmp_path )
