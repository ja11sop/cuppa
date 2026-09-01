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


def test_open_progress_stream_falls_back_without_tty( monkeypatch ):
    import builtins

    real_open = builtins.open

    def fake_open( path, *args, **kwargs ):
        if path in ( '/dev/tty', 'CONOUT$' ):
            raise OSError( 'no tty' )
        return real_open( path, *args, **kwargs )

    monkeypatch.setattr( builtins, 'open', fake_open )
    stream, is_tty, owns = dl.open_progress_stream()
    assert stream is __import__( 'sys' ).stderr
    assert owns is False
    assert is_tty in ( True, False )


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
