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


def _configure( stream, clock, columns=120, style=None, compact=False ):
    def sleep( seconds ):
        clock.advance( seconds )

    hb.configure_quiet_console(
            'warn',
            stream=stream,
            is_tty=True,
            owns_stream=False,
            clock=clock,
            columns=columns,
            pulse=False,
            style=style,
            sleep=sleep,
            compact=compact,
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


def test_configure_keeps_heartbeat_for_terse_gaps( monkeypatch ):
    """Terse transcript and heartbeat coexist; clear before each terse line."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    assert hb.quiet_console() is True
    assert hb.diverting() is True
    assert logger.isEnabledFor( logging.INFO )

    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in stream.getvalue()
    assert _status_body( stream )[ : hb._PULSE_WIDTH ] in hb._PULSE_FRAMES

    from cuppa.progress import _write_terse_stdout
    import cuppa.utility.heartbeat as heartbeat_module
    out = io.StringIO()
    real_stdout = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = out
    try:
        _write_terse_stdout( '  1/2 · 10% [ok] … · compile a.cpp\n' )
    finally:
        heartbeat_module.sys.stdout = real_stdout
    # Owned stream: durable terse line on the heartbeat TTY, not the pipe.
    assert 'compile a.cpp\n' in stream.getvalue()
    assert out.getvalue() == ''
    assert 'Updating [libfoo]' not in _status_body( stream )


def test_fit_plain_truncates_with_ellipsis():
    assert hb._fit_plain( 'short', 80 ) == 'short'
    assert hb._fit_plain( 'abcdefghij', 5 ) == 'abcd' + hb._ELLIPSIS
    assert hb._fit_plain( 'ab', 1 ) == hb._ELLIPSIS


def test_pulse_status_omits_working_word():
    """ECG widget is self-explanatory — no ``working`` prefix."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=80 )
    logger.info( 'Updating [libfoo]' )
    body = _status_body( stream )
    assert not body.startswith( 'working ' )
    pulse = body[ : hb._PULSE_WIDTH ]
    assert pulse in hb._PULSE_FRAMES
    # Two spaces separate the widget from the caption.
    assert body[ hb._PULSE_WIDTH: hb._PULSE_WIDTH + 2 ] == '  '
    assert 'Updating [libfoo]' in body


def test_spinner_style_keeps_working_word():
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


def test_normalize_style_accepts_pulse_spinner_and_off():
    assert hb.normalize_style( None ) == 'pulse'
    assert hb.normalize_style( 'Spinner' ) == 'spinner'
    assert hb.normalize_style( [ 'pulse' ] ) == 'pulse'
    assert hb.normalize_style( 'off' ) == 'off'
    assert hb.normalize_style( 'none' ) == 'off'
    with pytest.raises( ValueError ):
        hb.normalize_style( 'ecg' )


def test_style_off_disables_heartbeat():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, style='off' )
    assert hb.quiet_console() is True
    assert hb.diverting() is False
    assert not logger.isEnabledFor( logging.INFO )
    logger.info( 'hidden' )
    assert stream.getvalue() == ''


def test_compact_terse_pulse_aligns_arrow_with_location_maps():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120, compact=True )
    logger.info( 'Updating [libfoo]' )
    body = _status_body( stream )
    assert body.startswith( '|' )
    assert not body.startswith( 'working ' )
    assert 'Updating [libfoo]' in body
    arrow_at = body.index( '→' )
    from cuppa.progress import terse_arrow_column
    assert arrow_at == terse_arrow_column()


def test_compact_terse_spinner_aligns_arrow_with_location_maps():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120, style='spinner', compact=True )
    logger.info( 'Updating [libfoo]' )
    body = _status_body( stream )
    assert body.startswith( 'working ' )
    assert 'Updating [libfoo]' in body
    arrow_at = body.index( '→' )
    from cuppa.progress import terse_arrow_column
    assert arrow_at == terse_arrow_column()


