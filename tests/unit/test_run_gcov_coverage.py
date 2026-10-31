#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import fnmatch
import os

import pytest

from cuppa.cpp.run_gcov_coverage import detail_html_pattern, emit_tool_summary, run_command
from cuppa.progress import take_terse_children

pytestmark = pytest.mark.unit


def test_detail_pattern_does_not_treat_a_shorter_name_as_a_prefix():
    """``lim*.html`` matches ``lim_table``. The detail glob must not."""
    lim = detail_html_pattern( "test.gcc.coverage.lim" )
    table = detail_html_pattern( "test.gcc.coverage.lim_table" )
    lim_detail = "test.gcc.coverage.lim.functions.html"
    table_detail = "test.gcc.coverage.lim_table.functions.html"
    lim_index = "test.gcc.coverage.lim.html"

    assert fnmatch.fnmatch( lim_detail, lim )
    assert not fnmatch.fnmatch( table_detail, lim )
    assert not fnmatch.fnmatch( lim_index, lim )
    assert fnmatch.fnmatch( table_detail, table )
    assert not fnmatch.fnmatch( lim_detail, table )
    # The old pattern is what the soak stole pages with.
    assert fnmatch.fnmatch( table_detail, "test.gcc.coverage.lim*.html" )


def test_terse_tool_command_is_noted_not_echoed( capsys ):
    take_terse_children()
    code, output = run_command(
            "/bin/echo coverage-summary-line",
            os.getcwd(),
            { "terse_output": True },
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "coverage-summary-line" in output
    assert captured.out == ""
    children = take_terse_children()
    assert len( children ) == 1
    command, lines, failed = children[0]
    assert command.startswith( "/bin/echo" )
    assert failed is False
    assert any( "coverage-summary-line" in line for line in lines )


def test_tool_summary_stays_off_stdout_when_terse( capsys ):
    emit_tool_summary( "lines: 100.0% (1 out of 1)", { "terse_output": True } )
    assert capsys.readouterr().out == ""
    emit_tool_summary( "lines: 100.0% (1 out of 1)", {} )
    assert "lines: 100.0%" in capsys.readouterr().out
