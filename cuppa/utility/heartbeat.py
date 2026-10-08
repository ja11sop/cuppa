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

After a transcript line, INFO captions stay pending until a short idle gate
expires (latest wins). That avoids a fast ``terse–info–terse`` pattern
seizing the row and forcing a full-cycle dwell before the next transcript.
"""

import logging
import os
import sys
import threading
import time
from contextlib import contextmanager


# Message changes throttle slightly slower than the pulse tick.
_MESSAGE_INTERVAL_S = 0.12
# Caption hold: several message periods, then drop text; next INFO always
# replaces the caption immediately via ``_flush_unlocked``.
_MESSAGE_HOLD_PERIODS = 5
_MESSAGE_HOLD_S = _MESSAGE_INTERVAL_S * _MESSAGE_HOLD_PERIODS
# After a transcript write, defer painting INFO until the stream has been
# quiet this long — coalesce to the latest pending message.
_IDLE_GATE_S = 0.20
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
_STYLE_OFF = 'off'
_STYLES = frozenset( ( _STYLE_PULSE, _STYLE_SPINNER, _STYLE_OFF ) )
# Spinner keeps a ``working`` word — a lone ``|/-\`` is ambiguous. Pulse is
# self-explanatory, so the ECG widget is the anchor alone.
_WORKING = 'working'
_GAP = '  '
# Terse quiet form pads so ``→`` matches location-map arrows (see
# ``cuppa.progress.terse_arrow_column``).

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
_idle_flush = None
_draw_lock = threading.Lock()
_pulse_enabled = True
_suppress_depth = 0
_wrap_disabled = False
_style = _STYLE_PULSE
_compact = False
_transcript_lock = threading.Lock()
# Monotonic time of the last stdout transcript write (0 = none yet).
_last_transcript_at = 0.0
# Sticky captions are in-progress (``operation_status``), not event INFO.
# They do not age out to the pulse-only anchor until cleared or replaced.
_sticky = False
_pending_is_sticky = False
# Terse-without-quiet operation_status owns a TTY status row separate from
# quiet diversion; transcript writes must clear it the same way.
_operation_stop = None
_operation_stream = None
_operation_owns = False
_operation_last = ''
_operation_painted = False
_operation_since = None
_operation_lock = threading.Lock()


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


def _arrow_column():
    """Column where terse nested ``→`` lands; fallback matches resolve maps."""
    try:
        from cuppa.progress import terse_arrow_column
        return max( 0, int( terse_arrow_column() ) )
    except Exception:
        return 14


def _status_head_plain():
    """Widget, with ``working`` only for the spinner style."""
    widget = _animation_plain()
    if _style == _STYLE_SPINNER:
        return "{} {}".format( _WORKING, widget )
    return widget


def _with_aligned_arrow( head ):
    """Pad ``head`` so ``→`` lines up with terse location-map arrows."""
    pad = max( _arrow_column() - len( head ), 1 )
    return head + ( ' ' * pad ) + '→ '


def _prefix_plain():
    """Plain status prefix used for column budgeting."""
    head = _status_head_plain()
    if _compact:
        return _with_aligned_arrow( head )
    return "{}{}".format( head, _GAP )


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
    """Styled status prefix; QRS green when colour is on."""
    from cuppa.colourise import as_subdued
    head = _status_head_plain()
    if _style == _STYLE_SPINNER:
        widget = as_subdued( _WORKING + ' ' ) + _animation_styled()
    else:
        widget = _animation_styled()
    if _compact:
        pad = max( _arrow_column() - len( head ), 1 )
        return widget + as_subdued( ( ' ' * pad ) + '→ ' )
    return widget + as_subdued( _GAP )


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


def idle_gate_s():
    """Seconds of quiet before a deferred status line may paint."""
    return _IDLE_GATE_S


def cycle_duration_s():
    """Wall time for one full pulse or spinner cycle."""
    return _cycle_duration_s()


def ensure_min_dwell( visible_since=None ):
    """Wait out one full animation cycle before erase-for-transcript.

    Warn/error ``clear()`` stays immediate. Tool ``reveal`` / spawn ``suppress``
    wait so ``working`` does not flash and vanish unreadably.

    ``visible_since`` (monotonic/wall matching the transfer clock) lets a
    transfer progress line dwell even when the heartbeat status row is clear.
    """
    if visible_since is not None:
        elapsed = _clock() - visible_since
        remaining = max( 0.0, _cycle_duration_s() - elapsed )
    else:
        remaining = _dwell_remaining_s()
    if remaining > 0:
        _sleep( remaining )


def _transcript_is_idle( now ):
    """True when INFO may paint (no recent transcript, or idle gate elapsed)."""
    if not _last_transcript_at:
        return True
    return ( now - _last_transcript_at ) >= _IDLE_GATE_S


def _cancel_idle_flush_unlocked():
    global _idle_flush
    if _idle_flush is not None:
        try:
            _idle_flush.cancel()
        except Exception:
            pass
        _idle_flush = None


def _arm_idle_flush_unlocked():
    """Schedule a pending INFO paint once the transcript idle gate opens."""
    global _idle_flush
    _cancel_idle_flush_unlocked()
    if (
            not _heartbeat_active
            or _pending is None
            or _suppress_depth
            or _stream is None
    ):
        return
    now = _clock()
    if _transcript_is_idle( now ):
        return
    delay = _IDLE_GATE_S - ( now - _last_transcript_at )
    if delay < 0:
        delay = 0.0
    timer = threading.Timer( delay, _on_idle_flush )
    timer.daemon = True
    _idle_flush = timer
    timer.start()


def _mark_transcript_unlocked():
    """Record a transcript write; defer any pending INFO until idle again."""
    global _last_transcript_at
    _last_transcript_at = _clock()
    _cancel_idle_flush_unlocked()
    if _pending is not None and not _suppress_depth:
        _arm_idle_flush_unlocked()


def _on_idle_flush():
    """Timer callback: paint the latest pending INFO if still idle."""
    with _draw_lock:
        if not _heartbeat_active or _pending is None or _suppress_depth:
            return
        now = _clock()
        if not _transcript_is_idle( now ):
            _arm_idle_flush_unlocked()
            return
        if _last_emit and ( now - _last_emit ) < _MESSAGE_INTERVAL_S:
            return
        _flush_unlocked( now )


def normalize_style( style ):
    """Return a valid heartbeat style: ``pulse``, ``spinner``, or ``off``."""
    if style is None or style == '':
        return _STYLE_PULSE
    if isinstance( style, ( list, tuple ) ):
        style = style[0] if style else _STYLE_PULSE
    text = str( style ).strip().lower()
    if text in ( 'none', 'false', 'no', '0' ):
        text = _STYLE_OFF
    if text not in _STYLES:
        raise ValueError(
                "quiet heartbeat style must be 'pulse', 'spinner', or 'off', not {!r}".format(
                        style
                )
        )
    return text


def style():
    """Current alive-animation style (``pulse``, ``spinner``, or ``off``)."""
    return _style


def compact():
    """True when status lines use the terse arrow-aligned alive head."""
    return _compact


def muted():
    """True when transfer / heartbeat status should use subdued colours (quiet)."""
    return _quiet_console


def set_presentation( *, style=None, compact=None ):
    """Remember alive style and terse compact layout for transfer status.

    Called from output options so download / compress progress can share the
    same pulse/spinner choice and terse arrow alignment even when ``-Q`` is
    not diverting INFO onto the heartbeat line.
    """
    global _style, _compact
    if style is not None:
        _style = normalize_style( style )
    if compact is not None:
        _compact = bool( compact )


def format_alive_prefix( spin, *, style=None, compact=None ):
    """Return ``(plain_prefix, styled_prefix)`` for a transfer status line.

    ``style`` / ``compact`` default to the current presentation. Style ``off``
    yields empty prefixes (progress bar / metrics only).
    """
    chosen = normalize_style( style if style is not None else _style )
    use_compact = _compact if compact is None else bool( compact )
    if chosen == _STYLE_OFF:
        return '', ''

    if chosen == _STYLE_SPINNER:
        widget_plain = _spinner_frame( spin )
        head_plain = "{} {}".format( _WORKING, widget_plain )
        from cuppa.colourise import as_subdued
        widget_styled = as_subdued( widget_plain )
        head_styled = as_subdued( _WORKING + ' ' ) + widget_styled
    else:
        widget_plain = _pulse_frame( spin )
        head_plain = widget_plain
        head_styled = _style_pulse( widget_plain )

    if use_compact:
        pad = max( _arrow_column() - len( head_plain ), 1 )
        plain = head_plain + ( ' ' * pad ) + '→ '
        from cuppa.colourise import as_subdued
        styled = head_styled + as_subdued( ( ' ' * pad ) + '→ ' )
        return plain, styled

    plain = head_plain + _GAP
    from cuppa.colourise import as_subdued
    styled = head_styled + as_subdued( _GAP )
    return plain, styled


def transfer_progress_allowed():
    """Whether cuppa-owned transfer / archive progress may print.

    Under quiet+TTY with an alive style, muted transfer status is allowed (the
    shared engine replaces the old multi-line bar gate). Quiet with
    ``--quiet-heartbeat=off``, or quiet without a TTY, stays silent. Otherwise
    matches the historical INFO gate.
    """
    if _quiet_console:
        if _style == _STYLE_OFF:
            return False
        return bool( _heartbeat_active )
    from cuppa.log import logger
    return logger.isEnabledFor( logging.INFO )


def write_transcript( text, *, dwell=True ):
    """Serialize a stdout transcript write; clear the status line first when diverting.

    Parallel ``-j`` / ``--parallel`` jobs must not interleave terse lines (that
    produced ``format.ovariant`` shearing). Dwell waits run *outside* the
    transcript lock so one job's animation hold does not block others' writes
    for the whole cycle — only the clear+write critical section is serialised.

    Console reports pass ``dwell=False`` so mode banners are not delayed; they
    still clear under the same lock so a status redraw cannot win the row.

    Marks the transcript idle gate so INFO captions stay pending (latest wins)
    until the stream has been quiet for ``_IDLE_GATE_S``.

    Also clears a terse-without-quiet ``operation_status`` row so ``→ [update]``
    cannot share the physical line with a pulse rewrite.
    """
    if dwell and diverting():
        ensure_min_dwell()
    # Drop any standalone operation_status paint before the transcript line.
    clear_operation_status( dwell=dwell )
    with _transcript_lock:
        if diverting():
            with _draw_lock:
                _mark_transcript_unlocked()
                if _last_line or _body is not None:
                    # Keep unpainted INFO so it can show after the idle gate.
                    _clear_unlocked( advance=False, keep_pending=True )
        sys.stdout.write( text )
        try:
            sys.stdout.flush()
        except Exception:
            pass


def _outer_stdout_is_tty():
    """Whether the ``cuppa`` launcher's stdout is a TTY (interactive console).

    The launcher sets ``CUPPA_STDOUT_IS_TTY`` because this process's stdout is
    always a pipe under ``python -m cuppa``. Unset (direct SCons) means
    "assume interactive" so banners stay on the progress TTY only.
    """
    flag = os.environ.get( 'CUPPA_STDOUT_IS_TTY' )
    if flag is None:
        return True
    return flag.strip() not in ( '0', 'false', 'False', 'no', 'NO' )


def write_report( text ):
    """Console report while diverting: clear status, write without dwell.

    On an interactive launcher (``CUPPA_STDOUT_IS_TTY=1``), write only on the
    progress TTY so the stdout pipe cannot append the banner onto
    ``working …``. When the launcher itself is piped (CI, ``>log``), also
    write on stdout so the wrapper can forward the report — CONOUT$ /
    ``/dev/tty`` alone would hide it from capture. Non-diverting callers keep
    using stdout only.

    Marks the transcript idle gate so an INFO caption cannot repaint between
    report chunks (purge/list tables) and shear onto the next line.
    """
    with _transcript_lock:
        wrote_tty = False
        with _draw_lock:
            if _last_line or _body is not None:
                _clear_unlocked( advance=False )
            _mark_transcript_unlocked()
            if _heartbeat_active and _stream is not None:
                try:
                    _stream.write( text )
                    _stream.flush()
                    wrote_tty = True
                except Exception:
                    pass
            if wrote_tty and _outer_stdout_is_tty():
                return
        sys.stdout.write( text )
        try:
            sys.stdout.flush()
        except Exception:
            pass


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
    """Drop a stale *event* caption; keep ``working`` + widget until the next INFO.

    Sticky in-progress captions (``show_info(..., sticky=True)`` /
    ``operation_status``) do not age out — they stay until ``clear()`` or a
    newer sticky/operation message replaces them.
    """
    global _body, _message_shown_at
    if _sticky:
        return False
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
    global _message_shown_at, _visible_since, _style, _sleep, _compact
    global _last_transcript_at, _sticky, _pending_is_sticky
    with _draw_lock:
        _cancel_idle_flush_unlocked()
    clear_operation_status( dwell=False )
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
    _compact = False
    _last_transcript_at = 0.0
    _sticky = False
    _pending_is_sticky = False
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
        compact=False,
):
    """Enable quiet console, with TTY heartbeat when appropriate.

    ``quiet_kind`` is ``'warn'`` (``-Q``), ``'error'`` (``-s``), or ``None``.
    ``style`` is ``pulse`` (ECG, default), ``spinner`` (classic ASCII), or
    ``off`` (classic quiet, no status line). ``compact`` (terse builds) uses
    ``<widget>  → <message>`` instead of ``working <widget>  <message>``.

    Without a TTY, keep classic quiet levels. With ``--terse-output``, the
    heartbeat still runs so long waits between transcript lines stay alive;
    terse writers clear this line before each stdout write.

    Status text is truncated to the **TTY** width (not piped stdout). Autowrap
    is disabled while the status line is shown so a mis-sized width cannot
    leave wrapped debris. Captions age out after one full animation cycle;
    a new INFO always replaces the caption immediately.
    """
    from cuppa.log import set_logging_level

    global _quiet_console, _suppress_below, _heartbeat_active
    global _stream, _owns_stream, _clock, _columns, _pulse_enabled, _style, _sleep
    global _compact

    chosen_style = normalize_style( style )
    reset()
    _style = chosen_style
    _compact = bool( compact )
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

    if chosen_style == _STYLE_OFF:
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


def clear_operation_status( dwell=True ):
    """Erase a terse-without-quiet ``operation_status`` row, if any."""
    global _operation_stop, _operation_stream, _operation_owns
    global _operation_last, _operation_painted, _operation_since
    with _operation_lock:
        stop = _operation_stop
        stream = _operation_stream
        owns = _operation_owns
        painted = _operation_painted
        since = _operation_since
        _operation_stop = None
        _operation_stream = None
        _operation_owns = False
        _operation_last = ''
        _operation_painted = False
        _operation_since = None
    if stop is not None:
        stop.set()
    if not painted or stream is None:
        if owns and stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        return
    if dwell and since is not None:
        remaining = max( 0.0, _cycle_duration_s() - ( _clock() - since ) )
        if remaining > 0:
            _sleep( remaining )
    try:
        stream.write( '\r' + _ERASE_EOL + _WRAP_ON )
        stream.flush()
    except Exception:
        pass
    if owns:
        try:
            stream.close()
        except Exception:
            pass


@contextmanager
def operation_status( message ):
    """Keep the console alive during a long wait (git update, clone, …).

    Location retrieve uses pip's quiet ``git fetch``, so Cuppa owns no byte
    bar there. This arms the same alive presentation the transfer engine uses:

    * **Quiet diverting** — caption on the heartbeat (idle-gate aware, like INFO).
    * **Terse + TTY** (not quiet) — alive + ``→`` + message after the idle gate;
      pulse while waiting; dwell one cycle and clear on exit (and before any
      terse transcript line via ``write_transcript``).
    * **Otherwise** — no-op (callers still ``logger.info`` when not terse).

    Under ``--terse-output`` the retrieve path skips multi-line INFO so the
    heartbeat would never see a start trigger without this helper.
    """
    from cuppa.output_processor import strip_ansi

    text = strip_ansi( ( message or '' ).replace( '\n', ' ' ) ).strip()
    if not text:
        yield
        return

    if diverting():
        # In-progress: keep the caption until we clear (do not age out to pulse-only).
        show_info( text, sticky=True )
        try:
            yield
        finally:
            ensure_min_dwell()
            clear()
        return

    if not _compact or _style == _STYLE_OFF:
        yield
        return

    from cuppa.utility.download import open_progress_stream

    # Replace any prior operation_status before starting a new one.
    clear_operation_status( dwell=False )

    stream, is_tty, owns = open_progress_stream()
    if not is_tty:
        if owns and stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        yield
        return

    stop = threading.Event()
    spin = [ 0 ]

    def _paint():
        global _operation_last, _operation_painted, _operation_since
        from cuppa.colourise import as_subdued
        from cuppa.output_processor import strip_ansi as _strip

        if stop.is_set():
            return
        plain_prefix, styled_prefix = format_alive_prefix(
                spin[0], style=_style, compact=True,
        )
        cols = _terminal_columns()
        budget = max( 1, cols - len( plain_prefix ) )
        fitted = _fit_plain( _strip( text ), budget )
        line = styled_prefix + as_subdued( fitted )
        with _operation_lock:
            # Cleared or superseded by another operation_status / transcript.
            if _operation_stream is not stream or stop.is_set():
                return
            try:
                # Same protocol as quiet heartbeat: no wrap, erase tail.
                stream.write( _WRAP_OFF + '\r' + line + _ERASE_EOL )
                stream.flush()
            except Exception:
                return
            if not _operation_painted:
                _operation_painted = True
                _operation_since = _clock()
            _operation_last = line
        spin[0] += 1

    def _run():
        deadline = _clock() + _IDLE_GATE_S
        while _clock() < deadline:
            if stop.is_set():
                return
            _sleep( min( 0.02, deadline - _clock() ) )
        if stop.is_set():
            return
        while not stop.is_set():
            _paint()
            if _style == _STYLE_PULSE and _pulse_frame( spin[0] ) == _PULSE_REST:
                delay = _PULSE_REST_INTERVAL_S
            else:
                delay = _PULSE_INTERVAL_S
            end = _clock() + delay
            while _clock() < end and not stop.is_set():
                _sleep( min( 0.02, end - _clock() ) )

    with _operation_lock:
        global _operation_stop, _operation_stream, _operation_owns
        global _operation_last, _operation_painted, _operation_since
        _operation_stop = stop
        _operation_stream = stream
        _operation_owns = bool( owns )
        _operation_last = ''
        _operation_painted = False
        _operation_since = None

    thread = threading.Thread( target=_run, name='cuppa-operation-status' )
    thread.daemon = True
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join( timeout=2.0 )
        clear_operation_status( dwell=True )


def show_info( message, sticky=False ):
    """Rewrite the status line with the latest INFO message (throttled).

    While a recent transcript write keeps the idle gate closed, only the
    latest message is remembered — it paints once the gate opens so a fast
    ``terse–info–terse`` stream cannot force full-cycle dwells.

    ``sticky=True`` marks an **in-progress** caption (see ``operation_status``):
    it does not age out to the pulse-only anchor. Ordinary INFO stays
    event-style and ages out after the caption hold. A non-sticky INFO while
    a sticky caption is held is remembered as pending and does not steal the
    row; a newer sticky message replaces the current one.
    """
    global _pending, _pending_is_sticky
    if not _heartbeat_active or _stream is None:
        return
    text = ( message or '' ).replace( '\n', ' ' ).strip()
    if not text:
        return
    with _draw_lock:
        if _sticky and not sticky:
            # Keep the in-progress caption; coalesce event INFO for after clear.
            _pending = text
            _pending_is_sticky = False
            return
        _pending = text
        _pending_is_sticky = bool( sticky )
        if _suppress_depth:
            # Remember for after the spawn; do not fight the transcript.
            return
        now = _clock()
        if not _transcript_is_idle( now ):
            _arm_idle_flush_unlocked()
            return
        # Sticky in-progress captions skip the event INFO throttle so a long
        # wait arms immediately once the transcript idle gate is open.
        if (
                not sticky
                and _last_emit
                and ( now - _last_emit ) < _MESSAGE_INTERVAL_S
        ):
            return
        _flush_unlocked( now )


def flush_pending():
    """Emit a deferred status line when the transcript idle gate is open."""
    with _draw_lock:
        if _pending is None or _suppress_depth:
            return
        now = _clock()
        if not _transcript_is_idle( now ):
            _arm_idle_flush_unlocked()
            return
        if (
                not _pending_is_sticky
                and _last_emit
                and ( now - _last_emit ) < _MESSAGE_INTERVAL_S
        ):
            return
        _flush_unlocked( now )


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

    No-op when nothing is on the status row. Keeps an unpainted pending INFO
    for the idle gate (same as ``write_transcript``).
    """
    with _draw_lock:
        if not _last_line and _body is None:
            return
    ensure_min_dwell()
    with _draw_lock:
        if not _last_line and _body is None:
            return
        _mark_transcript_unlocked()
        _clear_unlocked( advance=False, keep_pending=True )


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
        ensure_min_dwell()
    with _draw_lock:
        _suppress_depth += 1
        _mark_transcript_unlocked()
        _clear_unlocked( advance=advance, keep_pending=True )