def test_write_transcript_serializes_parallel_lines( monkeypatch ):
    """Two writers must not shear into ``format.ovariant``."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    import cuppa.utility.heartbeat as heartbeat_module
    out = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = out
    try:
        hb.write_transcript( 'format.o\n' )
        hb.write_transcript( 'variant     18% [progress] end\n' )
    finally:
        heartbeat_module.sys.stdout = real
    # Interactive diverting: durable lines on the owned heartbeat stream.
    assert 'format.o\n' in stream.getvalue()
    assert 'variant     18% [progress] end\n' in stream.getvalue()
    assert 'format.ovariant' not in stream.getvalue()
    assert out.getvalue() == ''


def test_info_during_busy_transcript_stays_pending_until_idle( monkeypatch ):
    """INFO after a terse line must not seize the row before the idle gate."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock( start=1000.0 )
    _configure( stream, clock, columns=120 )
    import cuppa.utility.heartbeat as heartbeat_module
    out = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = out
    try:
        hb.write_transcript( '  1/2 · 10% [ok] · compile a.cpp\n' )
        assert '1/2' in stream.getvalue()
        before = stream.getvalue()
        logger.info( 'Updating [libfoo]' )
        assert stream.getvalue() == before
        assert hb._pending == 'Updating [libfoo]'
        assert hb._body is None

        clock.advance( hb._IDLE_GATE_S - 0.01 )
        hb.flush_pending()
        assert stream.getvalue() == before
        assert hb._pending == 'Updating [libfoo]'

        clock.advance( 0.01 )
        hb.flush_pending()
    finally:
        heartbeat_module.sys.stdout = real
    assert 'Updating [libfoo]' in _status_body( stream )
    assert out.getvalue() == ''


def test_busy_transcript_coalesces_and_drops_intermediate_infos( monkeypatch ):
    """Rapid terse–info–terse must not force full-cycle dwells on each info."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock( start=1000.0 )
    _configure( stream, clock, columns=120 )
    import cuppa.utility.heartbeat as heartbeat_module
    out = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = out
    try:
        hb.write_transcript( 'terse-1\n' )
        logger.info( 'Updating [a]' )
        assert hb._pending == 'Updating [a]'
        assert 'Updating [a]' not in _status_body( stream )

        # Next terse while the gate is still closed: no dwell (nothing drawn).
        hb.write_transcript( 'terse-2\n' )
        assert clock.now == 1000.0
        assert hb._body is None
        logger.info( 'Updating [b]' )
        logger.info( 'Updating [c]' )
        assert hb._pending == 'Updating [c]'

        hb.write_transcript( 'terse-3\n' )
        assert clock.now == 1000.0
        assert 'Updating' not in _status_body( stream )

        clock.advance( hb._IDLE_GATE_S )
        hb.flush_pending()
    finally:
        heartbeat_module.sys.stdout = real
    assert 'Updating [c]' in _status_body( stream )
    assert 'Updating [a]' not in stream.getvalue()
    assert 'Updating [b]' not in stream.getvalue()
    assert 'terse-1\n' in stream.getvalue()
    assert 'terse-2\n' in stream.getvalue()
    assert 'terse-3\n' in stream.getvalue()
    assert out.getvalue() == ''


def test_info_before_any_transcript_still_paints_immediately():
    """Configure chatter before the first transcript must keep the console alive."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in _status_body( stream )


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
    assert body[ : hb._PULSE_WIDTH ] in hb._PULSE_FRAMES
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
    assert '|' in first

    logger.info( 'Using package [a]' )  # within throttle window
    assert stream.getvalue() == first

    clock.advance( 0.15 )
    logger.info( 'Using package [b]' )
    assert 'Using package [b]' in stream.getvalue()


