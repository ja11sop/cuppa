#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io
import os

import pytest

from cuppa.utility import download as dl


pytestmark = pytest.mark.unit


class FakeClock( object ):
    def __init__( self, start=1000.0 ):
        self.now = start

    def __call__( self ):
        return self.now

    def advance( self, seconds ):
        self.now += seconds


def test_format_duration():
    assert dl.format_duration( 45 ) == '45s'
    assert dl.format_duration( 80 ) == '1m20s'
    assert dl.format_duration( 3725 ) == '1h02m'
    assert dl.format_duration( None ) == '--'


def test_format_progress_bar_states():
    assert dl.format_progress_bar( 0, started=False ) == '[' + ( ' ' * 20 ) + ']'
    assert dl.format_progress_bar( 0, started=True ) == '[>' + ( ' ' * 19 ) + ']'
    assert dl.format_progress_bar( 5 ) == '[=>' + ( ' ' * 18 ) + ']'
    assert dl.format_progress_bar( 95 ) == '[' + ( '=' * 19 ) + '>]'
    assert dl.format_progress_bar( 100 ) == '[' + ( '=' * 20 ) + ']'


def test_format_progress_line_known_size():
    line = dl.format_progress_line( 'big.deb', 412 * 1024 * 1024, 1600 * 1024 * 1024, 10.0 )
    assert 'Downloading big.deb' in line
    assert '[' in line and ']' in line
    assert '/' in line
    assert '%' in line
    assert '/s' in line
    assert 'ETA' in line


def test_format_progress_line_columns_stable():
    from cuppa.utility.storage import visible_len

    total = int( 1.6 * 1024 ** 3 )
    lines = [
        dl.format_progress_line( 'file.deb', 0, total, 0.0, started=True ),
        dl.format_progress_line( 'file.deb', int( 0.05 * total ), total, 0.8 ),
        dl.format_progress_line( 'file.deb', int( 0.10 * total ), total, 1.5 ),
        dl.format_progress_line( 'file.deb', total, total, 15.0 ),
    ]
    for marker in ( ']  ', '  ETA ' ):
        columns = [ line.index( marker ) for line in lines ]
        assert len( set( columns ) ) == 1, ( marker, columns, lines )
    assert '  0%' in lines[0]
    assert '100%' in lines[-1]
    assert '[>' in lines[0]
    assert '[' + ( '=' * 20 ) + ']' in lines[-1]
    assert len( set( visible_len( line ) for line in lines ) ) == 1


def test_format_progress_line_uses_colour_when_enabled():
    from cuppa.colourise import colouriser

    was = colouriser.use_colour
    colouriser.enable()
    try:
        mid = dl.format_progress_line( 'file.deb', 50, 100, 1.0 )
        assert '\x1b[' in mid
        assert ' 50%' in mid
        # Brackets stay outside the emphasised info fill.
        assert '[\x1b[' in mid
        done = dl.format_progress_line( 'file.deb', 100, 100, 1.0 )
        # Completed transferred size is emphasised; mid-transfer size is not.
        assert done.count( '\x1b[1m' ) > mid.count( '\x1b[1m' )
    finally:
        colouriser.use_colour = was


def test_format_progress_line_extract_action():
    line = dl.format_progress_line(
            'data.tar.xz', 100, 200, 1.0, action='Extracting',
    )
    assert line.startswith( 'Extracting data.tar.xz' )


def test_format_progress_line_unknown_size():
    line = dl.format_progress_line( 'mystery.bin', 50 * 1024 * 1024, None, 5.0 )
    assert 'transferred' in line
    assert 'ETA' not in line


def _reset_progress_tty_state( monkeypatch ):
    monkeypatch.delenv( dl.PROGRESS_TTY_ENV, raising=False )
    monkeypatch.delenv( dl.PROGRESS_FD_ENV, raising=False )
    dl._progress_tty_stream = None
    dl._progress_tty_fd = None


def test_open_progress_stream_falls_back_without_tty( monkeypatch ):
    import builtins

    real_open = builtins.open

    def fake_open( path, *args, **kwargs ):
        if path in ( '/dev/tty', 'CONOUT$' ):
            raise OSError( 'no tty' )
        return real_open( path, *args, **kwargs )

    _reset_progress_tty_state( monkeypatch )
    monkeypatch.setattr( builtins, 'open', fake_open )
    stream, is_tty, owns = dl.open_progress_stream()
    assert stream is __import__( 'sys' ).stderr
    assert owns is False
    assert is_tty in ( True, False )