def allow():
    """End a ``suppress()`` region.

    Does **not** redraw immediately: the launcher may still be flushing the
    command we wrote to the stdout pipe. A pending INFO paints after the
    transcript idle gate (or on the next ``show_info`` once idle).
    """
    global _suppress_depth
    with _draw_lock:
        if _suppress_depth > 0:
            _suppress_depth -= 1
        if _suppress_depth == 0 and _pending is not None:
            _arm_idle_flush_unlocked()


def _clear_unlocked( advance=False, keep_pending=False ):
    global _pending, _body, _last_line, _last_emit, _wrap_disabled
    global _message_shown_at, _visible_since, _sticky, _pending_is_sticky
    _cancel_pulse()
    # Keep ``_pending`` when suppressing or clearing for transcript so INFO
    # during a busy stream can show after the idle gate; warn/report drops it.
    if not keep_pending:
        _pending = None
        _pending_is_sticky = False
        _cancel_idle_flush_unlocked()
    _body = None
    _sticky = False
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
    global _sticky, _pending_is_sticky
    if _pending is None or _stream is None or _suppress_depth:
        return
    _body = _pending
    _sticky = bool( _pending_is_sticky )
    _pending = None
    _pending_is_sticky = False
    _message_shown_at = now
    _spin += 1
    _draw_unlocked( _body )
    _last_emit = now
    _arm_pulse()


def _draw_unlocked( body ):
    """Write one status line fitted to the TTY width."""
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
        # Anchor only — no arrow/gap after the widget.
        if _style == _STYLE_SPINNER:
            styled = as_subdued( _WORKING + ' ' ) + _animation_styled()
        else:
            styled = _animation_styled()
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
