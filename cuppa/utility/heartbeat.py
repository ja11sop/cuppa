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
# Compact bounce pulse (alive-progress "circles"/unknown-bar idea, not the
# library): a hot cell travels on a dim track — reads as a heartbeat without
# a dependency or cell-architecture compiler. Width stays in the 8–12 range.
_PULSE_WIDTH = 10
_PULSE_BG = '\u00b7'   # ·
_PULSE_FG = '\u25cf'   # ●
# ``working ···●······ `` — fixed visible prefix so the eye can skip lines.
_WORKING = 'working'

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
_last_line = ''
_columns = None  # None → ask the TTY; set for tests
_spin = 0
_clock = time.monotonic
_pulse = None
_pulse_lock = threading.Lock()
_draw_lock = threading.Lock()
_pulse_enabled = True
_suppress_depth = 0
_wrap_disabled = False


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
    """One bounce-pulse frame: hot cell travels left→right→left on a dim track."""
    width = _PULSE_WIDTH
    if width < 2:
        return _PULSE_FG
    period = 2 * ( width - 1 )
    pos = index % period
    if pos >= width:
        pos = period - pos
    return _PULSE_BG * pos + _PULSE_FG + _PULSE_BG * ( width - 1 - pos )


def _prefix():
    """``working ···●······ `` (pulse advances while the line is held)."""
    return "{} {} ".format( _WORKING, _pulse_frame( _spin ) )


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
    """Keep the bounce pulse moving while a status line is held (long waits)."""
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
        timer = threading.Timer( _PULSE_INTERVAL_S, _on_pulse )
        timer.daemon = True
        _pulse = timer
        timer.start()


def _expire_message_unlocked( now ):
    """Drop a stale caption; keep ``working`` + pulse until the next INFO."""
    global _body, _message_shown_at
    if not _body or not _message_shown_at:
        return False
    if ( now - _message_shown_at ) < _MESSAGE_HOLD_S:
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
    global _message_shown_at
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
    _last_line = ''
    _columns = None
    _spin = 0
    _pulse_enabled = True
    _suppress_depth = 0
    _clock = time.monotonic


def configure_quiet_console(
        quiet_kind,
        *,
        stream=None,
        is_tty=None,
        owns_stream=None,
        clock=None,
        columns=None,
        pulse=True,
):
    """Enable quiet console, with TTY heartbeat when appropriate.

    ``quiet_kind`` is ``'warn'`` (``-Q``), ``'error'`` (``-s``), or ``None``.
    Without a TTY, keep classic quiet levels. With ``--terse-output``, the
    heartbeat still runs so long waits between transcript lines stay alive;
    terse writers clear this line before each stdout write.

    Status text is truncated to the **TTY** width (not piped stdout). Autowrap
    is disabled while the status line is shown so a mis-sized width cannot
    leave wrapped debris. Each line is ``working <pulse> <message>``; after
    ``_MESSAGE_HOLD_S`` without a newer INFO the caption drops and only the
    ``working`` + pulse anchor remains until the next message (a new INFO
    always replaces the caption immediately).
    """
    from cuppa.log import set_logging_level

    global _quiet_console, _suppress_below, _heartbeat_active
    global _stream, _owns_stream, _clock, _columns, _pulse_enabled

    reset()
    if clock is not None:
        _clock = clock
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
    """Blank the status line so a report, warn/error, or transcript can replace it."""
    with _draw_lock:
        _clear_unlocked( advance=False )


def reveal():
    """Erase ``working`` in place before a stdout transcript line.

    SCons prints tool commands via ``PRINT_CMD_LINE_FUNC`` *before* ``SPAWN``.
    Clearing inside ``Popen`` is too late: the ``cuppa`` launcher may already
    have echoed the command onto the status row. Call this from the print
    hook *before* writing to the stdout pipe so the command reuses the same
    physical row (no blank line).

    No-op when nothing is on the status row.
    """
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
    Pending INFO is kept so it can show after ``allow()``.
    """
    global _suppress_depth
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
    global _message_shown_at
    _cancel_pulse()
    # Keep ``_pending`` when suppressing so INFO during a spawn can show later;
    # a plain clear / reveal (warn/report/transcript) drops it.
    if not keep_pending:
        _pending = None
    _body = None
    _message_shown_at = 0.0
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
    global _last_line, _wrap_disabled
    if _stream is None or body is None or _suppress_depth:
        return
    from cuppa.colourise import as_subdued
    from cuppa.output_processor import strip_ansi

    cols = _terminal_columns()
    prefix = _prefix()
    if body:
        budget = max( 1, cols - len( prefix ) )
        plain = _fit_plain( strip_ansi( body ), budget )
        text = prefix + plain
    else:
        # Anchor only — no trailing space after the pulse.
        text = prefix.rstrip()
    styled = as_subdued( text )
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