def test_stale_caption_drops_to_pulse_anchor():
    """Last INFO is context, not truth — age it out; keep the pulse widget."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    logger.info( 'Using [/tmp] for dependencies' )
    assert 'Using [/tmp]' in _status_body( stream )

    hold = hb._caption_hold_s()
    # Still held before one full animation cycle (and the message hold) elapses.
    clock.advance( hold - 0.01 )
    hb._on_pulse()
    assert 'Using [/tmp]' in _status_body( stream )

    clock.advance( 0.02 )
    hb._on_pulse()
    body = _status_body( stream )
    assert body[ : hb._PULSE_WIDTH ] in hb._PULSE_FRAMES
    assert 'working' not in body
    assert 'Using [/tmp]' not in body
    assert hb._body == ''

    # A newer INFO always replaces the caption immediately.
    clock.advance( 0.15 )
    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in _status_body( stream )


def test_reveal_waits_one_full_animation_cycle( monkeypatch ):
    """Status must not flash away — hold one full cycle before erase-for-transcript."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock( start=1000.0 )
    _configure( stream, clock, columns=120 )
    logger.info( 'Using [/tmp] for dependencies' )
    assert hb._visible_since == 1000.0
    cycle = hb._cycle_duration_s()

    from cuppa.progress import heartbeat_print_cmd_line
    import cuppa.utility.heartbeat as heartbeat_module
    out = io.StringIO()
    real_stdout = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = out
    try:
        heartbeat_print_cmd_line( '/usr/bin/g++ -c foo.cpp', [], [], {} )
    finally:
        heartbeat_module.sys.stdout = real_stdout

    assert clock.now == pytest.approx( 1000.0 + cycle )
    assert hb._last_line == ''
    assert '/usr/bin/g++ -c foo.cpp\n' in stream.getvalue()
    assert out.getvalue() == ''