def test_open_progress_stream_uses_cuppa_progress_tty_env( monkeypatch, tmp_path ):
    """Path fallback when /dev/tty is gone but CUPPA_PROGRESS_TTY is set."""
    import builtins
    import io

    real_open = builtins.open
    pts = tmp_path / "fake-pts"
    pts.write_text( "", encoding="utf-8" )
    opened = []

    class _TtyStream( io.StringIO ):
        def isatty( self ):
            return True

        def fileno( self ):
            return 99

    def fake_open( path, *args, **kwargs ):
        opened.append( str( path ) )
        if path in ( '/dev/tty', 'CONOUT$' ):
            raise OSError( 'no controlling tty' )
        if str( path ) == str( pts ):
            return _TtyStream()
        return real_open( path, *args, **kwargs )

    _reset_progress_tty_state( monkeypatch )
    monkeypatch.setenv( dl.PROGRESS_TTY_ENV, str( pts ) )
    monkeypatch.setattr( builtins, 'open', fake_open )
    monkeypatch.setattr( os, 'ttyname', lambda fd: str( pts ), raising=False )
    monkeypatch.setattr( os, 'isatty', lambda fd: fd == 99 )

    stream, is_tty, owns = dl.open_progress_stream()
    assert is_tty is True
    assert owns is False
    assert str( pts ) in opened


def test_open_progress_stream_uses_inherited_progress_fd( monkeypatch ):
    """pass_fds + CUPPA_PROGRESS_FD is the nest-safe path (no CTTY reopen)."""
    import pty

    _reset_progress_tty_state( monkeypatch )
    master, slave = pty.openpty()
    try:
        monkeypatch.setenv( dl.PROGRESS_FD_ENV, str( slave ) )
        stream, is_tty, owns = dl.open_progress_stream()
        assert is_tty is True
        assert owns is False
        assert stream.fileno() == slave
    finally:
        try:
            os.close( master )
        except Exception:
            pass
        try:
            os.close( slave )
        except Exception:
            pass
        _reset_progress_tty_state( monkeypatch )


def test_progress_tty_popen_kwargs_pass_fds( monkeypatch ):
    import pty

    _reset_progress_tty_state( monkeypatch )
    master, slave = pty.openpty()
    try:
        monkeypatch.setenv( dl.PROGRESS_FD_ENV, str( slave ) )
        kwargs, env = dl.progress_tty_popen_kwargs( {} )
        assert kwargs.get( "pass_fds" ) == ( slave, )
        assert env[dl.PROGRESS_FD_ENV] == str( slave )
    finally:
        try:
            os.close( master )
        except Exception:
            pass
        try:
            os.close( slave )
        except Exception:
            pass
        _reset_progress_tty_state( monkeypatch )


def test_progress_tty_popen_kwargs_omits_pass_fds_on_windows( monkeypatch ):
    """Windows subprocess rejects pass_fds — only publish env for CONOUT$ reopen."""
    _reset_progress_tty_state( monkeypatch )
    monkeypatch.setattr( dl.sys, "platform", "win32" )
    monkeypatch.setattr( dl.os, "name", "nt" )
    monkeypatch.setattr( dl, "ensure_progress_tty_fd", lambda: 7 )
    monkeypatch.setattr( dl.os, "ttyname", lambda fd: "CONOUT$", raising=False )
    kwargs, env = dl.progress_tty_popen_kwargs( {} )
    assert "pass_fds" not in kwargs
    assert env[dl.PROGRESS_FD_ENV] == "7"


def test_resolve_progress_tty_path_remembers_existing_env( monkeypatch, tmp_path ):
    pts = tmp_path / "pts0"
    pts.write_text( "", encoding="utf-8" )
    _reset_progress_tty_state( monkeypatch )
    monkeypatch.setenv( dl.PROGRESS_TTY_ENV, str( pts ) )
    assert dl.resolve_progress_tty_path() == str( pts )


