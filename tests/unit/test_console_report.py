#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Console-report writer — unprefixed stdout, not the logger."""

import io

import pytest

from cuppa.colourise import as_info_label
from cuppa.utility.console_report import report_mode_banner, write_report_lines


pytestmark = pytest.mark.unit


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