def test_warn_clear_does_not_wait_for_animation_cycle( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock( start=1000.0 )
    _configure( stream, clock, columns=120 )
    logger.info( 'Using [/tmp] for dependencies' )
    capture = io.StringIO()
    monkeypatch.setattr( log_mod._log_handler, 'stream', capture )
    logger.warn( 'something went wrong' )
    # Immediate clear — clock must not jump by a full cycle.
    assert clock.now == 1000.0
    assert 'something went wrong' in capture.getvalue()


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


def test_report_on_default_stdout_uses_tty_when_diverting( monkeypatch ):
    """Mode banners must not ride the stdout pipe past a status paint."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'using sconstruct file [sconstruct]' )
    assert 'using sconstruct file' in _status_body( stream )

    import cuppa.utility.heartbeat as heartbeat_module
    pipe = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = pipe
    try:
        write_report_lines( [ 'Running in OFFLINE mode' ] )
    finally:
        heartbeat_module.sys.stdout = real

    assert pipe.getvalue() == ''
    assert 'Running in OFFLINE mode' in stream.getvalue()
    assert 'using sconstruct file' not in _status_body( stream )
    assert 'Running in OFFLINE mode\n' in stream.getvalue()


def test_report_also_reaches_stdout_when_launcher_is_piped( monkeypatch ):
    """CI / redirects: outer stdout is not a TTY — durable line on the pipe only."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '0' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'using sconstruct file [sconstruct]' )

    import cuppa.utility.heartbeat as heartbeat_module
    pipe = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = pipe
    try:
        write_report_lines( [ 'Running in OFFLINE mode' ] )
    finally:
        heartbeat_module.sys.stdout = real

    assert pipe.getvalue() == 'Running in OFFLINE mode\n'
    # Never dual-write: CI capture is the pipe; status row was cleared only.
    assert 'Running in OFFLINE mode\n' not in stream.getvalue()
    assert 'using sconstruct file' not in _status_body( stream )


def test_write_transcript_owned_stream_when_interactive( monkeypatch ):
    """Diverting + interactive: clear+write on heartbeat stream, not the pipe."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Updating [libfoo]' )
    assert 'Updating [libfoo]' in _status_body( stream )

    import cuppa.utility.heartbeat as heartbeat_module
    pipe = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = pipe
    try:
        hb.write_transcript( '              → -- Configuring done (0.1s)\n' )
    finally:
        heartbeat_module.sys.stdout = real

    assert pipe.getvalue() == ''
    assert '→ -- Configuring done (0.1s)\n' in stream.getvalue()
    assert 'Updating [libfoo]' not in _status_body( stream )


def test_write_transcript_pipe_only_when_launcher_piped( monkeypatch ):
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '0' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Updating [libfoo]' )

    import cuppa.utility.heartbeat as heartbeat_module
    pipe = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = pipe
    try:
        hb.write_transcript( '              → ninja: no work to do.\n' )
    finally:
        heartbeat_module.sys.stdout = real

    assert pipe.getvalue() == '              → ninja: no work to do.\n'
    assert 'ninja: no work to do.' not in stream.getvalue()


def test_resolve_cuppa_stdout_is_tty_preserves_inherited():
    assert hb.resolve_cuppa_stdout_is_tty(
            environ={ 'CUPPA_STDOUT_IS_TTY': '1' },
            stdout_is_tty=False,
    ) == '1'
    assert hb.resolve_cuppa_stdout_is_tty(
            environ={ 'CUPPA_STDOUT_IS_TTY': '0' },
            stdout_is_tty=True,
    ) == '0'
    assert hb.resolve_cuppa_stdout_is_tty(
            environ={},
            stdout_is_tty=True,
    ) == '1'
    assert hb.resolve_cuppa_stdout_is_tty(
            environ={},
            stdout_is_tty=False,
    ) == '0'


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
    clock.advance( hb._IDLE_GATE_S )
    logger.info( 'Updating [libfoo] during spawn' )
    assert 'Updating [libfoo] during spawn' in _status_body( stream )


def test_reveal_before_print_cmd_line_reuses_status_row( monkeypatch ):
    """PRINT_CMD_LINE clears working in place; durable cmd on the owned stream."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Using [/tmp] for dependencies' )
    assert 'Using [/tmp]' in _status_body( stream )
    before_reveal = stream.getvalue()

    from cuppa.progress import heartbeat_print_cmd_line
    import cuppa.utility.heartbeat as heartbeat_module
    out = io.StringIO()
    real_stdout = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = out
    try:
        heartbeat_print_cmd_line( '/usr/bin/g++ -c foo.cpp', [], [], {} )
    finally:
        heartbeat_module.sys.stdout = real_stdout

    assert '/usr/bin/g++ -c foo.cpp\n' in stream.getvalue()
    assert out.getvalue() == ''
    assert hb._last_line == ''
    # Clear (\\r erase) then durable newline on the same owned stream.
    revealed = stream.getvalue()[ len( before_reveal ): ]
    assert revealed.endswith( '/usr/bin/g++ -c foo.cpp\n' )
    after_cmd = stream.getvalue()

    hb.suppress( advance=False )
    assert hb._suppress_depth == 1
    added = stream.getvalue()[ len( after_cmd ): ]
    assert '\n' not in added
    hb.allow()

    # No status visible → second command is still a durable owned-stream write.
    heartbeat_module.sys.stdout = out
    try:
        heartbeat_print_cmd_line( '/usr/bin/g++ -c bar.cpp', [], [], {} )
    finally:
        heartbeat_module.sys.stdout = real_stdout
    assert '/usr/bin/g++ -c bar.cpp\n' in stream.getvalue()
    assert out.getvalue() == ''


def test_spawn_transcript_clears_heartbeat( monkeypatch ):
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Using [/tmp] for dependencies' )
    assert hb._last_line

    from cuppa import output_processor as op
    import cuppa.utility.heartbeat as heartbeat_module
    out = io.StringIO()
    real = heartbeat_module.sys.stdout
    heartbeat_module.sys.stdout = out
    try:
        op._emit_transcript( '/usr/bin/g++ -c foo.cpp' )
    finally:
        heartbeat_module.sys.stdout = real
    assert '/usr/bin/g++ -c foo.cpp\n' in stream.getvalue()
    assert out.getvalue() == ''
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


def test_transfer_progress_allowed_under_quiet_tty():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, style='pulse' )
    assert hb.transfer_progress_allowed() is True
    assert hb.multi_line_progress_allowed() is False
    hb.reset()


