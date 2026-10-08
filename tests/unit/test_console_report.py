#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Console-report writer — unprefixed stdout, not the logger."""

import io
import logging
import sys

import pytest

from cuppa.colourise import as_info_label
from cuppa.log import logger
from cuppa.utility import heartbeat as hb
from cuppa.utility.console_report import (
    ensure_report_stream,
    report_mode_banner,
    reset_mode_banners_for_tests,
    write_report_lines,
)


pytestmark = pytest.mark.unit


class FakeClock( object ):
    def __init__( self ):
        self.now = 1000.0

    def __call__( self ):
        return self.now

    def advance( self, seconds ):
        self.now += seconds


@pytest.fixture( autouse=True )
def _reset_heartbeat():
    # ``configure_quiet_console`` calls ``set_logging_level``; ``hb.reset``
    # does not undo that. Restore cuppa/root levels so later modules that use
    # ``caplog.at_level("DEBUG")`` still see Location's DEBUG notices.
    previous_cuppa_level = logger.level
    previous_root_level = logging.getLogger().level
    hb.reset()
    reset_mode_banners_for_tests()
    yield
    hb.reset()
    reset_mode_banners_for_tests()
    logger.setLevel( previous_cuppa_level )
    logging.getLogger().setLevel( previous_root_level )


def test_write_report_lines_are_unprefixed_and_flushed():
    out = io.StringIO()
    write_report_lines( [ "alpha", "beta" ], out=out )
    assert out.getvalue() == "alpha\nbeta\n"


def test_report_mode_banner_keeps_colour_and_plain_suffix():
    out = io.StringIO()
    line = "{} — report only".format( as_info_label( "Running in CASCADE PLAN mode" ) )
    report_mode_banner( line, out=out )
    text = out.getvalue()
    assert text.startswith( as_info_label( "Running in CASCADE PLAN mode" ) )
    assert text.endswith( " — report only\n" )
    assert "cuppa:" not in text
    assert "[info]" not in text


def test_report_mode_banner_dedupes_identical_chips():
    out = io.StringIO()
    line = as_info_label( "Running in OFFLINE mode" )
    report_mode_banner( line, out=out )
    report_mode_banner( line, out=out )
    report_mode_banner( as_info_label( "Running in DUMP mode" ), out=out )
    text = out.getvalue()
    assert text.count( "Running in OFFLINE mode" ) == 1
    assert text.count( "Running in DUMP mode" ) == 1


def test_ensure_report_stream_passthrough_when_not_diverting():
    out = io.StringIO()
    assert ensure_report_stream( out ) is out
    assert ensure_report_stream( None ) is sys.stdout


def test_ensure_report_stream_clears_status_before_purge_chunk( monkeypatch ):
    """Purge/list ``out.write`` must not glue onto the quiet status row."""
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False,
            clock=clock, columns=120, pulse=False, style='pulse',
    )
    hb.show_info(
            "Using [/home/user/_cuppa/_download] for dependencies "
            "and [/home/user/.cuppa/downloads] for downloads"
    )
    assert 'Using [' in stream.getvalue()

    pipe = io.StringIO()
    real = hb.sys.stdout
    hb.sys.stdout = pipe
    try:
        out = ensure_report_stream( sys.stdout )
        out.write(
                "Removing 1 dependency tree and 1 download (1.9G) "
                "under ~/_cuppa/_download / ~/.cuppa/downloads\n"
        )
        out.write( "-" * 80 + "\n" )
    finally:
        hb.sys.stdout = real

    # Interactive: report on the progress TTY, not the stdout pipe.
    assert pipe.getvalue() == ''
    body = stream.getvalue()
    assert 'Removing 1 dependency tree' in body
    assert 'downloadsRemoving' not in body
    assert 'downloads  ---' not in body
    assert body.count( 'Removing 1 dependency tree' ) == 1


def test_write_report_lines_explicit_stdout_uses_tty_when_diverting( monkeypatch ):
    monkeypatch.setenv( 'CUPPA_STDOUT_IS_TTY', '1' )
    stream = io.StringIO()
    clock = FakeClock()
    hb.configure_quiet_console(
            'warn', stream=stream, is_tty=True, owns_stream=False,
            clock=clock, columns=80, pulse=False, style='pulse',
    )
    hb.show_info( 'Using [/tmp] for dependencies' )
    pipe = io.StringIO()
    real = hb.sys.stdout
    hb.sys.stdout = pipe
    try:
        write_report_lines( [ 'Running in PURGE DEPENDENCIES mode' ], out=sys.stdout )
    finally:
        hb.sys.stdout = real
    assert pipe.getvalue() == ''
    assert 'Running in PURGE DEPENDENCIES mode\n' in stream.getvalue()
    assert 'Using [/tmp]' not in stream.getvalue().split( 'Running in' )[ -1 ]
