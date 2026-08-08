#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""HTTP file downloads with a shared transfer-progress reporter.

Used by location archive fetches and toolchain archives. See
``design/plans/download-progress.md``.
"""

from __future__ import print_function

import logging
import os
import sys
import time

try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

from cuppa.log import logger
from cuppa.utility.python2to3 import Exception as CuppaException
from cuppa.utility.storage import human_size


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


def format_progress_line( label, bytes_so_far, total_size, elapsed_s ):
    """One progress line (no trailing newline). Shared TTY and non-TTY shape."""
    rate = ( float( bytes_so_far ) / elapsed_s ) if elapsed_s > 0 else 0.0
    rate_text = "{}/s".format( human_size( rate ) )
    done = human_size( bytes_so_far )
    if total_size and total_size > 0:
        percent = min( 100.0, 100.0 * float( bytes_so_far ) / float( total_size ) )
        remaining = max( 0.0, float( total_size ) - float( bytes_so_far ) )
        eta = ( remaining / rate ) if rate > 0 else None
        return "Downloading {}  {} / {}  ({:.0f}%)  {}  ETA {}".format(
                label,
                done,
                human_size( total_size ),
                percent,
                rate_text,
                format_duration( eta ),
        )
    return "Downloading {}  {} downloaded  {}".format( label, done, rate_text )


class ProgressReporter( object ):
    """Throttle and render download progress on a stream (stderr by default)."""

    def __init__(
            self,
            stream=None,
            is_tty=None,
            clock=None,
            tty_interval_s=_TTY_INTERVAL_S,
            line_interval_s=_LINE_INTERVAL_S,
            line_percent_step=_LINE_PERCENT_STEP,
    ):
        self._stream = stream if stream is not None else sys.stderr
        self._clock = clock if clock is not None else time.time
        if is_tty is None:
            is_tty = bool( getattr( self._stream, 'isatty', lambda: False )() )
        self._is_tty = is_tty
        self._tty_interval_s = tty_interval_s
        self._line_interval_s = line_interval_s
        self._line_percent_step = line_percent_step
        self._label = ''
        self._total = None
        self._started = None
        self._last_emit = None
        self._next_line_percent = line_percent_step
        self._last_line = ''
        self._finished = False

    def begin( self, label, total_size=None ):
        self._label = label or 'download'
        self._total = total_size if total_size and total_size > 0 else None
        self._started = self._clock()
        self._last_emit = None
        self._next_line_percent = self._line_percent_step
        self._last_line = ''
        self._finished = False
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

        line = format_progress_line( self._label, bytes_so_far, self._total, elapsed )
        self._emit( line, newline=not self._is_tty )
        self._last_emit = now
        self._last_line = line

    def _emit( self, line, newline ):
        if self._is_tty and not newline:
            width = max( len( self._last_line ), len( line ) )
            self._stream.write( '\r' + line.ljust( width ) )
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
        line = format_progress_line( self._label, bytes_so_far, self._total, elapsed )
        self._emit( line, newline=True )
        self._last_line = line


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


def download_file( url, dest_path, *, label=None, show_progress=None, reporter=None ):
    """Download ``url`` to ``dest_path`` via a ``.partial`` file then rename.

    ``show_progress`` defaults to True when the cuppa logger is at INFO or finer.
    Pass an existing ``ProgressReporter`` for tests; otherwise one is created on stderr.
    """
    if show_progress is None:
        show_progress = logger.isEnabledFor( logging.INFO )

    parent = os.path.dirname( dest_path )
    if parent and not os.path.isdir( parent ):
        os.makedirs( parent )

    tmp_path = dest_path + '.partial'
    display = label or os.path.basename( dest_path ) or url
    progress = None
    if show_progress:
        progress = reporter if reporter is not None else ProgressReporter()

    bytes_so_far = 0
    try:
        request = Request( url )
        response = urlopen( request )
        try:
            total = _content_length( response )
            if progress:
                progress.begin( display, total )
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
