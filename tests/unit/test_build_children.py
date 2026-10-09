#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os
import signal

import pytest

from cuppa.__main__ import run_scons
from cuppa.output_processor import IncrementalSubProcess
from cuppa.utility import build_children


pytestmark = pytest.mark.unit


class _Child( object ):

    def __init__( self, pid ):
        self.pid = pid


def test_the_first_ctrl_c_signals_children_and_the_second_hard_stops_them( monkeypatch ):
    """Delegates must learn about the first Ctrl-C; second is SIGTERM."""
    killed = []
    monkeypatch.setattr(
            build_children, "terminate_process_tree",
            lambda pid, sig=None: killed.append( ( pid, sig or signal.SIGTERM ) ),
    )
    build_children.reset_stop_requests()
    child = _Child( 42 )
    try:
        build_children.remember_child( child )
        assert build_children.note_stop_request() == 1
        assert build_children.stop_count() == 1
        if os.name != "nt":
            assert killed == [ ( 42, signal.SIGINT ) ]
        assert build_children.note_stop_request() == 2
        if os.name != "nt":
            assert killed == [ ( 42, signal.SIGINT ), ( 42, signal.SIGTERM ) ]
    finally:
        build_children.forget_child( child )
        build_children.reset_stop_requests()


def test_terminate_process_tree_signals_descendants( monkeypatch ):
    if os.name == "nt":
        pytest.skip( "POSIX process groups only" )
    import sys
    sent = []

    class _FakeChild( object ):
        def __init__( self, pid ):
            self.pid = pid

        def send_signal( self, sig ):
            sent.append( ( self.pid, sig ) )

    class _FakeProc( object ):
        def __init__( self, pid ):
            self.pid = pid

        def children( self, recursive=False ):
            assert recursive is True
            return [ _FakeChild( 7 ), _FakeChild( 8 ) ]

        def send_signal( self, sig ):
            sent.append( ( self.pid, sig ) )

    class _FakePsutil( object ):
        Error = type( "Error", ( Exception, ), {} )

        @staticmethod
        def Process( pid ):
            return _FakeProc( pid )

    monkeypatch.setitem( sys.modules, "psutil", _FakePsutil() )
    killed_pg = []
    monkeypatch.setattr(
            build_children.os, "killpg",
            lambda pid, sig: killed_pg.append( ( pid, sig ) ),
    )
    monkeypatch.setattr( build_children.os, "kill", lambda pid, sig: None )
    build_children.terminate_process_tree( 42, signal.SIGTERM )
    assert sent == [
            ( 8, signal.SIGTERM ),
            ( 7, signal.SIGTERM ),
            ( 42, signal.SIGTERM ),
    ]
    assert killed_pg == [ ( 42, signal.SIGTERM ) ]


def test_a_build_child_is_started_outside_the_terminal_session( monkeypatch ):
    seen = {}

    class _TextPipe( object ):
        def readline( self ):
            return ""

    class _Proc( object ):
        pid = 99
        stdout = _TextPipe()
        stderr = _TextPipe()
        returncode = 0

        def wait( self ):
            return 0

        def kill( self ):
            return None

    def fake_popen( args, **kwargs ):
        seen['kwargs'] = kwargs
        return _Proc()

    monkeypatch.setattr( "cuppa.output_processor.subprocess.Popen", fake_popen )
    code = IncrementalSubProcess.Popen2(
            lambda line: None, lambda line: None, [ "true" ], suppress_output=True,
    )
    assert code == 0
    if os.name != "nt":
        assert seen['kwargs']['start_new_session'] is True


class _Pipe( object ):

    def __init__( self, lines ):
        self._lines = list( lines )

    def readline( self ):
        if not self._lines:
            return b""
        item = self._lines.pop( 0 )
        if item is KeyboardInterrupt:
            raise KeyboardInterrupt
        return item


class _Scons( object ):

    def __init__( self, lines ):
        self.stdout = _Pipe( lines )
        self.stderr = _Pipe( [] )
        self.returncode = 2
        self.killed = False
        self.pid = 77

    def wait( self ):
        return self.returncode

    def poll( self ):
        return None

    def kill( self ):
        self.killed = True


def test_the_cuppa_wrapper_keeps_reading_after_the_first_ctrl_c( monkeypatch ):
    process = _Scons( [ KeyboardInterrupt, b"still going\n" ] )

    def fake_popen( args, **kwargs ):
        return process

    monkeypatch.setattr( "cuppa.__main__.subprocess.Popen", fake_popen )
    monkeypatch.setattr( "cuppa.__main__.inject_inventory_ignore_errors", lambda args: args )
    assert run_scons( [] ) == 2
    assert process.killed is False


def test_a_second_ctrl_c_in_the_wrapper_leaves_scons_to_abort_its_children( monkeypatch ):
    process = _Scons( [ KeyboardInterrupt, KeyboardInterrupt ] )

    def fake_popen( args, **kwargs ):
        return process

    monkeypatch.setattr( "cuppa.__main__.subprocess.Popen", fake_popen )
    monkeypatch.setattr( "cuppa.__main__.inject_inventory_ignore_errors", lambda args: args )
    assert run_scons( [] ) == 2
    assert process.killed is False


def test_jobs_returning_closes_a_quiet_interrupt( capsys ):
    """``-Q`` never writes ``scons: Build interrupted.`` The close still prints."""
    import sys

    import SCons.Taskmaster.Job as jobs

    from cuppa import progress

    saved_run = jobs.Jobs.run
    saved_setup = jobs.Jobs._setup_sig_handler
    saved_flag = build_children._handler_installed
    saved_out, saved_err = sys.stdout, sys.stderr
    build_children._handler_installed = False
    try:
        def quiet_run( self, postfunc=lambda: None ):
            if postfunc:
                postfunc()

        jobs.Jobs.run = quiet_run
        jobs.Jobs._setup_sig_handler = lambda self: None
        build_children.install_graceful_interrupt()
        progress.install_terse_interrupt_filter()

        progress.note_build_interrupted()
        capsys.readouterr()
        jobs.Jobs.run( object(), lambda: None )
        out = capsys.readouterr().out
        assert out.startswith( "stopped in-flight actions\n[interrupted]" )

        progress.reset_build_interrupted()
        progress.note_build_interrupted()
        progress.note_build_aborted()
        capsys.readouterr()
        jobs.Jobs.run( object(), lambda: None )
        assert capsys.readouterr().out == ""
    finally:
        jobs.Jobs.run = saved_run
        jobs.Jobs._setup_sig_handler = saved_setup
        build_children._handler_installed = saved_flag
        sys.stdout = saved_out
        sys.stderr = saved_err
        progress.reset_build_interrupted()


def test_a_third_ctrl_c_in_the_wrapper_stops_scons( monkeypatch ):
    process = _Scons( [ KeyboardInterrupt, KeyboardInterrupt, KeyboardInterrupt ] )

    def fake_popen( args, **kwargs ):
        return process

    monkeypatch.setattr( "cuppa.__main__.subprocess.Popen", fake_popen )
    monkeypatch.setattr( "cuppa.__main__.inject_inventory_ignore_errors", lambda args: args )
    assert run_scons( [] ) == 2
    assert process.killed is True