def test_reporter_tty_rewrites_same_line():
    stream = io.StringIO()
    clock = FakeClock()
    reporter = dl.ProgressReporter(
            stream=stream, is_tty=True, clock=clock, tty_interval_s=0.1,
    )
    reporter.begin( 'file.tgz', total_size=1000 )
    clock.advance( 0.2 )
    reporter.update( 500 )
    clock.advance( 0.2 )
    reporter.done( 1000 )
    text = stream.getvalue()
    assert text.count( '\r' ) >= 1
    assert text.endswith( '\n' )
    assert 'file.tgz' in text
    # done() must \\r-replace the last mid-transfer line, not append after it.
    assert 'ETA 0sDownloading' not in text.replace( ' ', '' )
    assert text.count( '\n' ) == 1


def test_reporter_non_tty_emits_newlines_on_percent_steps():
    stream = io.StringIO()
    clock = FakeClock()
    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=False,
            clock=clock,
            line_interval_s=100,
            line_percent_step=25,
    )
    reporter.begin( 'file.tgz', total_size=100 )
    clock.advance( 1 )
    reporter.update( 25 )
    clock.advance( 1 )
    reporter.update( 50 )
    clock.advance( 1 )
    reporter.done( 100 )
    lines = [ line for line in stream.getvalue().splitlines() if line.strip() ]
    assert len( lines ) >= 3
    assert all( 'Downloading file.tgz' in line for line in lines )


def test_download_file_http_server( tmp_path ):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    payload = b'abcdefghijklmnopqrstuvwxyz' * 1024

    class Handler( BaseHTTPRequestHandler ):
        def do_GET( self ):
            self.send_response( 200 )
            self.send_header( 'Content-Length', str( len( payload ) ) )
            self.end_headers()
            self.wfile.write( payload )

        def log_message( self, format, *args ):
            return

    server = HTTPServer( ( '127.0.0.1', 0 ), Handler )
    thread = threading.Thread( target=server.serve_forever )
    thread.daemon = True
    thread.start()
    try:
        url = 'http://127.0.0.1:{}/blob.bin'.format( server.server_address[1] )
        dest = tmp_path / 'blob.bin'
        stream = io.StringIO()
        reporter = dl.ProgressReporter( stream=stream, is_tty=False, line_interval_s=0 )
        path = dl.download_file(
                url, str( dest ), label='blob.bin', show_progress=True, reporter=reporter,
        )
        assert path == str( dest )
        assert dest.read_bytes() == payload
        assert not os.path.isfile( str( dest ) + '.partial' )
        assert 'Downloading blob.bin' in stream.getvalue()
    finally:
        server.shutdown()
        thread.join( timeout=5 )


def test_download_file_sends_headers( tmp_path ):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    seen = {}

    class Handler( BaseHTTPRequestHandler ):
        def do_GET( self ):
            seen['private'] = self.headers.get( 'Private-Token' )
            body = b'ok'
            self.send_response( 200 )
            self.send_header( 'Content-Length', str( len( body ) ) )
            self.end_headers()
            self.wfile.write( body )

        def log_message( self, format, *args ):
            return

    server = HTTPServer( ( '127.0.0.1', 0 ), Handler )
    thread = threading.Thread( target=server.serve_forever )
    thread.daemon = True
    thread.start()
    try:
        url = 'http://127.0.0.1:{}/pkg.bin'.format( server.server_address[1] )
        dest = tmp_path / 'pkg.bin'
        dl.download_file(
                url,
                str( dest ),
                show_progress=False,
                headers={ 'PRIVATE-TOKEN': 'secret-token' },
        )
        assert dest.read_bytes() == b'ok'
        assert seen.get( 'private' ) == 'secret-token'
    finally:
        server.shutdown()
        thread.join( timeout=5 )


def test_download_file_cleans_partial_on_failure( tmp_path, monkeypatch ):
    dest = tmp_path / 'broken.bin'

    class Boom( object ):
        headers = { 'Content-Length': '100' }

        def read( self, size=-1 ):
            raise IOError( 'connection reset' )

        def close( self ):
            return

    monkeypatch.setattr( dl, 'urlopen', lambda request: Boom() )
    with pytest.raises( dl.DownloadError ):
        dl.download_file( 'http://example.com/broken.bin', str( dest ), show_progress=False )
    assert not dest.exists()
    assert not os.path.isfile( str( dest ) + '.partial' )


