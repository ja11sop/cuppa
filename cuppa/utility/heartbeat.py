#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Quiet+TTY heartbeat — diverted INFO as one subdued status line
#-------------------------------------------------------------------------------

"""TTY liveness while ``-Q`` / ``-s`` suppress multi-line info logs.

See ``design/plans/quiet-tty-heartbeat.md``. Not a console report: clear this
line before reports, warnings, errors, and build transcript lines. Silent
without a controlling TTY.

Writes go to the controlling TTY (``/dev/tty``). Build commands often go
through the ``cuppa`` launcher's stdout pipe, so the status line is
**suppressed for the whole spawn** (not only cleared once) to avoid a pulse
redraw racing the piped command onto the same row.
"""

import logging
import os
import threading
import time


# Message changes throttle slightly slower than the pulse tick.
_MESSAGE_INTERVAL_S = 0.12
# Caption hold: several message periods, then drop text; next INFO always
# replaces the caption immediately via ``_flush_unlocked``.
_MESSAGE_HOLD_PERIODS = 5
_MESSAGE_HOLD_S = _MESSAGE_INTERVAL_S * _MESSAGE_HOLD_PERIODS
_PULSE_INTERVAL_S = 0.08
_ELLIPSIS = '\u2026'
# Compact ECG-style pulse (alive-progress ``pulse`` idea, not the library):
# bordered track, bullet, short QRS blip. Cycle starts on rest so the first
# paint is not mid-beat; rest frames also use a longer tick.
_PULSE_BEAT = (
        '|•--------|',
        '|-•-------|',
        '|--•------|',
        '|---√-----|',
        '|---√\\----|',
        '|---√\\/---|',
        '|----\\/---|',
        '|-----/---|',
        '|------•--|',
        '|-------•-|',
        '|--------•|',
)
_PULSE_REST = '|---------|'
_PULSE_REST_HOLD = 3
_PULSE_FRAMES = ( _PULSE_REST, ) * _PULSE_REST_HOLD + _PULSE_BEAT
_PULSE_WIDTH = len( _PULSE_FRAMES[0] )
# Hot glyphs in the QRS / bullet (track and bars stay subdued; hot = hospital green).
_PULSE_HOT = frozenset( '•√\\/' )
# Rest ticks run slower than the beat so the diastolic pause is felt.
_PULSE_REST_INTERVAL_S = _PULSE_INTERVAL_S * 2.5
# Classic ASCII spinner — lighter alternative to the ECG pulse.
_SPINNER = ( '|', '/', '-', '\\' )
_STYLE_PULSE = 'pulse'
_STYLE_SPINNER = 'spinner'
_STYLES = frozenset( ( _STYLE_PULSE, _STYLE_SPINNER ) )
# ``working`` is the durable anchor; two spaces separate the widget from the caption.
_WORKING = 'working'
_GAP = '  '

# VT100 / ANSI: erase from cursor to end of line; disable/enable autowrap.
_ERASE_EOL = '\x1b[K'
_WRAP_OFF = '\x1b[?7l'
_WRAP_ON = '\x1b[?7h'


_quiet_console = False
_suppress_below = logging.WARN
_heartbeat_active = False
_stream = None
_owns_stream = False
_last_emit = 0.0
_pending = None
# Plain caption without working/pulse. ``None`` = status off; ``''`` = anchor
# only (pulse held after the last INFO aged out).
_body = None
_message_shown_at = 0.0
_visible_since = 0.0
_last_line = ''
_columns = None  # None → ask the TTY; set for tests
_spin = 0
_clock = time.monotonic
_sleep = time.sleep
_pulse = None
_pulse_lock = threading.Lock()
_draw_lock = threading.Lock()
_pulse_enabled = True
_suppress_depth = 0
_wrap_disabled = False
_style = _STYLE_PULSE


