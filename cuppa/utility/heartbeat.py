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
"""

import logging
import os
import threading
import time


# Match download.ProgressReporter's TTY interval.
_INTERVAL_S = 0.35
_ELLIPSIS = '\u2026'
# ASCII spinner — widely available; advances while a status line is held.
_SPINNER = ( '|', '/', '-', '\\' )
# ``Working / `` — fixed visible prefix so the eye can skip heartbeat lines.
_WORKING = 'Working'


_quiet_console = False
_suppress_below = logging.WARN
_heartbeat_active = False
_stream = None
_owns_stream = False
_last_emit = 0.0
_pending = None
_body = None  # last plain message (without Working/spinner)
_last_line = ''
_columns = None  # None → ask the TTY; set for tests
_spin = 0
_clock = time.monotonic
_pulse = None
_pulse_lock = threading.Lock()
_pulse_enabled = True


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


def _prefix():
    """``Working / `` (spinner advances while the line is held)."""
    return "{} {} ".format( _WORKING, _SPINNER[ _spin % len( _SPINNER ) ] )


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
    """Keep the spinner moving while a status line is held (long waits)."""
    global _pulse
    with _pulse_lock:
        if _pulse is not None:
            try:
                _pulse.cancel()
            except Exception:
                pass
            _pulse = None
        if not _pulse_enabled or not _heartbeat_active or not _body:
            return
        timer = threading.Timer( _INTERVAL_S, _on_pulse )
        timer.daemon = True
        _pulse = timer
        timer.start()


def _on_pulse():
    global _spin
    if not _heartbeat_active or not _body:
        return
    _spin = ( _spin + 1 ) % len( _SPINNER )
    _draw( _body )
    _arm_pulse()


def reset():
    """Stop diversion and restore a clean status line."""
    global _quiet_console, _suppress_below, _heartbeat_active
    global _stream, _owns_stream, _last_emit, _pending, _body, _last_line
    global _columns, _spin, _pulse_enabled, _clock
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
    _last_line = ''
    _columns = None
    _spin = 0
    _pulse_enabled = True
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

    Status text is truncated to the **TTY** width (not piped stdout) so ``\\r``
    rewrite never wraps. Each line is ``Working <spinner> <message>``.
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
    _pending = text
    now = _clock()
    if _last_emit and ( now - _last_emit ) < _INTERVAL_S:
        return
    _flush( now )


def flush_pending():
    """Emit a deferred status line (tests / shutdown)."""
    if _pending is not None:
        _flush( _clock() )


def clear():
    """Blank the status line so a report, warn/error, or transcript can replace it."""
    global _pending, _body, _last_line, _last_emit
    _cancel_pulse()
    _pending = None
    _body = None
    if not _heartbeat_active or _stream is None:
        _last_line = ''
        return
    if not _last_line:
        return
    cols = _terminal_columns()
    try:
        _stream.write( '\r' + ( ' ' * cols ) + '\r' )
        _stream.flush()
    except Exception:
        pass
    _last_line = ''
    # Allow the next INFO to show immediately after a clear.
    _last_emit = 0.0


def _flush( now ):
    global _pending, _last_emit, _body, _spin
    if _pending is None or _stream is None:
        return
    _body = _pending
    _pending = None
    _spin = ( _spin + 1 ) % len( _SPINNER )
    _draw( _body )
    _last_emit = now
    _arm_pulse()


def _draw( body ):
    """Write one ``Working <spinner> <message>`` line fitted to the TTY width."""
    global _last_line
    if _stream is None or body is None:
        return
    from cuppa.colourise import as_subdued
    from cuppa.output_processor import strip_ansi
    from cuppa.utility.storage import pad_visible

    cols = _terminal_columns()
    prefix = _prefix()
    # Fit the message into the columns left after the Working/spinner prefix.
    budget = max( 1, cols - len( prefix ) )
    plain = _fit_plain( strip_ansi( body ), budget )
    styled = as_subdued( prefix + plain )
    try:
        _stream.write( '\r' + pad_visible( styled, cols ) )
        _stream.flush()
    except Exception:
        pass
    _last_line = styled