def test_upload_file_http_server( tmp_path ):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    payload = b'upload-payload-' * 2048
    src = tmp_path / 'pkg.tar.gz'
    src.write_bytes( payload )
    received = {}

    class Handler( BaseHTTPRequestHandler ):
        def do_PUT( self ):
            length = int( self.headers.get( 'Content-Length', '0' ) )
            received['body'] = self.rfile.read( length )
            received['content_type'] = self.headers.get( 'Content-Type' )
            received['path'] = self.path
            self.send_response( 201 )
            self.end_headers()
            self.wfile.write( b'{"message":"201 Created"}' )

        def log_message( self, format, *args ):
            return

    server = HTTPServer( ( '127.0.0.1', 0 ), Handler )
    thread = threading.Thread( target=server.serve_forever )
    thread.daemon = True
    thread.start()
    try:
        url = 'http://127.0.0.1:{}/packages/generic/widget/1.0.0/pkg.tar.gz'.format(
                server.server_address[1]
        )
        stream = io.StringIO()
        reporter = dl.ProgressReporter(
                stream=stream, is_tty=False, line_interval_s=0, action='Uploading',
        )
        path = dl.upload_file(
                url, str( src ), label='pkg.tar.gz', show_progress=True, reporter=reporter,
        )
        assert path == str( src )
        assert received.get( 'body' ) == payload
        assert received.get( 'content_type' ) == 'application/octet-stream'
        assert 'Uploading pkg.tar.gz' in stream.getvalue()
    finally:
        server.shutdown()
        thread.join( timeout=5 )


def test_upload_file_sends_headers( tmp_path ):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    src = tmp_path / 'pkg.bin'
    src.write_bytes( b'payload' )
    seen = {}

    class Handler( BaseHTTPRequestHandler ):
        def do_PUT( self ):
            seen['private'] = self.headers.get( 'Private-Token' )
            length = int( self.headers.get( 'Content-Length', '0' ) )
            self.rfile.read( length )
            self.send_response( 201 )
            self.end_headers()

        def log_message( self, format, *args ):
            return

    server = HTTPServer( ( '127.0.0.1', 0 ), Handler )
    thread = threading.Thread( target=server.serve_forever )
    thread.daemon = True
    thread.start()
    try:
        url = 'http://127.0.0.1:{}/pkg.bin'.format( server.server_address[1] )
        dl.upload_file(
                url,
                str( src ),
                show_progress=False,
                headers={ 'PRIVATE-TOKEN': 'secret-token' },
        )
        assert seen.get( 'private' ) == 'secret-token'
    finally:
        server.shutdown()
        thread.join( timeout=5 )


def test_upload_file_http_error_includes_body( tmp_path ):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    src = tmp_path / 'pkg.bin'
    src.write_bytes( b'payload' )

    class Handler( BaseHTTPRequestHandler ):
        def do_PUT( self ):
            length = int( self.headers.get( 'Content-Length', '0' ) )
            self.rfile.read( length )
            body = b'{"error":"unauthorized"}'
            self.send_response( 401 )
            self.send_header( 'Content-Length', str( len( body ) ) )
            self.end_headers()
            self.wfile.write( body )

        def log_message( self, format, *args ):
            return

    server = HTTPServer( ( '127.0.0.1', 0 ), Handler )
    thread = threading.Thread( target=server.serve_forever )
    thread.daemon = True
    thread.start()
    try:
        url = 'http://127.0.0.1:{}/pkg.bin'.format( server.server_address[1] )
        with pytest.raises( dl.UploadError ) as raised:
            dl.upload_file( url, str( src ), show_progress=False )
        assert raised.value.http_status == 401
        assert 'unauthorized' in str( raised.value.parameter )
        assert 'unauthorized' in ( raised.value.body or '' )
    finally:
        server.shutdown()
        thread.join( timeout=5 )


def test_upload_file_missing_source( tmp_path ):
    missing = tmp_path / 'gone.bin'
    with pytest.raises( dl.UploadError ) as raised:
        dl.upload_file( 'http://example.com/pkg.bin', str( missing ), show_progress=False )
    assert 'missing' in str( raised.value.parameter )