def _terminal_columns():
    """Columns for one physical status line.

    Prefer the progress TTY's file descriptor. Under the ``cuppa`` launcher
    stdout/stderr are pipes, so ``shutil.get_terminal_size()`` falls back to
    80 and the status line looks arbitrarily narrow.
    """
    if _columns is not None:
        return max( 1, int( _columns ) )
    if _stream is not None:
        try:
            return max( 1, os.get_terminal_size( _stream.fileno() ).columns )
        except Exception:
            pass
    try:
        import shutil
        return max( 1, shutil.get_terminal_size( fallback=( 80, 24 ) ).columns )
    except Exception:
        return 80


def _fit_plain( plain, cols ):
    """Truncate plain text to ``cols`` visible columns with an ellipsis."""
    text = plain or ''
    if cols < 1:
        cols = 1
    if len( text ) <= cols:
        return text
    if cols == 1:
        return _ELLIPSIS
    return text[ : cols - 1 ] + _ELLIPSIS


def _pulse_frame( index ):
    """One ECG-style pulse frame from the fixed cycle."""
    return _PULSE_FRAMES[ index % len( _PULSE_FRAMES ) ]


def _spinner_frame( index ):
    """One classic ASCII spinner frame."""
    return _SPINNER[ index % len( _SPINNER ) ]


def _animation_plain():
    """Current pulse or spinner widget (no leading/trailing spaces)."""
    if _style == _STYLE_SPINNER:
        return _spinner_frame( _spin )
    return _pulse_frame( _spin )


def _prefix_plain():
    """Plain ``working <widget><gap>`` used for column budgeting."""
    return "{} {}{}".format( _WORKING, _animation_plain(), _GAP )


def _style_pulse( frame ):
    """Subdue track/bars; colour the bullet and QRS hospital-monitor green."""
    from cuppa.colourise import as_colour, as_subdued

    parts = []
    buf = []
    hot = None
    for ch in frame:
        is_hot = ch in _PULSE_HOT
        if hot is None:
            hot = is_hot
            buf = [ ch ]
            continue
        if is_hot == hot:
            buf.append( ch )
            continue
        text = ''.join( buf )
        parts.append( as_colour( 'success', text ) if hot else as_subdued( text ) )
        hot = is_hot
        buf = [ ch ]
    if buf:
        text = ''.join( buf )
        parts.append( as_colour( 'success', text ) if hot else as_subdued( text ) )
    return ''.join( parts )


def _animation_styled():
    """Styled pulse or spinner widget."""
    from cuppa.colourise import as_subdued
    if _style == _STYLE_SPINNER:
        return as_subdued( _spinner_frame( _spin ) )
    return _style_pulse( _pulse_frame( _spin ) )


def _prefix_styled():
    """Styled ``working`` + widget + gap; QRS green when colour is on."""
    from cuppa.colourise import as_subdued
    return as_subdued( _WORKING + ' ' ) + _animation_styled() + as_subdued( _GAP )


def _next_pulse_interval():
    """Longer delay after a rest frame; normal cadence during the beat/spinner."""
    if _style == _STYLE_PULSE and _pulse_frame( _spin ) == _PULSE_REST:
        return _PULSE_REST_INTERVAL_S
    return _PULSE_INTERVAL_S


def _cycle_duration_s():
    """Wall time for one full pulse or spinner cycle."""
    if _style == _STYLE_SPINNER:
        return len( _SPINNER ) * _PULSE_INTERVAL_S
    return (
            _PULSE_REST_HOLD * _PULSE_REST_INTERVAL_S
            + len( _PULSE_BEAT ) * _PULSE_INTERVAL_S
    )


def _caption_hold_s():
    """Caption stays at least one full animation cycle so it can be read."""
    return max( _MESSAGE_HOLD_S, _cycle_duration_s() )


def _dwell_remaining_s():
    """Seconds left before the status line may be blanked without looking like a flash."""
    with _draw_lock:
        if not _last_line and _body is None:
            return 0.0
        if not _visible_since:
            return 0.0
        elapsed = _clock() - _visible_since
        return max( 0.0, _cycle_duration_s() - elapsed )


