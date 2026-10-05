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
from cuppa.output_processor import strip_ansi
from cuppa.utility import heartbeat as hb
from cuppa.utility.console_report import write_report_lines
from cuppa.utility.storage import visible_len


pytestmark = pytest.mark.unit


class FakeClock( object ):
    def __init__( self, start=1000.0 ):
        self.now = start

    def __call__( self ):
        return self.now

    def advance( self, seconds ):
        self.now += seconds


def _configure( stream, clock, columns=120, style=None ):
    hb.configure_quiet_console(
            'warn',
            stream=stream,
            is_tty=True,
            owns_stream=False,
            clock=clock,
            columns=columns,
            pulse=False,
            style=style,
    )


def _status_body( stream ):
    """Last CR-separated status fragment, ANSI stripped, trailing pad removed."""
    return strip_ansi( stream.getvalue().split( '\r' )[-1] ).rstrip( ' ' )


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
    _configure( stream, clock )
    assert hb.quiet_console() is True
    assert hb.diverting() is True
    assert logger.isEnabledFor( logging.INFO )

    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in stream.getvalue()
    assert 'working' in _status_body( stream )

    from cuppa.progress import _write_terse_stdout
    import cuppa.progress as progress_module
    out = io.StringIO()
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


def test_working_prefix_and_pulse_on_status_line():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=80 )
    logger.info( 'Updating [libfoo]' )
    body = _status_body( stream )
    assert body.startswith( 'working ' )
    pulse = body[ len( 'working ' ): len( 'working ' ) + hb._PULSE_WIDTH ]
    assert pulse in hb._PULSE_FRAMES
    # Two spaces separate the widget from the caption.
    assert body[ len( 'working ' ) + hb._PULSE_WIDTH: len( 'working ' ) + hb._PULSE_WIDTH + 2 ] == '  '
    assert 'Updating [libfoo]' in body


def test_spinner_style_uses_ascii_spinner():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=80, style='spinner' )
    assert hb.style() == 'spinner'
    logger.info( 'Updating [libfoo]' )
    body = _status_body( stream )
    assert body.startswith( 'working ' )
    assert body[ len( 'working ' ) ] in hb._SPINNER
    assert body[ len( 'working ' ) + 1: len( 'working ' ) + 3 ] == '  '
    assert 'Updating [libfoo]' in body


def test_pulse_frames_are_bordered_ecg_cycle():
    assert hb._PULSE_WIDTH == 11
    assert all( len( f ) == hb._PULSE_WIDTH for f in hb._PULSE_FRAMES )
    assert all( f.startswith( '|' ) and f.endswith( '|' ) for f in hb._PULSE_FRAMES )
    # Cycle opens on rest so the first paint is not mid-beat.
    assert hb._pulse_frame( 0 ) == hb._PULSE_REST
    assert hb._PULSE_FRAMES[: hb._PULSE_REST_HOLD ] == ( hb._PULSE_REST, ) * hb._PULSE_REST_HOLD
    assert hb._pulse_frame( hb._PULSE_REST_HOLD ) == '|•--------|'
    assert hb._pulse_frame( hb._PULSE_REST_HOLD + 5 ) == '|---√\\/---|'
    assert hb._PULSE_FRAMES.count( hb._PULSE_REST ) == hb._PULSE_REST_HOLD
    assert hb._pulse_frame( len( hb._PULSE_FRAMES ) ) == hb._pulse_frame( 0 )


def test_pulse_rest_tick_is_slower_than_beat():
    hb._spin = 0
    assert hb._pulse_frame( hb._spin ) == hb._PULSE_REST
    assert hb._next_pulse_interval() == hb._PULSE_REST_INTERVAL_S
    hb._spin = hb._PULSE_REST_HOLD
    assert hb._pulse_frame( hb._spin ).startswith( '|•' )
    assert hb._next_pulse_interval() == hb._PULSE_INTERVAL_S