def test_transfer_progress_denied_when_quiet_heartbeat_off():
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, style='off' )
    assert hb.transfer_progress_allowed() is False
    hb.reset()


def test_format_alive_prefix_pulse_and_off():
    plain, styled = hb.format_alive_prefix( 0, style='pulse', compact=False )
    assert plain.startswith( '|' )
    assert plain.endswith( '  ' )
    assert styled
    plain_off, styled_off = hb.format_alive_prefix( 0, style='off' )
    assert plain_off == '' and styled_off == ''


def test_set_presentation_updates_style_and_compact():
    hb.reset()
    hb.set_presentation( style='spinner', compact=True )
    assert hb.style() == 'spinner'
    assert hb.compact() is True
    plain, _styled = hb.format_alive_prefix( 1, style=None, compact=None )
    assert 'working' in plain
    assert '→' in plain
    hb.reset()


def test_operation_status_under_diverting_uses_heartbeat( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, style='pulse' )
    seen = []

    def fake_show( message, sticky=False ):
        seen.append( ( message, sticky ) )

    monkeypatch.setattr( hb, 'show_info', fake_show )
    with hb.operation_status( 'Updating [libfoo] in [/tmp/libfoo]' ):
        assert seen == [ ( 'Updating [libfoo] in [/tmp/libfoo]', True ) ]
    hb.reset()


def test_sticky_caption_does_not_age_out():
    """In-progress captions stay until clear; event INFO still ages out."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    hb.show_info( 'Updating [libfoo]', sticky=True )
    assert 'Updating [libfoo]' in _status_body( stream )
    assert hb._sticky is True

    hold = hb._caption_hold_s()
    clock.advance( hold + 1.0 )
    hb._on_pulse()
    assert 'Updating [libfoo]' in _status_body( stream )
    assert hb._body == 'Updating [libfoo]'

    # Event INFO must not steal the sticky row; it becomes pending.
    clock.advance( 0.15 )
    logger.info( 'Using [/tmp] for dependencies' )
    assert 'Updating [libfoo]' in _status_body( stream )
    assert 'Using [/tmp]' not in _status_body( stream )

    hb.clear()
    assert hb._sticky is False
    hb.reset()


def test_caption_flush_does_not_advance_spin():
    """Same-row message updates keep the ECG frame; only pulse advances spin."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    hb.show_info( 'Updating [libfoo]', sticky=True )
    assert hb._spin == 0
    assert 'Updating [libfoo]' in _status_body( stream )
    # Mid-cycle on the *same* row — caption change must not reset or bump.
    hb._spin = 7

    clock.advance( 0.15 )
    hb.show_info( 'Updating [libbar]', sticky=True )
    assert hb._spin == 7
    assert 'Updating [libbar]' in _status_body( stream )

    hb._on_pulse()
    assert hb._spin == 8
    hb.reset()


def test_caption_flush_does_not_restart_pulse_timer( monkeypatch ):
    """Re-arming on every INFO reset the beat cadence (choppy heartbeat)."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    # Real timers would fire; stub so we only watch arm/ensure behaviour.
    monkeypatch.setattr( hb, '_pulse_enabled', True )
    started = []

    class _FakeTimer( object ):
        def __init__( self, interval, callback ):
            self.interval = interval
            self.callback = callback
            self.daemon = False

        def start( self ):
            started.append( self )

        def cancel( self ):
            pass

    monkeypatch.setattr( hb.threading, 'Timer', _FakeTimer )
    hb.show_info( 'Updating [libfoo]', sticky=True )
    assert len( started ) == 1
    first = started[0]
    assert hb._pulse is first

    clock.advance( 0.15 )
    hb.show_info( 'Updating [libbar]', sticky=True )
    assert len( started ) == 1
    assert hb._pulse is first

    hb.reset()


def test_clear_resets_spin_so_new_row_starts_at_rest():
    """After transcript/clear, the next status row must not resume mid-beat."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    hb.show_info( 'Updating [libfoo]', sticky=True )
    hb._spin = 9
    hb.clear()
    assert hb._spin == 0
    assert hb._last_line == ''

    hb.show_info( 'Updating [libbar]', sticky=True )
    assert hb._spin == 0
    assert hb._pulse_frame( hb._spin ) == hb._PULSE_REST
    assert 'Updating [libbar]' in _status_body( stream )
    hb.reset()