def _ensure_min_dwell():
    """Wait out one full animation cycle before erase-for-transcript.

    Warn/error ``clear()`` stays immediate. Tool ``reveal`` / spawn ``suppress``
    wait so ``working`` does not flash and vanish unreadably.
    """
    remaining = _dwell_remaining_s()
    if remaining > 0:
        _sleep( remaining )


def normalize_style( style ):
    """Return a valid heartbeat style name (``pulse`` or ``spinner``)."""
    if style is None or style == '':
        return _STYLE_PULSE
    if isinstance( style, ( list, tuple ) ):
        style = style[0] if style else _STYLE_PULSE
    text = str( style ).strip().lower()
    if text not in _STYLES:
        raise ValueError(
                "quiet heartbeat style must be 'pulse' or 'spinner', not {!r}".format( style )
        )
    return text


def style():
    """Current quiet heartbeat animation style."""
    return _style


def quiet_console():
    """True when ``-Q`` / ``-s`` forced quiet without an explicit ``--verbosity``."""
    return _quiet_console


def diverting():
    """True when INFO is folded onto the TTY status line."""
    return _heartbeat_active


def suppress_below():
    """Multi-line log threshold while diverting (``WARN`` for ``-Q``, ``ERROR`` for ``-s``)."""
    return _suppress_below


def multi_line_progress_allowed():
    """Whether git/download bars may print.

    Off under quiet console even when the logger stays at INFO for diversion.
    Otherwise matches the historical ``logger.isEnabledFor(INFO)`` gate.
    """
    if _quiet_console:
        return False
    from cuppa.log import logger
    return logger.isEnabledFor( logging.INFO )


def _cancel_pulse():
    global _pulse
    with _pulse_lock:
        if _pulse is not None:
            try:
                _pulse.cancel()
            except Exception:
                pass
            _pulse = None


def _arm_pulse():
    """Keep the ECG pulse moving while a status line is held (long waits)."""
    global _pulse
    with _pulse_lock:
        if _pulse is not None:
            try:
                _pulse.cancel()
            except Exception:
                pass
            _pulse = None
        if (
                not _pulse_enabled
                or not _heartbeat_active
                or _body is None
                or _suppress_depth
        ):
            return
        timer = threading.Timer( _next_pulse_interval(), _on_pulse )
        timer.daemon = True
        _pulse = timer
        timer.start()


def _expire_message_unlocked( now ):
    """Drop a stale caption; keep ``working`` + widget until the next INFO."""
    global _body, _message_shown_at
    if not _body or not _message_shown_at:
        return False
    if ( now - _message_shown_at ) < _caption_hold_s():
        return False
    _body = ''
    _message_shown_at = 0.0
    return True


def _on_pulse():
    global _spin
    if not _heartbeat_active or _body is None or _suppress_depth:
        return
    with _draw_lock:
        if not _heartbeat_active or _body is None or _suppress_depth:
            return
        _expire_message_unlocked( _clock() )
        _spin += 1
        _draw_unlocked( _body )
    _arm_pulse()


def reset():
    """Stop diversion and restore a clean status line."""
    global _quiet_console, _suppress_below, _heartbeat_active
    global _stream, _owns_stream, _last_emit, _pending, _body, _last_line
    global _columns, _spin, _pulse_enabled, _clock, _suppress_depth
    global _message_shown_at, _visible_since, _style, _sleep
    clear()
    if _owns_stream and _stream is not None:
        try:
            _stream.close()
        except Exception:
            pass
    _quiet_console = False
    _suppress_below = logging.WARN
    _heartbeat_active = False
    _stream = None
    _owns_stream = False
    _last_emit = 0.0
    _pending = None
    _body = None
    _message_shown_at = 0.0
    _visible_since = 0.0
    _last_line = ''
    _columns = None
    _spin = 0
    _pulse_enabled = True
    _suppress_depth = 0
    _style = _STYLE_PULSE
    _clock = time.monotonic
    _sleep = time.sleep