def test_transfer_file_reports_extract_progress( tmp_path ):
    src = tmp_path / 'payload.bin'
    payload = b'xyz' * 10000
    src.write_bytes( payload )
    sink = io.BytesIO()
    stream = io.StringIO()
    reporter = dl.ProgressReporter(
            stream=stream, is_tty=False, line_interval_s=0, action='Extracting',
    )
    total = dl.transfer_file(
            str( src ),
            sink.write,
            label='payload.bin',
            action='Extracting',
            show_progress=True,
            reporter=reporter,
    )
    assert total == len( payload )
    assert sink.getvalue() == payload
    assert 'Extracting payload.bin' in stream.getvalue()


def test_tar_stdin_argv_compression_flags( tmp_path ):
    root = str( tmp_path / 'out' )
    assert dl.tar_stdin_argv( '/tmp/a.tar.gz', root ) == [ 'tar', '-xzf', '-', '-C', root ]
    assert dl.tar_stdin_argv( '/tmp/a.tgz', root ) == [ 'tar', '-xzf', '-', '-C', root ]
    assert dl.tar_stdin_argv( '/tmp/a.tar.xz', root ) == [ 'tar', '-xJf', '-', '-C', root ]
    assert dl.tar_stdin_argv( '/tmp/a.tar', root ) == [ 'tar', '-xf', '-', '-C', root ]


def test_extract_tar_archive_with_progress( tmp_path ):
    import tarfile

    source = tmp_path / 'tree'
    source.mkdir()
    ( source / 'hello.txt' ).write_text( 'hi', encoding='utf-8' )
    archive = tmp_path / 'pkg.tar.gz'
    target = tmp_path / 'out'
    with tarfile.open( archive, 'w:gz' ) as handle:
        handle.add( str( source / 'hello.txt' ), arcname='hello.txt' )

    stream = io.StringIO()
    reporter = dl.ProgressReporter(
            stream=stream, is_tty=False, line_interval_s=0, action='Extracting',
    )
    dl.extract_tar_archive(
            str( archive ),
            str( target ),
            show_progress=True,
            reporter=reporter,
    )
    assert ( target / 'hello.txt' ).read_text( encoding='utf-8' ) == 'hi'
    assert 'Extracting pkg.tar.gz' in stream.getvalue()


def test_extract_zip_archive_with_progress( tmp_path ):
    import zipfile

    archive = tmp_path / 'pkg.zip'
    target = tmp_path / 'out'
    with zipfile.ZipFile( archive, 'w' ) as handle:
        handle.writestr( 'dir/a.txt', 'aaa' * 1000 )
        handle.writestr( 'dir/b.txt', 'bbb' * 1000 )

    stream = io.StringIO()
    reporter = dl.ProgressReporter(
            stream=stream, is_tty=False, line_interval_s=0, action='Extracting',
    )
    dl.extract_zip_archive(
            str( archive ),
            str( target ),
            show_progress=True,
            reporter=reporter,
    )
    assert ( target / 'dir' / 'a.txt' ).read_text( encoding='utf-8' ) == 'aaa' * 1000
    assert ( target / 'dir' / 'b.txt' ).read_text( encoding='utf-8' ) == 'bbb' * 1000
    assert 'Extracting pkg.zip' in stream.getvalue()


def test_is_http_not_found():
    assert dl.is_http_not_found( dl.DownloadError( 'missing', http_status=404 ) )
    assert not dl.is_http_not_found( dl.DownloadError( 'denied', http_status=403 ) )
    assert not dl.is_http_not_found( dl.DownloadError( 'no status' ) )


def test_format_progress_line_compact_drops_bar():
    full = dl.format_progress_line( 'f.bin', 50, 100, 1.0, compact=False )
    compact = dl.format_progress_line( 'f.bin', 50, 100, 1.0, compact=True )
    assert '[' in full and ']' in full
    assert '[' not in compact
    assert '50%' in compact
    assert 'ETA' in compact


def test_format_progress_line_muted_subdues_verb_and_label():
    """Terse/quiet mute the progress body; ECG colour is separate."""
    from cuppa.colourise import as_subdued, colouriser
    from cuppa.output_processor import strip_ansi

    was = colouriser.use_colour
    colouriser.enable()
    try:
        muted = dl.format_progress_line(
                'pkg.tgz', 50, 100, 1.0, muted=True, include_bar=True,
        )
        plain = strip_ansi( muted )
        assert 'Downloading' in plain
        assert 'pkg.tgz' in plain
        assert as_subdued( 'Downloading' ) in muted
        assert as_subdued( 'pkg.tgz' ) in muted
    finally:
        colouriser.use_colour = was