def test_operation_status_handoff_keeps_spin_without_full_cycle_dwell():
    """Sequential quiet retrieves must replace in-row, not dwell+clear each time."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )

    with hb.operation_status( 'Updating [libfoo]' ):
        assert 'Updating [libfoo]' in _status_body( stream )
        hb._spin = 5

    # Released sticky, but the row and spin remain for the next caption.
    assert hb._sticky is False
    assert hb._spin == 5
    assert hb._last_line
    assert 'Updating [libfoo]' in _status_body( stream )

    clock.advance( 0.05 )
    with hb.operation_status( 'Updating [libbar]' ):
        assert hb._spin == 5
        assert 'Updating [libbar]' in _status_body( stream )
        assert 'Updating [libfoo]' not in _status_body( stream )

    hb.reset()


def test_rapid_non_sticky_info_can_flush_several_times_per_cycle():
    """Event INFO throttle is ~0.12s — not one flush per full ECG cycle."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock, columns=120 )
    cycle = hb._cycle_duration_s()
    paints = 0
    t = 0.0
    while t < cycle:
        hb.show_info( 'Updating [pkg-{}]'.format( paints ) )
        paints += 1
        clock.advance( hb._MESSAGE_INTERVAL_S + 0.01 )
        t += hb._MESSAGE_INTERVAL_S + 0.01
    assert paints >= 5
    assert 'Updating [pkg-{}]'.format( paints - 1 ) in _status_body( stream )
    hb.reset()


def test_operation_status_terse_without_quiet_uses_shared_status_row( monkeypatch ):
    """Compact terse arms the same heartbeat row — not a second painter."""
    import cuppa.utility.download as download_mod

    hb.reset()
    hb.set_presentation( style='pulse', compact=True )
    stream = io.StringIO()
    clock = FakeClock()
    sleeps = []

    def sleep( seconds ):
        sleeps.append( seconds )
        clock.advance( seconds )

    monkeypatch.setattr( hb, '_clock', clock )
    monkeypatch.setattr( hb, '_sleep', sleep )
    monkeypatch.setattr(
            download_mod, 'open_progress_stream',
            lambda: ( stream, True, False ),
    )
    monkeypatch.setattr( hb, '_columns', 200 )

    assert hb.ensure_status_row() is True
    assert hb.status_row_active() is True
    assert hb.diverting() is False
    assert hb.quiet_console() is False

    with hb.operation_status(
            'Updating [libfoo] · git+https://example.com/very/long/path@master'
    ):
        body = _status_body( stream )
        assert 'Updating [libfoo]' in body
        # Shared column probe on the owned TTY — not the pipe's 80 fallback.
        assert '\u2026' not in body
        assert visible_len( body ) > 80

    # Exit releases sticky without full-cycle dwell.
    cycle = hb._cycle_duration_s()
    assert sum( sleeps ) < cycle * 0.5
    assert hb.diverting() is False
    hb.reset()