def configure_quiet_console(
        quiet_kind,
        *,
        stream=None,
        is_tty=None,
        owns_stream=None,
        clock=None,
        columns=None,
        pulse=True,
        style=None,
        sleep=None,
):
    """Enable quiet console, with TTY heartbeat when appropriate.

    ``quiet_kind`` is ``'warn'`` (``-Q``), ``'error'`` (``-s``), or ``None``.
    ``style`` is ``pulse`` (ECG, default) or ``spinner`` (classic ASCII).
    Without a TTY, keep classic quiet levels. With ``--terse-output``, the
    heartbeat still runs so long waits between transcript lines stay alive;
    terse writers clear this line before each stdout write.

    Status text is truncated to the **TTY** width (not piped stdout). Autowrap
    is disabled while the status line is shown so a mis-sized width cannot
    leave wrapped debris. Each line is ``working <widget>  <message>``; after
    ``_MESSAGE_HOLD_S`` without a newer INFO the caption drops and only the
    ``working`` + widget anchor remains until the next message (a new INFO
    always replaces the caption immediately).
    """
    from cuppa.log import set_logging_level

    global _quiet_console, _suppress_below, _heartbeat_active
    global _stream, _owns_stream, _clock, _columns, _pulse_enabled, _style, _sleep

    chosen_style = normalize_style( style )
    reset()
    _style = chosen_style
    if clock is not None:
        _clock = clock
    if sleep is not None:
        _sleep = sleep
    if columns is not None:
        _columns = columns
    _pulse_enabled = bool( pulse )
    if not quiet_kind:
        return

    _quiet_console = True
    _suppress_below = logging.WARN if quiet_kind == 'warn' else logging.ERROR

    if stream is None:
        from cuppa.utility.download import open_progress_stream
        stream, detected_tty, opened_owns = open_progress_stream()
        if is_tty is None:
            is_tty = detected_tty
        if owns_stream is None:
            owns_stream = opened_owns
    else:
        if is_tty is None:
            try:
                is_tty = bool( stream.isatty() )
            except Exception:
                is_tty = False
        if owns_stream is None:
            owns_stream = False

    if not is_tty:
        set_logging_level( quiet_kind )
        return

    _stream = stream
    _owns_stream = bool( owns_stream )
    _heartbeat_active = True
    # Generate INFO so the handler can divert it; multi-line INFO stays off.
    set_logging_level( 'info' )


def show_info( message ):
    """Rewrite the status line with the latest INFO message (throttled)."""
    global _pending
    if not _heartbeat_active or _stream is None:
        return
    text = ( message or '' ).replace( '\n', ' ' ).strip()
    if not text:
        return
    with _draw_lock:
        _pending = text
        if _suppress_depth:
            # Remember for after the spawn; do not fight the transcript.
            return
        now = _clock()
        if _last_emit and ( now - _last_emit ) < _MESSAGE_INTERVAL_S:
            return
        _flush_unlocked( now )


def flush_pending():
    """Emit a deferred status line (tests / shutdown)."""
    with _draw_lock:
        if _pending is not None and not _suppress_depth:
            _flush_unlocked( _clock() )


def clear():
    """Blank the status line so a report, warn/error, or transcript can replace it.

    Immediate — warnings and console reports must not wait on the animation.
    """
    with _draw_lock:
        _clear_unlocked( advance=False )


def reveal():
    """Erase ``working`` in place before a stdout transcript line.

    SCons prints tool commands via ``PRINT_CMD_LINE_FUNC`` *before* ``SPAWN``.
    Clearing inside ``Popen`` is too late: the ``cuppa`` launcher may already
    have echoed the command onto the status row. Call this from the print
    hook *before* writing to the stdout pipe so the command reuses the same
    physical row (no blank line).

    Holds the status for one full animation cycle first so a brief
    ``working`` line does not flash and vanish unreadably.

    No-op when nothing is on the status row.
    """
    with _draw_lock:
        if not _last_line and _body is None:
            return
    _ensure_min_dwell()
    with _draw_lock:
        if not _last_line and _body is None:
            return
        _clear_unlocked( advance=False )