class _NoAliveTimer( object ):
    """Disable background alive ticks in FakeClock unit tests."""

    def __init__( self, *args, **kwargs ):
        pass

    def start( self ):
        pass

    def cancel( self ):
        pass


def test_reporter_normal_tty_has_no_alive_widget():
    from cuppa.output_processor import strip_ansi
    from cuppa.utility import heartbeat as hb

    hb.reset()
    hb.set_presentation( style='pulse', compact=False )
    stream = io.StringIO()
    clock = FakeClock()
    reporter = dl.ProgressReporter(
            stream=stream, is_tty=True, clock=clock, tty_interval_s=0.1,
            alive_timer_factory=_NoAliveTimer,
    )
    reporter.begin( 'file.tgz', total_size=100 )
    clock.advance( 0.2 )
    reporter.update( 50 )
    reporter.done( 100 )
    plain = strip_ansi( stream.getvalue() )
    assert 'Downloading file.tgz' in plain
    assert '[' in plain  # progress bar
    assert not plain.lstrip( '\r' ).startswith( '|' )  # no pulse head
    assert plain.endswith( '\n' )  # durable final line
    hb.reset()


def test_reporter_quiet_normal_tty_has_alive_widget():
    """Normal ``-Q`` muted progress shares the quiet heartbeat alive head."""
    from cuppa.output_processor import strip_ansi
    from cuppa.utility import heartbeat as hb

    hb.reset()
    hb.set_presentation( style='pulse', compact=False )
    status = io.StringIO()
    hb.configure_quiet_console( 'warn', stream=status, is_tty=True )
    stream = io.StringIO()
    clock = FakeClock()
    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=True,
            clock=clock,
            tty_interval_s=0.1,
            alive_timer_factory=_NoAliveTimer,
    )
    reporter.begin( 'file.tgz', total_size=100, action='Compressing' )
    clock.advance( 0.25 )
    reporter.update( 50 )
    plain = strip_ansi( stream.getvalue() )
    assert plain.lstrip( '\r' ).startswith( '|' )  # pulse head
    assert 'Compressing file.tgz' in plain
    assert '[' in plain
    assert '→' not in plain  # quiet normal is not arrow-compact
    reporter.done( 100 )
    hb.reset()


def test_reporter_terse_tty_alive_arrow_bar_and_overwrite():
    from cuppa.output_processor import strip_ansi
    from cuppa.utility import heartbeat as hb

    hb.reset()
    stream = io.StringIO()
    clock = FakeClock()
    slept = []

    def sleep( seconds ):
        slept.append( seconds )
        clock.advance( seconds )

    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=True,
            clock=clock,
            sleep=sleep,
            tty_interval_s=0.1,
            compact=True,
            alive_style='pulse',
            alive_timer_factory=_NoAliveTimer,
    )
    reporter.begin( 'pkg.tar.gz', total_size=200, action='Compressing' )
    # Below idle gate — no paint yet.
    clock.advance( 0.05 )
    reporter.update( 50 )
    assert stream.getvalue() == ''
    # Past idle gate — paint alive + → + bar.
    clock.advance( 0.20 )
    reporter.update( 100 )
    mid = strip_ansi( stream.getvalue() )
    assert '→' in mid
    assert '|' in mid
    assert '[' in mid  # terse keeps the bar
    assert 'Compressing pkg.tar.gz' in mid
    # Still early in the first animation cycle — dwell finishes that cycle.
    reporter.done( 200 )
    assert not strip_ansi( stream.getvalue() ).rstrip().endswith( '100%' )
    assert slept, 'quick bar past idle gate should dwell to finish one cycle'
    assert slept[0] > 0
    assert slept[0] <= hb.cycle_duration_s()
    hb.reset()