def test_style_pulse_uses_hospital_green_for_qrs():
    from cuppa.colourise import colouriser
    import colorama
    was = colouriser.use_colour
    colouriser.enable()
    try:
        styled = hb._style_pulse( '|---√\\/---|' )
        assert '√' in styled
        assert colorama.Fore.GREEN in styled
        # Hot and subdued spans are separate SGR regions.
        assert styled.count( '\x1b[' ) >= 2
    finally:
        colouriser.use_colour = was


def test_normalize_style_accepts_pulse_and_spinner():
    assert hb.normalize_style( None ) == 'pulse'
    assert hb.normalize_style( 'Spinner' ) == 'spinner'
    assert hb.normalize_style( [ 'pulse' ] ) == 'pulse'
    with pytest.raises( ValueError ):
        hb.normalize_style( 'ecg' )


def test_long_info_stays_on_one_physical_line():
    """``\\r`` cannot clear a wrapped line — never write past the terminal width."""
    stream = io.StringIO()
    clock = FakeClock()
    cols = 40
    _configure( stream, clock, columns=cols )
    long_msg = (
            'Updating [git+ssh://git@example.com/org/very_long_repo_name@master] '
            'in [/home/jamie/_cuppa/_download/git_ssh_…/] on '
            "<RevOptions git: rev='master'> at [master rev. abcdef]"
    )
    assert len( long_msg ) > cols
    logger.info( long_msg )
    body = _status_body( stream )
    assert visible_len( body ) <= cols
    assert body.startswith( 'working ' )
    assert body.endswith( hb._ELLIPSIS )

    clock.advance( 0.15 )
    logger.info( 'Using package [tip]' )
    body2 = _status_body( stream )
    assert visible_len( body2 ) <= cols
    assert 'Using package [tip]' in body2
    # Previous long tail must not remain after the rewrite.
    assert 'very_long_repo_name' not in body2


def test_terminal_columns_prefer_stream_fileno( monkeypatch ):
    """Piped stdout makes ``shutil.get_terminal_size`` lie; use the TTY fd."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )  # columns override set — clear it to exercise fd path
    hb._columns = None

    class Size( object ):
        columns = 160
        lines = 40

    monkeypatch.setattr( stream, 'fileno', lambda: 99 )
    monkeypatch.setattr( hb.os, 'get_terminal_size', lambda fd: Size() )
    assert hb._terminal_columns() == 160


def test_info_rewrites_throttled_status_line():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )

    assert hb.diverting() is True
    assert logger.isEnabledFor( logging.INFO )
    assert hb.multi_line_progress_allowed() is False

    logger.info( 'Updating [libfoo]' )
    first = stream.getvalue()
    assert 'Updating [libfoo]' in first
    assert '\r' in first
    assert 'cuppa:' not in first
    assert '[info]' not in first
    assert 'working' in first

    logger.info( 'Using package [a]' )  # within throttle window
    assert stream.getvalue() == first

    clock.advance( 0.15 )
    logger.info( 'Using package [b]' )
    assert 'Using package [b]' in stream.getvalue()


def test_stale_caption_drops_to_working_pulse_anchor():
    """Last INFO is context, not truth — age it out; keep working + pulse."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    logger.info( 'Using [/tmp] for dependencies' )
    assert 'Using [/tmp]' in _status_body( stream )

    # Still held before five message periods elapse.
    clock.advance( hb._MESSAGE_HOLD_S - 0.01 )
    hb._on_pulse()
    assert 'Using [/tmp]' in _status_body( stream )

    clock.advance( 0.02 )
    hb._on_pulse()
    body = _status_body( stream )
    assert body.startswith( 'working ' )
    pulse = body[ len( 'working ' ): len( 'working ' ) + hb._PULSE_WIDTH ]
    assert pulse in hb._PULSE_FRAMES
    assert 'Using [/tmp]' not in body
    assert hb._body == ''

    # A newer INFO always replaces the caption immediately.
    clock.advance( 0.15 )
    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in _status_body( stream )


