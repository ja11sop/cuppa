#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Quiet+TTY heartbeat — diverted INFO as one subdued status line
#-------------------------------------------------------------------------------

"""TTY liveness while ``-Q`` / ``-s`` suppress multi-line info logs.

See ``design/plans/quiet-tty-heartbeat.md``. Not a console report: clear this
line before reports, warnings, and errors. Silent without a controlling TTY.
"""

import logging
import time


# Match download.ProgressReporter's TTY interval.
_INTERVAL_S = 0.35

_quiet_console = False
_suppress_below = logging.WARN
_heartbeat_active = False
_stream = None
_owns_stream = False
_last_emit = 0.0
_pending = None
_last_line = ''
_width = 0
_clock = time.monotonic


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


def reset():
    """Stop diversion and restore a clean status line."""
    global _quiet_console, _suppress_below, _heartbeat_active
    global _stream, _owns_stream, _last_emit, _pending, _last_line, _width
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
    _last_line = ''
    _width = 0


def configure_quiet_console(
        quiet_kind,
        *,
        terse_output=False,
        stream=None,
        is_tty=None,
        owns_stream=None,
        clock=None,
):
    """Enable quiet console, with TTY heartbeat when appropriate.

    ``quiet_kind`` is ``'warn'`` (``-Q``), ``'error'`` (``-s``), or ``None``.
    With ``--terse-output``, keep classic quiet levels (terse already shows
    resolve/location liveness). Without a TTY, keep classic quiet levels.
    """
    from cuppa.log import set_logging_level

    global _quiet_console, _suppress_below, _heartbeat_active
    global _stream, _owns_stream, _clock

    reset()
    if clock is not None:
        _clock = clock
    if not quiet_kind:
        return

    _quiet_console = True
    _suppress_below = logging.WARN if quiet_kind == 'warn' else logging.ERROR

    if terse_output:
        set_logging_level( quiet_kind )
        return

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
    """Blank the status line so a report or warn/error can replace it."""
    global _pending, _last_line, _width, _last_emit
    _pending = None
    if not _heartbeat_active or _stream is None:
        _last_line = ''
        _width = 0
        return
    if not _last_line and not _width:
        return
    try:
        import shutil
        cols = max( _width, shutil.get_terminal_size( fallback=( 80, 24 ) ).columns )
    except Exception:
        cols = max( _width, 80 )
    try:
        _stream.write( '\r' + ( ' ' * cols ) + '\r' )
        _stream.flush()
    except Exception:
        pass
    _last_line = ''
    _width = 0
    # Allow the next INFO to show immediately after a clear.
    _last_emit = 0.0


def _flush( now ):
    global _pending, _last_emit, _last_line, _width
    if _pending is None or _stream is None:
        return
    from cuppa.colourise import as_subdued
    from cuppa.output_processor import strip_ansi
    from cuppa.utility.storage import pad_visible, visible_len

    plain = strip_ansi( _pending )
    styled = as_subdued( plain )
    _width = max( _width, visible_len( styled ), visible_len( _last_line ) )
    try:
        import shutil
        cols = max( _width, shutil.get_terminal_size( fallback=( 80, 24 ) ).columns )
    except Exception:
        cols = max( _width, 80 )
    try:
        _stream.write( '\r' + pad_visible( styled, cols ) )
        _stream.flush()
    except Exception:
        pass
    _last_line = styled
    _last_emit = now
    _pending = None