def test_reporter_long_transfer_skips_post_complete_dwell():
    """Dwell is not an extra cycle after a long transfer already showed one."""
    from cuppa.utility import heartbeat as hb

    hb.reset()
    stream = io.StringIO()
    clock = FakeClock()
    slept = []

    def sleep( seconds ):
        slept.append( seconds )
        clock.advance( seconds )

    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=True,
            clock=clock,
            sleep=sleep,
            tty_interval_s=0.1,
            compact=True,
            alive_style='pulse',
            alive_timer_factory=_NoAliveTimer,
    )
    reporter.begin( 'pkg.tar.gz', total_size=200, action='Compressing' )
    clock.advance( 0.25 )
    reporter.update( 100 )
    # Already past one full animation cycle since first paint.
    clock.advance( hb.cycle_duration_s() + 0.5 )
    reporter.done( 200 )
    assert slept == []
    hb.reset()


def test_reporter_alive_ticks_between_byte_updates():
    """Alive advances on its animation timer, not only on progress throttle."""
    from cuppa.output_processor import strip_ansi
    from cuppa.utility import heartbeat as hb

    hb.reset()
    stream = io.StringIO()
    clock = FakeClock()
    pending = []

    class _CaptureTimer( object ):
        def __init__( self, interval, func ):
            self.interval = interval
            self.func = func
            pending.append( self )

        def start( self ):
            pass

        def cancel( self ):
            if self in pending:
                pending.remove( self )

    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=True,
            clock=clock,
            tty_interval_s=10.0,  # byte metrics rarely refresh
            compact=True,
            alive_style='pulse',
            alive_timer_factory=_CaptureTimer,
    )
    reporter.begin( 'big.tar.gz', total_size=1000, action='Compressing' )
    clock.advance( 0.25 )
    reporter.update( 100 )
    assert pending, 'alive timer should arm after first paint'
    spin_before = reporter._spin
    frame_before = strip_ansi( stream.getvalue() )
    # Simulate animation ticks with no new byte progress.
    pending[-1].func()
    pending[-1].func()
    assert reporter._spin == spin_before + 2
    frame_after = strip_ansi( stream.getvalue() )
    assert 'Compressing big.tar.gz' in frame_after
    assert frame_after != frame_before or reporter._spin > spin_before
    reporter.done( 100 )
    hb.reset()


def test_reporter_rapid_updates_do_not_reset_alive_timer():
    """Compress-per-file update storms must not cancel the alive cadence."""
    from cuppa.utility import heartbeat as hb

    hb.reset()
    stream = io.StringIO()
    clock = FakeClock()
    armed = []

    class _CaptureTimer( object ):
        def __init__( self, interval, func ):
            self.interval = interval
            self.func = func
            self.cancelled = False
            armed.append( self )

        def start( self ):
            pass

        def cancel( self ):
            self.cancelled = True

    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=True,
            clock=clock,
            tty_interval_s=1.0,
            compact=True,
            alive_style='pulse',
            alive_timer_factory=_CaptureTimer,
    )
    reporter.begin( 'many.tar.gz', total_size=10000, action='Compressing' )
    clock.advance( 0.25 )
    reporter.update( 10 )
    assert len( armed ) == 1
    first = armed[0]
    # Storm of throttled updates (same window) — must keep the same timer.
    for n in range( 50 ):
        clock.advance( 0.01 )
        reporter.update( 10 + n )
    assert first.cancelled is False
    assert reporter._alive_timer is first
    assert len( armed ) == 1
    reporter.done( 100 )
    hb.reset()


def test_reporter_terse_non_tty_stays_silent():
    stream = io.StringIO()
    clock = FakeClock()
    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=False,
            clock=clock,
            line_interval_s=0,
            compact=True,
            alive_timer_factory=_NoAliveTimer,
    )
    reporter.begin( 'pkg.tar.gz', total_size=100 )
    clock.advance( 1.0 )
    reporter.update( 50 )
    reporter.done( 100 )
    assert stream.getvalue() == ''


def test_reporter_fast_terse_never_reveals():
    """Transfers that finish before the idle gate never flash progress."""
    stream = io.StringIO()
    clock = FakeClock()
    reporter = dl.ProgressReporter(
            stream=stream,
            is_tty=True,
            clock=clock,
            compact=True,
            alive_style='pulse',
            alive_timer_factory=_NoAliveTimer,
    )
    reporter.begin( 'tiny.bin', total_size=10 )
    clock.advance( 0.05 )  # still under idle gate
    reporter.done( 10 )
    assert stream.getvalue() == ''