def suppress( advance=False ):
    """Clear and hold the heartbeat for a spawn / transcript burst.

    Nested: each ``suppress()`` needs a matching ``allow()``. While held,
    INFO is remembered but not drawn.

    Clears in place by default. Pass ``advance=True`` only when a following
    stdout write cannot reuse the status row (legacy / non-print-cmd paths).
    Pending INFO is kept so it can show after ``allow()``. Holds for one
    full animation cycle first when a status line is visible (same as
    ``reveal``).
    """
    global _suppress_depth
    with _draw_lock:
        showing = bool( _last_line ) or _body is not None
    if showing:
        _ensure_min_dwell()
    with _draw_lock:
        _suppress_depth += 1
        _clear_unlocked( advance=advance, keep_pending=True )


def allow():
    """End a ``suppress()`` region.

    Does **not** redraw immediately: the launcher may still be flushing the
    command we wrote to the stdout pipe. The next ``show_info`` after the
    spawn paints ``working`` again.
    """
    global _suppress_depth
    with _draw_lock:
        if _suppress_depth > 0:
            _suppress_depth -= 1


def _clear_unlocked( advance=False, keep_pending=False ):
    global _pending, _body, _last_line, _last_emit, _wrap_disabled
    global _message_shown_at, _visible_since
    _cancel_pulse()
    # Keep ``_pending`` when suppressing so INFO during a spawn can show later;
    # a plain clear / reveal (warn/report/transcript) drops it.
    if not keep_pending:
        _pending = None
    _body = None
    _message_shown_at = 0.0
    _visible_since = 0.0
    if not _heartbeat_active or _stream is None:
        _last_line = ''
        _wrap_disabled = False
        return
    try:
        # Erase the status row and restore autowrap. ``advance`` ends the row
        # when a following write cannot reuse it; prefer in-place erase when
        # the next stdout line is written after this clear in the same process.
        text = '\r' + _ERASE_EOL + _WRAP_ON
        if advance:
            text += '\n'
        _stream.write( text )
        _stream.flush()
    except Exception:
        pass
    _wrap_disabled = False
    _last_line = ''
    _last_emit = 0.0


def _flush_unlocked( now ):
    global _pending, _last_emit, _body, _spin, _message_shown_at
    if _pending is None or _stream is None or _suppress_depth:
        return
    _body = _pending
    _pending = None
    _message_shown_at = now
    _spin += 1
    _draw_unlocked( _body )
    _last_emit = now
    _arm_pulse()


def _draw_unlocked( body ):
    """Write one ``working <pulse> [<message>]`` line fitted to the TTY width."""
    global _last_line, _wrap_disabled, _visible_since
    if _stream is None or body is None or _suppress_depth:
        return
    from cuppa.colourise import as_subdued
    from cuppa.output_processor import strip_ansi

    starting = not _last_line
    cols = _terminal_columns()
    prefix_plain = _prefix_plain()
    prefix_styled = _prefix_styled()
    if body:
        budget = max( 1, cols - len( prefix_plain ) )
        plain = _fit_plain( strip_ansi( body ), budget )
        styled = prefix_styled + as_subdued( plain )
    else:
        # Anchor only — no trailing gap after the widget.
        styled = as_subdued( _WORKING + ' ' ) + _animation_styled()
    try:
        # Disable wrap so a wrong column count cannot leave debris; erase the
        # tail instead of space-padding to the full width (padding raced with
        # piped stdout and looked like a trail of blanks).
        _stream.write( _WRAP_OFF + '\r' + styled + _ERASE_EOL )
        _stream.flush()
        _wrap_disabled = True
    except Exception:
        pass
    _last_line = styled
    if starting:
        _visible_since = _clock()
