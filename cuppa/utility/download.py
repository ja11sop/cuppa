#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""HTTP file downloads with a shared transfer-progress reporter.

Used by location archive fetches and toolchain archives. See
``design/plans/download-progress.md``.

Progress prefers the controlling terminal (``/dev/tty`` / ``CONOUT$``) so a
rewriting line still works when the ``cuppa`` launcher pipes scons stdout/stderr
for secret masking — those pipes are not TTYs and are consumed line-by-line.
"""

from __future__ import print_function

import logging
import os
import shutil
import subprocess
import sys
import tarfile
import time

try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

from cuppa.colourise import as_emphasised, as_info, as_subdued
from cuppa.log import logger
from cuppa.utility.python2to3 import Exception as CuppaException
from cuppa.utility.storage import human_size, pad_visible, visible_len


class DownloadError( CuppaException ):
    def __init__( self, value ):
        self.parameter = value

    def __str__( self ):
        return repr( self.parameter )


_CHUNK_SIZE = 256 * 1024
_TTY_INTERVAL_S = 0.35
_LINE_INTERVAL_S = 2.0
_LINE_PERCENT_STEP = 5


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
):
    """One progress line (no trailing newline). Shared TTY and non-TTY shape.

    Known size: ``percent [bar] done/total rate ETA``. Percent and bar fill use
    emphasised info colour; target size is emphasised only (normal foreground);
    transferred size is info (also emphasised at 100%); rate is subdued.
    Fields are padded before ANSI wraps so columns stay aligned.
    """
    rate = ( float( bytes_so_far ) / elapsed_s ) if elapsed_s > 0 else 0.0
    rate_text = as_subdued( "{}/s".format( human_size( rate ) ).rjust( _RATE_WIDTH ) )
    done_text = human_size( bytes_so_far ).rjust( _SIZE_WIDTH )
    verb = action or 'Downloading'
    if total_size and total_size > 0:
        percent = min( 100.0, 100.0 * float( bytes_so_far ) / float( total_size ) )
        remaining = max( 0.0, float( total_size ) - float( bytes_so_far ) )
        eta = ( remaining / rate ) if rate > 0 else None
        percent_text = _as_emphasised_info( "{:3.0f}%".format( percent ) )
        if percent >= 100.0:
            done = _as_emphasised_info( done_text )
        else:
            done = as_info( done_text )
        total = as_emphasised( human_size( total_size ) )
        return "{} {}  {} {}  {}/{}  {}  ETA {}".format(
                verb,
                label,
                percent_text,
                format_progress_bar( percent, started=started ),
                done,
                total,
                rate_text,
                format_duration( eta ).rjust( _ETA_WIDTH ),
        )
    return "{} {}  {} transferred  {}".format(
            verb, label, as_info( done_text ), rate_text,
    )


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
    """Throttle and render transfer progress on a stream (tty or stderr)."""

    def __init__(
            self,
            stream=None,
            is_tty=None,
            clock=None,
            tty_interval_s=_TTY_INTERVAL_S,
            line_interval_s=_LINE_INTERVAL_S,
            line_percent_step=_LINE_PERCENT_STEP,
            action='Downloading',
            owns_stream=False,
    ):
        if stream is None:
            stream, detected_tty, owns_stream = open_progress_stream()
            if is_tty is None:
                is_tty = detected_tty
        self._stream = stream
        self._owns_stream = owns_stream
        self._clock = clock if clock is not None else time.time
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

    def begin( self, label, total_size=None, action=None ):
        self._label = label or 'transfer'
        if action is not None:
            self._action = action
        self._total = total_size if total_size and total_size > 0 else None
        self._started = self._clock()
        self._last_emit = None
        self._next_line_percent = self._line_percent_step
        self._last_line = ''
        self._finished = False
        # Empty bar (not started), then tip so the transfer looks armed at 0%.
        self._bar_started = False
        self.update( 0, force=True )
        self._bar_started = True
        self.update( 0, force=True )

    def update( self, bytes_so_far, force=False ):
        if self._finished:
            return
        now = self._clock()
        elapsed = max( 0.0, now - ( self._started or now ) )
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

        line = format_progress_line(
                self._label,
                bytes_so_far,
                self._total,
                elapsed,
                action=self._action,
                started=self._bar_started,
        )
        self._emit( line, newline=not self._is_tty )
        self._last_emit = now
        self._last_line = line

    def _emit( self, line, newline ):
        if self._is_tty:
            # Always return to column 0 so done() replaces the last rewrite
            # instead of appending after it. Pad by visible width so ANSI
            # colour codes do not leave trailing glyphs from a longer line.
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

    def done( self, bytes_so_far=None ):
        if self._finished:
            return
        self._finished = True
        if bytes_so_far is None:
            bytes_so_far = 0
        now = self._clock()
        elapsed = max( 0.0, now - ( self._started or now ) )
        line = format_progress_line(
                self._label,
                bytes_so_far,
                self._total,
                elapsed,
                action=self._action,
                started=True,
        )
        self._emit( line, newline=True )
        self._last_line = line
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
        show_progress = logger.isEnabledFor( logging.INFO )
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


def download_file( url, dest_path, *, label=None, show_progress=None, reporter=None ):
    """Download ``url`` to ``dest_path`` via a ``.partial`` file then rename.

    ``show_progress`` defaults to True when the cuppa logger is at INFO or finer.
    Pass an existing ``ProgressReporter`` for tests; otherwise one is created on the
    progress stream (controlling tty when available).
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
        raise DownloadError(
            "failed to download [{}]: {}".format( url, error )
        )