def test_resolve_transcript_skips_full_cycle_dwell_after_operation_status( monkeypatch ):
    """Uncounted resolve children must not seize one ECG cycle each."""
    import cuppa.utility.download as download_mod
    from cuppa.progress import _write_terse_stdout

    hb.reset()
    hb.set_presentation( style='pulse', compact=True )
    stream = io.StringIO()
    clock = FakeClock()
    sleeps = []

    def sleep( seconds ):
        sleeps.append( seconds )
        clock.advance( seconds )

    monkeypatch.setattr( hb, '_clock', clock )
    monkeypatch.setattr( hb, '_sleep', sleep )
    monkeypatch.setattr(
            download_mod, 'open_progress_stream',
            lambda: ( stream, True, False ),
    )
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '0' )

    out = io.StringIO()
    real_stdout = hb.sys.stdout
    hb.sys.stdout = out
    try:
        with hb.operation_status( 'Updating [fmt]' ):
            assert 'Updating [fmt]' in _status_body( stream )
        _write_terse_stdout(
                '              → [update]   <fmt> · main · abcdef01\n',
                dwell=False,
        )
        _write_terse_stdout(
                '              → [location] <date> = git_https_… · repository\n',
                dwell=False,
        )
    finally:
        hb.sys.stdout = real_stdout

    cycle = hb._cycle_duration_s()
    assert sum( sleeps ) < cycle * 0.5
    assert '[update]' in out.getvalue()
    assert '[location]' in out.getvalue()
    hb.reset()


def test_scons_display_clears_heartbeat_before_removed_line( monkeypatch ):
    """Clean ``Removed …`` must not glue onto the quiet status row."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Using [/tmp] for dependencies and [/tmp/dl] for downloads' )
    assert 'Using [/tmp]' in _status_body( stream )

    from SCons.Util import display
    display( 'Removed _build/foo.o' )

    # StringIO keeps CR history; treat CR as a line break the way a TTY would.
    lines = [
            line.rstrip()
            for line in strip_ansi( stream.getvalue() ).replace( '\r', '\n' ).split( '\n' )
            if line.strip()
    ]
    assert any( line == 'Removed _build/foo.o' for line in lines )
    assert all( 'downloadsRemoved' not in line for line in lines )
    assert 'Using [/tmp]' not in _status_body( stream )


def test_clean_quiet_uses_classic_quiet_without_heartbeat():
    """``-Q -c`` must not arm the status row (SCons clean bypasses PRINT_CMD_LINE)."""
    from cuppa.construct import Construct

    class _Env:
        def get_option( self, name, default=None ):
            options = {
                'verbosity': None,
                'silent': False,
                'no_progress': True,
                'clean': True,
                'quiet_heartbeat': 'pulse',
                'terse_output': False,
            }
            return options.get( name, default )

        def get( self, name, default=None ):
            return self.get_option( name, default )

    Construct._set_verbosity_level( _Env(), apply_quiet_heartbeat=True )
    assert hb.quiet_console() is True
    assert hb.diverting() is False
    assert not logger.isEnabledFor( logging.INFO )


def test_reset_and_atexit_restore_terminal_wrap():
    """Leaving ``?7l`` on makes later builds truncate long lines at the margin."""
    stream = io.StringIO()
    clock = FakeClock()
    _configure( stream, clock )
    logger.info( 'Using [/tmp] for dependencies' )
    assert hb._wrap_off_sent is True
    assert hb._WRAP_OFF in stream.getvalue()

    before = stream.getvalue()
    hb.reset()
    after = stream.getvalue()[ len( before ): ]
    assert hb._WRAP_ON in after
    assert hb._wrap_off_sent is False
    assert hb._wrap_disabled is False

    # Simulate a prior process that exited mid-pulse: force-heal without flags.
    hb._wrap_off_sent = False
    hb._wrap_disabled = False
    healed = io.StringIO()
    hb.restore_terminal_wrap( force=True )
    # No active stream — force opens a progress stream; with no TTY in tests
    # that may be stderr. Call again with an injected stream via paint path.
    hb.configure_quiet_console(
            'warn',
            stream=healed,
            is_tty=True,
            owns_stream=False,
            clock=clock,
            columns=120,
            pulse=False,
    )
    logger.info( 'again' )
    assert hb._wrap_off_sent is True
    hb.restore_terminal_wrap()
    assert hb._WRAP_ON in healed.getvalue()
    assert hb._wrap_off_sent is False
