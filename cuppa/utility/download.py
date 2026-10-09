#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""HTTP file transfer helpers with a shared progress reporter.

Downloads (location / toolchain / GitLab collect) and uploads (GitLab publish)
share ``ProgressReporter``. See ``design/archive/download-progress.md`` and
``design/plans/transfer-and-archive-progress.md``.

Progress prefers the controlling terminal (``/dev/tty`` / ``CONOUT$``) so a
rewriting line still works when the ``cuppa`` launcher pipes scons stdout/stderr
for secret masking — those pipes are not TTYs and are consumed line-by-line.
"""

from __future__ import print_function

import os
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError

from cuppa.colourise import as_emphasised, as_info, as_subdued
from cuppa.utility.python2to3 import Exception as CuppaException
from cuppa.utility.storage import human_size, pad_visible, visible_len


class DownloadError( CuppaException ):
    def __init__( self, value, http_status=None ):
        self.parameter = value
        self.http_status = http_status

    def __str__( self ):
        return repr( self.parameter )


class UploadError( CuppaException ):
    """HTTP PUT / upload failure (registry publish, etc.)."""

    def __init__( self, value, http_status=None, body=None ):
        self.parameter = value
        self.http_status = http_status
        self.body = body

    def __str__( self ):
        return repr( self.parameter )


def is_http_not_found( error ):
    """True when ``error`` is a missing HTTP resource (404)."""
    status = getattr( error, 'http_status', None )
    if status == 404:
        return True
    cause = getattr( error, '__cause__', None )
    if getattr( cause, 'code', None ) == 404:
        return True
    if isinstance( error, HTTPError ) and getattr( error, 'code', None ) == 404:
        return True
    return False


_CHUNK_SIZE = 256 * 1024
_TTY_INTERVAL_S = 0.35
_LINE_INTERVAL_S = 2.0
_LINE_PERCENT_STEP = 5

# Active TTY progress bar (compress/upload/download). Transcript writers clear
# this before printing so ``Compressing …`` cannot shear onto cmake ``→`` lines.
_active_progress = None


def register_active_progress( reporter ):
    """Remember the live ``ProgressReporter`` so transcript can wipe its row."""
    global _active_progress
    _active_progress = reporter


def clear_active_progress():
    """Blank the active progress bar row without finishing the transfer."""
    reporter = _active_progress
    if reporter is None:
        return
    try:
        reporter.interrupt_clear()
    except Exception:
        pass


def format_duration( seconds ):
    """Compact ETA / elapsed for progress lines (``45s``, ``6m20s``, ``1h05m``)."""
    if seconds is None or seconds < 0 or seconds != seconds:  # NaN
        return '--'
    total = int( round( seconds ) )
    if total < 60:
        return "{}s".format( total )
    minutes, secs = divmod( total, 60 )
    if minutes < 60:
        return "{}m{:02d}s".format( minutes, secs )
    hours, minutes = divmod( minutes, 60 )
    return "{}h{:02d}m".format( hours, minutes )


# Fixed field widths so rewriting TTY lines do not shift columns as values grow.
_SIZE_WIDTH = 7   # e.g. "159.5M", "    0B"
_RATE_WIDTH = 8   # e.g. "109.1M/s", "     0B/s"
_ETA_WIDTH = 3    # e.g. "15s", " 9s", " --"
_BAR_WIDTH = 20   # cells inside ``[`` ``]``


def _as_emphasised_info( text ):
    """Bright info colour (percent, bar fill, completed done size)."""
    return as_emphasised( as_info( text ) )


def format_progress_bar( percent, width=_BAR_WIDTH, started=True ):
    """ASCII bar ``[…]``; fill is emphasised info colour, brackets are plain.

    Not started: empty fill. Started at 0%: tip ``>``. In progress: ``=`` run
    plus tip. Complete: solid ``=``.
    """
    if width < 1:
        width = 1
    if percent >= 100.0:
        fill = '=' * width
    elif not started:
        fill = ' ' * width
    else:
        filled = int( round( percent * width / 100.0 ) )
        if filled <= 0:
            fill = '>' + ' ' * ( width - 1 )
        else:
            # Keep a tip cell until the transfer completes.
            filled = min( filled, width - 1 )
            fill = ( '=' * filled ) + '>' + ( ' ' * ( width - filled - 1 ) )
    if fill.strip():
        # Colour only the glyph run; trailing spaces stay plain so empty cells
        # do not carry a lingering style into the closing bracket.
        glyphs = fill.rstrip( ' ' )
        spaces = ' ' * ( len( fill ) - len( glyphs ) )
        return '[' + _as_emphasised_info( glyphs ) + spaces + ']'
    return '[' + fill + ']'


def format_progress_line(
        label, bytes_so_far, total_size, elapsed_s, action='Downloading', started=True,
        *, compact=False, muted=False, include_bar=None,
):
    """One progress line (no trailing newline). Shared TTY and non-TTY shape.

    Known size: ``percent [bar] done/total rate ETA``. Percent and bar fill use
    emphasised info colour; target size is emphasised only (normal foreground);
    transferred size is info (also emphasised at 100%); rate is subdued.
    Fields are padded before ANSI wraps so columns stay aligned.

    ``compact`` drops the ASCII bar (terse / narrow status). ``muted`` subdues
    colours for quiet console. ``include_bar`` overrides the compact default.
    """
    if include_bar is None:
        include_bar = not compact
    rate = ( float( bytes_so_far ) / elapsed_s ) if elapsed_s > 0 else 0.0
    rate_text = as_subdued( "{}/s".format( human_size( rate ) ).rjust( _RATE_WIDTH ) )
    done_text = human_size( bytes_so_far ).rjust( _SIZE_WIDTH )
    verb = action or 'Downloading'
    # Terse/quiet: subdue the progress *body* (verb, label, metrics, bar).
    # Alive ECG stays hospital-green via ``format_alive_prefix`` — do not mute it.
    if muted:
        verb = as_subdued( verb )
        label = as_subdued( label )

    def _paint_info( text ):
        if muted:
            return as_subdued( text )
        return as_info( text )

    def _paint_emph_info( text ):
        if muted:
            return as_subdued( text )
        return _as_emphasised_info( text )

    def _paint_emph( text ):
        if muted:
            return as_subdued( text )
        return as_emphasised( text )

    if total_size and total_size > 0:
        percent = min( 100.0, 100.0 * float( bytes_so_far ) / float( total_size ) )
        remaining = max( 0.0, float( total_size ) - float( bytes_so_far ) )
        eta = ( remaining / rate ) if rate > 0 else None
        percent_text = _paint_emph_info( "{:3.0f}%".format( percent ) )
        if percent >= 100.0:
            done = _paint_emph_info( done_text )
        else:
            done = _paint_info( done_text )
        total = _paint_emph( human_size( total_size ) )
        if include_bar:
            if muted:
                bar = _muted_progress_bar( percent, started=started )
            else:
                bar = format_progress_bar( percent, started=started )
            return "{} {}  {} {}  {}/{}  {}  ETA {}".format(
                    verb,
                    label,
                    percent_text,
                    bar,
                    done,
                    total,
                    rate_text,
                    format_duration( eta ).rjust( _ETA_WIDTH ),
            )
        return "{} {}  {}  {}/{}  {}  ETA {}".format(
                verb,
                label,
                percent_text,
                done,
                total,
                rate_text,
                format_duration( eta ).rjust( _ETA_WIDTH ),
        )
    return "{} {}  {} transferred  {}".format(
            verb, label, _paint_info( done_text ), rate_text,
    )


def _muted_progress_bar( percent, width=_BAR_WIDTH, started=True ):
    """ASCII bar with subdued fill (quiet transfer status)."""
    if width < 1:
        width = 1
    if percent >= 100.0:
        fill = '=' * width
    elif not started:
        fill = ' ' * width
    else:
        filled = int( round( percent * width / 100.0 ) )
        if filled <= 0:
            fill = '>' + ' ' * ( width - 1 )
        else:
            filled = min( filled, width - 1 )
            fill = ( '=' * filled ) + '>' + ( ' ' * ( width - filled - 1 ) )
    if fill.strip():
        glyphs = fill.rstrip( ' ' )
        spaces = ' ' * ( len( fill ) - len( glyphs ) )
        return '[' + as_subdued( glyphs ) + spaces + ']'
    return '[' + fill + ']'


def open_progress_stream():
    """Return ``(stream, is_tty, owns_stream)`` for progress output.

    Prefer the controlling terminal so rewriting works under the ``cuppa``
    launcher (piped scons stdio). Fall back to ``sys.stderr`` with newline mode
    when there is no tty (CI).
    """
    candidates = ( 'CONOUT$', ) if sys.platform == 'win32' else ( '/dev/tty', )
    for path in candidates:
        try:
            stream = open( path, 'w' )
        except ( OSError, IOError ):
            continue
        try:
            if stream.isatty():
                return stream, True, True
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    stream = sys.stderr
    is_tty = False
    try:
        is_tty = bool( stream.isatty() )
    except Exception:
        is_tty = False
    if not is_tty:
        try:
            is_tty = os.isatty( 2 )
        except Exception:
            is_tty = False
    return stream, is_tty, False


class ProgressReporter( object ):
    """Throttle and render transfer progress on a stream (tty or stderr).

    Mode-tuned (see ``transfer-and-archive-progress``):

    * **Normal TTY** — progress bar only (no alive widget); full colour; show
      immediately; durable final 100% line.
    * **Normal + quiet TTY** — same shape, muted; idle-gate reveal; overwrite
      (clear) on completion.
    * **Terse TTY** — alive (unless ``off``) + ``→`` + progress bar, muted;
      idle-gate reveal; overwrite on completion after one animation dwell.
    * **Non-TTY** — periodic lines in **normal** only (silent under terse).
    """

    def __init__(
            self,
            stream=None,
            is_tty=None,
            clock=None,
            sleep=None,
            tty_interval_s=_TTY_INTERVAL_S,
            line_interval_s=_LINE_INTERVAL_S,
            line_percent_step=_LINE_PERCENT_STEP,
            action='Downloading',
            owns_stream=False,
            compact=None,
            muted=None,
            alive_style=None,
    ):
        if stream is None:
            stream, detected_tty, owns_stream = open_progress_stream()
            if is_tty is None:
                is_tty = detected_tty
        self._stream = stream
        self._owns_stream = owns_stream
        self._clock = clock if clock is not None else time.time
        self._sleep = sleep if sleep is not None else time.sleep
        if is_tty is None:
            is_tty = bool( getattr( self._stream, 'isatty', lambda: False )() )
        self._is_tty = is_tty
        self._tty_interval_s = tty_interval_s
        self._line_interval_s = line_interval_s
        self._line_percent_step = line_percent_step
        self._action = action or 'Downloading'
        self._label = ''
        self._total = None
        self._started = None
        self._bar_started = False
        self._last_emit = None
        self._next_line_percent = line_percent_step
        self._last_line = ''
        self._finished = False
        self._spin = 0
        self._alive_style_override = alive_style
        self._compact_override = compact
        self._muted_override = muted
        self._ever_painted = False
        self._visible_since = None
        self._resolve_presentation()

    def _resolve_presentation( self ):
        from cuppa.utility import heartbeat as hb
        if self._alive_style_override is None:
            self._alive_style = hb.style()
        else:
            self._alive_style = self._alive_style_override
        if self._compact_override is None:
            self._compact = hb.compact()
        else:
            self._compact = bool( self._compact_override )
        quiet = hb.muted()
        terse = bool( self._compact )
        if self._muted_override is None:
            # Terse progress is always muted; quiet mutes normal too.
            self._muted = terse or quiet
        else:
            self._muted = bool( self._muted_override )
        # Alive only under terse + TTY (unless style off).
        self._show_alive = (
                bool( self._is_tty ) and terse and self._alive_style != 'off'
        )
        self._terse = terse
        self._quiet = quiet
        # Idle reveal: terse always; normal only when quiet. Plain normal = immediate.
        self._use_reveal_gate = bool( self._is_tty ) and ( terse or quiet )
        self._overwrite_on_done = bool( self._is_tty ) and ( terse or quiet )
        # Non-TTY periodic lines only outside terse.
        self._emit_non_tty = ( not self._is_tty ) and ( not terse )

    def _compose_line( self, bytes_so_far, elapsed, started ):
        # Always include the bar on TTY (terse keeps bar; compact only affects alive).
        body = format_progress_line(
                self._label,
                bytes_so_far,
                self._total,
                elapsed,
                action=self._action,
                started=started,
                compact=False,
                muted=bool( self._muted ),
                include_bar=True,
        )
        if not self._is_tty or not self._terse:
            return body
        from cuppa.utility.heartbeat import format_alive_prefix
        if self._show_alive:
            _plain, styled_prefix = format_alive_prefix(
                    self._spin,
                    style=self._alive_style,
                    compact=True,
            )
            return styled_prefix + body
        # Terse + alive off: still arrow-align the progress bar.
        try:
            from cuppa.progress import terse_arrow_column
            indent = max( 0, int( terse_arrow_column() ) )
        except Exception:
            indent = 14
        from cuppa.colourise import as_subdued
        return as_subdued( ( ' ' * indent ) + '→ ' ) + body

    def begin( self, label, total_size=None, action=None ):
        from cuppa.utility import heartbeat as hb
        try:
            hb.clear()
        except Exception:
            pass
        register_active_progress( self )
        self._resolve_presentation()
        self._label = label or 'transfer'
        if action is not None:
            self._action = action
        self._total = total_size if total_size and total_size > 0 else None
        self._started = self._clock()
        self._last_emit = None
        self._next_line_percent = self._line_percent_step
        self._last_line = ''
        self._finished = False
        self._spin = 0
        self._ever_painted = False
        self._visible_since = None
        self._bar_started = True
        if not self._use_reveal_gate:
            # Immediate arm: empty tip then started tip (classic download look).
            self._bar_started = False
            self.update( 0, force=True )
            self._bar_started = True
            self.update( 0, force=True )

    def update( self, bytes_so_far, force=False ):
        if self._finished:
            return
        if not self._is_tty and not self._emit_non_tty:
            return
        now = self._clock()
        elapsed = max( 0.0, now - ( self._started or now ) )
        if self._use_reveal_gate:
            from cuppa.utility.heartbeat import idle_gate_s
            if elapsed < idle_gate_s():
                return
        if not force and self._last_emit is not None:
            if self._is_tty:
                if ( now - self._last_emit ) < self._tty_interval_s:
                    return
            else:
                percent_due = False
                if self._total:
                    percent = 100.0 * float( bytes_so_far ) / float( self._total )
                    if percent >= self._next_line_percent:
                        percent_due = True
                time_due = ( now - self._last_emit ) >= self._line_interval_s
                if not percent_due and not time_due:
                    return
                if percent_due and self._total:
                    while self._next_line_percent <= (
                            100.0 * float( bytes_so_far ) / float( self._total )
                    ):
                        self._next_line_percent += self._line_percent_step

        if self._show_alive:
            self._spin += 1
        line = self._compose_line( bytes_so_far, elapsed, started=self._bar_started )
        self._emit( line, newline=not self._is_tty )
        self._last_emit = now
        self._last_line = line
        if not self._ever_painted:
            self._ever_painted = True
            self._visible_since = now

    def _emit( self, line, newline ):
        if self._is_tty:
            width = max( visible_len( self._last_line ), visible_len( line ) )
            self._stream.write( '\r' + pad_visible( line, width ) )
            if newline:
                self._stream.write( '\n' )
        else:
            self._stream.write( line )
            self._stream.write( '\n' )
        try:
            self._stream.flush()
        except Exception:
            pass

    def _clear_line( self ):
        if not self._is_tty or not self._last_line:
            return
        width = visible_len( self._last_line )
        self._stream.write( '\r' + ( ' ' * width ) + '\r' )
        try:
            self._stream.flush()
        except Exception:
            pass
        self._last_line = ''

    def interrupt_clear( self ):
        """Wipe the rewriting row so a transcript line can own the TTY."""
        self._clear_line()

    def done( self, bytes_so_far=None ):
        global _active_progress
        if self._finished:
            return
        self._finished = True
        if _active_progress is self:
            _active_progress = None
        if bytes_so_far is None:
            bytes_so_far = 0
        now = self._clock()
        elapsed = max( 0.0, now - ( self._started or now ) )
        if self._ever_painted:
            if self._show_alive and self._visible_since is not None:
                from cuppa.utility.heartbeat import cycle_duration_s
                remaining = max(
                        0.0,
                        cycle_duration_s() - ( now - self._visible_since ),
                )
                if remaining > 0:
                    self._sleep( remaining )
                    now = self._clock()
                    elapsed = max( 0.0, now - ( self._started or now ) )
            if self._overwrite_on_done:
                self._clear_line()
            else:
                if self._show_alive:
                    self._spin += 1
                line = self._compose_line( bytes_so_far, elapsed, started=True )
                self._emit( line, newline=True )
                self._last_line = line
        try:
            from cuppa.utility import heartbeat as hb
            hb.clear()
        except Exception:
            pass
        if self._owns_stream:
            try:
                self._stream.close()
            except Exception:
                pass
            self._owns_stream = False


def _content_length( response ):
    headers = getattr( response, 'headers', None ) or getattr( response, 'info', lambda: {} )()
    try:
        value = headers.get( 'Content-Length' )
    except AttributeError:
        value = None
    if value is None:
        return None
    try:
        length = int( value )
    except ( TypeError, ValueError ):
        return None
    return length if length > 0 else None


def _maybe_reporter( show_progress, reporter, action ):
    if show_progress is None:
        from cuppa.utility.heartbeat import transfer_progress_allowed
        show_progress = transfer_progress_allowed()
    if not show_progress:
        return None
    if reporter is not None:
        return reporter
    return ProgressReporter( action=action )


def transfer_file( path, consumer, *, label=None, action='Extracting', show_progress=None, reporter=None ):
    """Read ``path`` in chunks, pass each to ``consumer(chunk)``, report progress.

    ``consumer`` should write/process the bytes (for example ``proc.stdin.write``).
    Returns the number of bytes read.
    """
    progress = _maybe_reporter( show_progress, reporter, action )
    display = label or os.path.basename( path ) or path
    total = None
    try:
        total = os.path.getsize( path )
    except OSError:
        total = None
    bytes_so_far = 0
    if progress:
        progress.begin( display, total, action=action )
    try:
        with open( path, 'rb' ) as handle:
            while True:
                chunk = handle.read( _CHUNK_SIZE )
                if not chunk:
                    break
                consumer( chunk )
                bytes_so_far += len( chunk )
                if progress:
                    progress.update( bytes_so_far )
        if progress:
            progress.done( bytes_so_far )
        return bytes_so_far
    except Exception:
        if progress is not None:
            try:
                progress.done( bytes_so_far )
            except Exception:
                pass
        raise


def tar_stdin_argv( archive_path, extract_root ):
    """``tar`` argv to extract ``archive_path`` from stdin into ``extract_root``."""
    name = os.path.basename( archive_path ).lower()
    if name.endswith( '.tar.xz' ) or name.endswith( '.txz' ):
        return [ 'tar', '-xJf', '-', '-C', extract_root ]
    if name.endswith( '.tar.gz' ) or name.endswith( '.tgz' ):
        return [ 'tar', '-xzf', '-', '-C', extract_root ]
    if name.endswith( '.tar.bz2' ) or name.endswith( '.tbz2' ) or name.endswith( '.tbz' ):
        return [ 'tar', '-xjf', '-', '-C', extract_root ]
    if name.endswith( '.tar.zst' ) or name.endswith( '.tzst' ):
        return [ 'tar', '--zstd', '-xf', '-', '-C', extract_root ]
    if name.endswith( '.tar.lzma' ):
        return [ 'tar', '--lzma', '-xf', '-', '-C', extract_root ]
    return [ 'tar', '-xf', '-', '-C', extract_root ]


def _extract_tar_via_tarfile( archive_path, extract_root ):
    with tarfile.open( archive_path, 'r:*' ) as handle:
        handle.extractall( extract_root )


def extract_tar_archive(
        archive_path,
        extract_root,
        *,
        label=None,
        show_progress=None,
        reporter=None,
):
    """Extract a tar archive into ``extract_root`` with byte progress when possible.

    Streams the archive into ``tar`` on stdin (same reporter shape as downloads).
    Falls back to ``tarfile`` without progress when ``tar`` is not on PATH.
    """
    if not os.path.isdir( extract_root ):
        os.makedirs( extract_root )

    which = getattr( shutil, 'which', None )
    if which is not None and which( 'tar' ) is None:
        _extract_tar_via_tarfile( archive_path, extract_root )
        return extract_root

    proc = subprocess.Popen(
            tar_stdin_argv( archive_path, extract_root ),
            stdin=subprocess.PIPE,
    )
    try:
        transfer_file(
                archive_path,
                proc.stdin.write,
                label=label or os.path.basename( archive_path ) or archive_path,
                action='Extracting',
                show_progress=show_progress,
                reporter=reporter,
        )
        proc.stdin.close()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        proc.wait()
        raise
    if proc.wait() != 0:
        raise DownloadError(
            "tar failed to extract [{}] into [{}]".format( archive_path, extract_root )
        )
    return extract_root


def _zip_member_is_dir( member ):
    is_dir = getattr( member, 'is_dir', None )
    if callable( is_dir ):
        return is_dir()
    name = member.filename
    return bool( name ) and name[-1] in '/\\'


def extract_zip_archive(
        archive_path,
        extract_root,
        *,
        label=None,
        show_progress=None,
        reporter=None,
):
    """Extract a zip archive into ``extract_root`` with uncompressed-byte progress.

    Walks members with ``ZipFile.extract`` (path sanitisation from zipfile) and
    advances the shared reporter by each member's ``file_size``.
    """
    if not os.path.isdir( extract_root ):
        os.makedirs( extract_root )

    progress = _maybe_reporter( show_progress, reporter, 'Extracting' )
    display = label or os.path.basename( archive_path ) or archive_path
    bytes_so_far = 0
    try:
        with zipfile.ZipFile( archive_path ) as handle:
            members = handle.infolist()
            total = sum( member.file_size for member in members )
            if progress:
                progress.begin(
                        display,
                        total if total > 0 else None,
                        action='Extracting',
                )
            for member in members:
                handle.extract( member, extract_root )
                if not _zip_member_is_dir( member ):
                    bytes_so_far += member.file_size
                    if progress:
                        progress.update( bytes_so_far )
            if progress:
                progress.done( bytes_so_far )
    except DownloadError:
        raise
    except Exception as error:
        if progress is not None:
            try:
                progress.done( bytes_so_far )
            except Exception:
                pass
        raise DownloadError(
            "zip failed to extract [{}] into [{}]: {}".format(
                    archive_path, extract_root, error
            )
        )
    return extract_root


def http_head( url, headers=None ):
    """Issue an HTTP HEAD for ``url``.

    Returns ``(status_code, headers_mapping)`` where header names are lower-case.
    Raises ``DownloadError`` on transport failure. A non-2xx/3xx status is still
    returned (callers decide whether 404 means missing).
    """
    request = Request( url, method='HEAD' )
    if headers:
        for name, value in headers.items():
            if name is None or value is None:
                continue
            request.add_header( str( name ), str( value ) )
    try:
        response = urlopen( request )
        try:
            status = getattr( response, 'status', None )
            if status is None:
                status = response.getcode()
            raw = getattr( response, 'headers', None )
            mapping = {}
            if raw is not None:
                try:
                    items = raw.items()
                except Exception:
                    items = []
                for name, value in items:
                    if name is None:
                        continue
                    mapping[ str( name ).lower() ] = value
            return int( status ), mapping
        finally:
            try:
                response.close()
            except Exception:
                pass
    except HTTPError as error:
        raw = getattr( error, 'headers', None )
        mapping = {}
        if raw is not None:
            try:
                for name, value in raw.items():
                    if name is None:
                        continue
                    mapping[ str( name ).lower() ] = value
            except Exception:
                pass
        return int( getattr( error, 'code', 0 ) or 0 ), mapping
    except Exception as error:
        wrapped = DownloadError(
                "failed to HEAD [{}]: {}".format( url, error ),
                http_status=getattr( error, 'code', None ),
        )
        wrapped.__cause__ = error
        raise wrapped


def download_file(
        url,
        dest_path,
        *,
        label=None,
        show_progress=None,
        reporter=None,
        headers=None,
):
    """Download ``url`` to ``dest_path`` via a ``.partial`` file then rename.

    ``show_progress`` defaults to True when multi-line progress is allowed
    (INFO or finer, and not under quiet console).
    Pass an existing ``ProgressReporter`` for tests; otherwise one is created on the
    progress stream (controlling tty when available).

    ``headers`` is an optional mapping of HTTP header name to value (for example
    GitLab ``PRIVATE-TOKEN`` / ``JOB-TOKEN``). Header values must not appear in
    ``label`` or other logged progress text.
    """
    progress = _maybe_reporter( show_progress, reporter, 'Downloading' )

    parent = os.path.dirname( dest_path )
    if parent and not os.path.isdir( parent ):
        os.makedirs( parent )

    tmp_path = dest_path + '.partial'
    display = label or os.path.basename( dest_path ) or url

    bytes_so_far = 0
    try:
        request = Request( url )
        if headers:
            for name, value in headers.items():
                if name is None or value is None:
                    continue
                request.add_header( str( name ), str( value ) )
        response = urlopen( request )
        try:
            total = _content_length( response )
            if progress:
                progress.begin( display, total, action='Downloading' )
            with open( tmp_path, 'wb' ) as handle:
                while True:
                    chunk = response.read( _CHUNK_SIZE )
                    if not chunk:
                        break
                    handle.write( chunk )
                    bytes_so_far += len( chunk )
                    if progress:
                        progress.update( bytes_so_far )
            if total is not None and bytes_so_far < total:
                raise DownloadError(
                    "retrieval incomplete: got only {} out of {} bytes from [{}]".format(
                        bytes_so_far, total, url
                    )
                )
        finally:
            try:
                response.close()
            except Exception:
                pass

        if progress:
            progress.done( bytes_so_far )
        if os.path.isfile( dest_path ):
            os.remove( dest_path )
        os.rename( tmp_path, dest_path )
        return dest_path
    except Exception as error:
        if progress is not None:
            try:
                progress.done( bytes_so_far )
            except Exception:
                pass
        if os.path.isfile( tmp_path ):
            try:
                os.remove( tmp_path )
            except OSError:
                pass
        if isinstance( error, DownloadError ):
            raise
        status = getattr( error, 'code', None )
        wrapped = DownloadError(
            "failed to download [{}]: {}".format( url, error ),
            http_status=status,
        )
        wrapped.__cause__ = error
        raise wrapped


class _ProgressFileReader( object ):
    """File body for ``urlopen`` that advances ``ProgressReporter`` as bytes leave.

    ``urllib`` reads from this object while sending the PUT, so ``read`` is a
    faithful upload progress signal (same idea as ``transfer_file``).
    """

    def __init__( self, path, progress=None, chunk_size=_CHUNK_SIZE ):
        self._handle = open( path, 'rb' )
        self._progress = progress
        self._chunk_size = chunk_size if chunk_size and chunk_size > 0 else _CHUNK_SIZE
        self._sent = 0
        try:
            self._total = os.path.getsize( path )
        except OSError:
            self._total = 0

    def __len__( self ):
        return int( self._total )

    def read( self, size=-1 ):
        if size is None or size < 0:
            size = self._chunk_size
        chunk = self._handle.read( size )
        if chunk:
            self._sent += len( chunk )
            if self._progress is not None:
                self._progress.update( self._sent )
        return chunk

    def close( self ):
        try:
            self._handle.close()
        except Exception:
            pass


def _http_error_body( error ):
    """Best-effort response body text from an ``HTTPError`` (fail-with-body)."""
    try:
        raw = error.read()
    except Exception:
        return ""
    if raw is None:
        return ""
    if isinstance( raw, bytes ):
        try:
            return raw.decode( 'utf-8', 'replace' )
        except Exception:
            return repr( raw )
    return str( raw )


def upload_file(
        url,
        source_path,
        *,
        label=None,
        show_progress=None,
        reporter=None,
        headers=None,
):
    """Upload ``source_path`` to ``url`` with an HTTP PUT and shared progress.

    Mirrors ``download_file`` for registry publish: same ``ProgressReporter``,
    auth ``headers``, and controlling-TTY rewrite. Sets ``Content-Length`` and
    ``Content-Type: application/octet-stream`` (urllib would otherwise default
    form-urlencoded). Non-2xx responses raise ``UploadError`` with status and
    body when available (curl ``--fail-with-body`` equivalent).

    Returns ``source_path`` on success.
    """
    if not os.path.isfile( source_path ):
        raise UploadError(
            "upload source missing [{}]".format( source_path )
        )

    progress = _maybe_reporter( show_progress, reporter, 'Uploading' )
    display = label or os.path.basename( source_path ) or url
    total = os.path.getsize( source_path )
    body = None
    bytes_so_far = 0

    try:
        if progress:
            progress.begin( display, total if total > 0 else None, action='Uploading' )
        body = _ProgressFileReader( source_path, progress=progress )
        request = Request( url, data=body, method='PUT' )
        # Explicit length + binary type: urllib defaults POST/PUT bodies to
        # application/x-www-form-urlencoded, which GitLab generic packages reject.
        request.add_header( 'Content-Length', str( total ) )
        request.add_header( 'Content-Type', 'application/octet-stream' )
        if headers:
            for name, value in headers.items():
                if name is None or value is None:
                    continue
                request.add_header( str( name ), str( value ) )
        response = urlopen( request )
        try:
            status = getattr( response, 'status', None )
            if status is None:
                status = response.getcode()
            status = int( status )
            # Drain so the connection can close cleanly.
            try:
                response.read()
            except Exception:
                pass
            if status < 200 or status >= 300:
                raise UploadError(
                    "failed to upload [{}] to [{}]: HTTP {}".format(
                            source_path, url, status
                    ),
                    http_status=status,
                )
        finally:
            try:
                response.close()
            except Exception:
                pass
        bytes_so_far = total
        if progress:
            progress.done( bytes_so_far )
        return source_path
    except UploadError:
        if progress is not None:
            try:
                progress.done( getattr( body, '_sent', bytes_so_far ) )
            except Exception:
                pass
        raise
    except HTTPError as error:
        if progress is not None:
            try:
                progress.done( getattr( body, '_sent', bytes_so_far ) )
            except Exception:
                pass
        body_text = _http_error_body( error )
        status = getattr( error, 'code', None )
        detail = body_text.strip() if body_text else str( error )
        wrapped = UploadError(
            "failed to upload [{}] to [{}]: {}".format( source_path, url, detail ),
            http_status=status,
            body=body_text,
        )
        wrapped.__cause__ = error
        raise wrapped
    except Exception as error:
        if progress is not None:
            try:
                progress.done( getattr( body, '_sent', bytes_so_far ) )
            except Exception:
                pass
        if isinstance( error, UploadError ):
            raise
        status = getattr( error, 'code', None )
        wrapped = UploadError(
            "failed to upload [{}] to [{}]: {}".format( source_path, url, error ),
            http_status=status,
        )
        wrapped.__cause__ = error
        raise wrapped
    finally:
        if body is not None:
            try:
                body.close()
            except Exception:
                pass
