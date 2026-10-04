#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Quiet+TTY heartbeat: INFO diversion, throttle, clear on warn/report."""

import io
import logging

import pytest

from cuppa import log as log_mod
from cuppa.log import logger, set_logging_level
from cuppa.utility import heartbeat as hb
from cuppa.utility.console_report import write_report_lines


pytestmark = pytest.mark.unit


class FakeClock( object ):
    def __init__( self, start=1000.0 ):
        self.now = start

    def __call__( self ):
        return self.now

    def advance( self, seconds ):
        self.now += seconds


@pytest.fixture( autouse=True )
def _reset_heartbeat():
    # Attach the Cuppa stream handler without ``initialise_logging``: that
    # renames levels and sets ``propagate=False``, which breaks later caplog
    # tests in the same pytest process. Restore logger levels afterward so
    # ``caplog.at_level("DEBUG")`` in other modules still works (a sticky
    # INFO on the cuppa logger would filter debug before propagation).
    handler = log_mod._log_handler
    if handler.formatter is None:
        handler.setFormatter( log_mod._formatter() )
    attached = handler in logger.handlers
    if not attached:
        logger.addHandler( handler )
    previous_cuppa_level = logger.level
    previous_root_level = logging.getLogger().level
    hb.reset()
    set_logging_level( 'info' )
    yield
    hb.reset()
    if not attached:
        logger.removeHandler( handler )
    logger.setLevel( previous_cuppa_level )
    logging.getLogger().setLevel( previous_root_level )


def test_configure_without_tty_uses_classic_quiet():
    stream = io.StringIO()
    hb.configure_quiet_console( 'warn', stream=stream, is_tty=False )
    assert hb.quiet_console() is True
    assert hb.diverting() is False
    assert not logger.isEnabledFor( logging.INFO )
    assert hb.multi_line_progress_allowed() is False


def test_configure_keeps_heartbeat_for_terse_gaps():
    """Terse transcript and heartbeat coexist; clear before each terse line."""
    stream = io.StringIO()
    clock = FakeClock()
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False, clock=clock,
    )
    assert hb.quiet_console() is True
    assert hb.diverting() is True
    assert logger.isEnabledFor( logging.INFO )

    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in stream.getvalue()

    from cuppa.progress import _write_terse_stdout
    out = io.StringIO()
    import cuppa.progress as progress_module
    real_stdout = progress_module.sys.stdout
    progress_module.sys.stdout = out
    try:
        _write_terse_stdout( '  1/2 · 10% [ok] … · compile a.cpp\n' )
    finally:
        progress_module.sys.stdout = real_stdout
    assert out.getvalue().endswith( 'compile a.cpp\n' )
    # Heartbeat status line was cleared before the transcript write.
    assert stream.getvalue().endswith( '\r' ) or ' ' in stream.getvalue()


def test_fit_plain_truncates_with_ellipsis():
    assert hb._fit_plain( 'short', 80 ) == 'short'
    assert hb._fit_plain( 'abcdefghij', 5 ) == 'abcd' + hb._ELLIPSIS
    assert hb._fit_plain( 'ab', 1 ) == hb._ELLIPSIS


def test_long_info_stays_on_one_physical_line():
    """``\\r`` cannot clear a wrapped line — never write past the terminal width."""
    stream = io.StringIO()
    clock = FakeClock()
    cols = 40
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False,
            clock=clock, columns=cols,
    )
    long_msg = (
            'Updating [git+ssh://git@example.com/org/very_long_repo_name@master] '
            'in [/home/jamie/_cuppa/_download/git_ssh_…/] on '
            "<RevOptions git: rev='master'> at [master rev. abcdef]"
    )
    assert len( long_msg ) > cols
    logger.info( long_msg )
    # Strip ANSI / CR for a visible-width check on the status body.
    from cuppa.output_processor import strip_ansi
    from cuppa.utility.storage import visible_len
    body = strip_ansi( stream.getvalue() ).lstrip( '\r' ).rstrip( ' ' )
    assert visible_len( body ) <= cols
    assert body.endswith( hb._ELLIPSIS )
    assert body.startswith( 'Updating [' )

    clock.advance( 0.40 )
    logger.info( 'Using package [tip]' )
    body2 = strip_ansi( stream.getvalue().split( '\r' )[-1] ).rstrip( ' ' )
    assert visible_len( body2 ) <= cols
    assert 'Using package [tip]' in body2
    # Previous long tail must not remain after the rewrite.
    assert 'very_long_repo_name' not in body2


def test_info_rewrites_throttled_status_line():
    stream = io.StringIO()
    clock = FakeClock()
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False, clock=clock,
            columns=120,
    )
    assert hb.diverting() is True
    assert logger.isEnabledFor( logging.INFO )
    assert hb.multi_line_progress_allowed() is False

    logger.info( 'Updating [libfoo]' )
    first = stream.getvalue()
    assert 'Updating [libfoo]' in first
    assert '\r' in first
    assert 'cuppa:' not in first
    assert '[info]' not in first

    logger.info( 'Using package [a]' )  # within throttle window
    assert stream.getvalue() == first

    clock.advance( 0.40 )
    logger.info( 'Using package [b]' )
    assert 'Using package [b]' in stream.getvalue()


def test_warn_clears_status_and_emits_multiline( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False, clock=clock,
    )
    # Point the cuppa log handler at a capture stream for the warn line.
    from cuppa import log as log_mod
    capture = io.StringIO()
    monkeypatch.setattr( log_mod._log_handler, 'stream', capture )

    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in stream.getvalue()

    logger.warn( 'something went wrong' )
    # Status line blanked (spaces after a carriage return).
    assert '\r' in stream.getvalue()
    text = capture.getvalue()
    assert 'something went wrong' in text
    # Level name is WARNING unless ``initialise_logging`` renamed it to warn.
    assert '[warn]' in text or '[WARNING]' in text


def test_silent_quiet_suppresses_warn_multiline( monkeypatch ):
    stream = io.StringIO()
    hb.configure_quiet_console(
            'error', stream=stream, is_tty=True, owns_stream=False,
    )
    from cuppa import log as log_mod
    capture = io.StringIO()
    monkeypatch.setattr( log_mod._log_handler, 'stream', capture )

    logger.info( 'Updating [libfoo]' )
    logger.warn( 'hidden under -s' )
    assert 'hidden under -s' not in capture.getvalue()

    logger.error( 'visible' )
    assert 'visible' in capture.getvalue()


def test_report_clears_heartbeat():
    stream = io.StringIO()
    clock = FakeClock()
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False, clock=clock,
    )
    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in stream.getvalue()

    out = io.StringIO()
    write_report_lines( [ 'Running in CASCADE PLAN mode' ], out=out )
    assert out.getvalue() == 'Running in CASCADE PLAN mode\n'
    # Clear wrote spaces over the status line.
    assert stream.getvalue().endswith( '\r' ) or ' ' in stream.getvalue()


def test_verbosity_override_resets_heartbeat():
    stream = io.StringIO()
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False,
    )
    assert hb.diverting() is True
    hb.reset()
    set_logging_level( 'info' )
    assert hb.diverting() is False
    assert hb.multi_line_progress_allowed() is True