def test_warn_clears_status_and_emits_multiline( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    capture = io.StringIO()
    monkeypatch.setattr( log_mod._log_handler, 'stream', capture )

    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in stream.getvalue()

    logger.warn( 'something went wrong' )
    assert '\r' in stream.getvalue()
    text = capture.getvalue()
    assert 'something went wrong' in text
    assert '[warn]' in text or '[WARNING]' in text


def test_silent_quiet_suppresses_warn_multiline( monkeypatch ):
    stream = io.StringIO()
    hb.configure_quiet_console(
            'error', stream=stream, is_tty=True, owns_stream=False, pulse=False,
    )
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
    _configure( stream, clock )
    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in stream.getvalue()

    out = io.StringIO()
    write_report_lines( [ 'Running in CASCADE PLAN mode' ], out=out )
    assert out.getvalue() == 'Running in CASCADE PLAN mode\n'
    assert stream.getvalue().endswith( '\r' ) or ' ' in stream.getvalue()


def test_spawn_suppress_clears_in_place_and_defers_redraw():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Using [/tmp] for dependencies' )
    assert 'Using [/tmp]' in _status_body( stream )
    assert hb._last_line

    before_suppress = stream.getvalue()
    hb.suppress()
    assert hb._last_line == ''
    assert hb._suppress_depth == 1
    # In-place erase so the next stdout line reuses the status row.
    added = stream.getvalue()[ len( before_suppress ): ]
    assert '\n' not in added
    assert added.endswith( hb._WRAP_ON )
    # INFO during a spawn is remembered, not drawn.
    before = stream.getvalue()
    logger.info( 'Updating [libfoo] during spawn' )
    assert stream.getvalue() == before
    assert hb._pending == 'Updating [libfoo] during spawn'

    hb.allow()
    assert hb._suppress_depth == 0
    # allow() must not redraw — launcher may still be flushing the command.
    assert stream.getvalue() == before
    clock.advance( 0.15 )
    logger.info( 'Updating [libfoo] during spawn' )
    assert 'Updating [libfoo] during spawn' in _status_body( stream )


def test_reveal_before_print_cmd_line_reuses_status_row():
    """PRINT_CMD_LINE clears working in place; SPAWN must not insert a newline."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Using [/tmp] for dependencies' )
    assert 'Using [/tmp]' in _status_body( stream )
    before_reveal = stream.getvalue()

    from cuppa.progress import heartbeat_print_cmd_line
    import cuppa.progress as progress_module
    out = io.StringIO()
    real_stdout = progress_module.sys.stdout
    progress_module.sys.stdout = out
    try:
        heartbeat_print_cmd_line( '/usr/bin/g++ -c foo.cpp', [], [], {} )
    finally:
        progress_module.sys.stdout = real_stdout

    assert out.getvalue() == '/usr/bin/g++ -c foo.cpp\n'
    assert hb._last_line == ''
    revealed = stream.getvalue()[ len( before_reveal ): ]
    assert '\n' not in revealed
    after_reveal = stream.getvalue()

    hb.suppress( advance=False )
    assert hb._suppress_depth == 1
    added = stream.getvalue()[ len( after_reveal ): ]
    assert '\n' not in added
    hb.allow()

    # No status visible → reveal is a no-op between commands.
    before_second = stream.getvalue()
    progress_module.sys.stdout = out
    try:
        heartbeat_print_cmd_line( '/usr/bin/g++ -c bar.cpp', [], [], {} )
    finally:
        progress_module.sys.stdout = real_stdout
    assert stream.getvalue() == before_second
    assert out.getvalue().endswith( '/usr/bin/g++ -c bar.cpp\n' )


def test_spawn_transcript_clears_heartbeat( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Using [/tmp] for dependencies' )
    assert hb._last_line

    from cuppa import output_processor as op
    printed = []
    monkeypatch.setattr(
            'builtins.print',
            lambda *a, **k: printed.append( a[0] if a else '' ),
    )
    op._emit_transcript( '/usr/bin/g++ -c foo.cpp' )
    assert printed == [ '/usr/bin/g++ -c foo.cpp' ]
    assert hb._last_line == ''
    assert hb._body is None


def test_verbosity_override_resets_heartbeat():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    assert hb.diverting() is True
    hb.reset()
    set_logging_level( 'info' )
    assert hb.diverting() is False
    assert hb.multi_line_progress_allowed() is True
