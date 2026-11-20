#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import fnmatch
import os

import pytest

from cuppa.cpp.run_gcov_coverage import (
        GCOV_NAME_LIMIT,
        bounded_gcov_filename,
        detail_html_pattern,
        emit_tool_summary,
        gcov_name_limit,
        run_command,
)
from cuppa.progress import take_terse_children

pytestmark = pytest.mark.unit

_TAIL = "##widget_test.gcov"


def _long_header_stem( padding=0 ):
    """Like the name ``gcov -l -p`` gives a header under a long package path."""
    header = "#".join( [
            "_cuppa", "example_lib@feature_a_long_branch_name_for_widgets",
            "include", "example", "widget", "detail", "widget_traits" + "x" * padding + ".hpp",
    ] )
    return "src#widget_test.cpp##" + header


def test_a_short_gcov_name_is_unchanged():
    assert bounded_gcov_filename( "src#widget_test.cpp##x.hpp", _TAIL ) == "src#widget_test.cpp##x.hpp" + _TAIL


def test_a_long_gcov_name_is_bounded_and_keeps_its_ends():
    stem = _long_header_stem( padding=300 )
    name = bounded_gcov_filename( stem, _TAIL )
    assert len( name.encode() ) <= GCOV_NAME_LIMIT
    assert name.startswith( "src#widget_test.cpp##" )
    assert name.endswith( _TAIL )
    assert "~" in name


def test_a_bounded_gcov_name_is_stable_and_distinct():
    first = bounded_gcov_filename( _long_header_stem( padding=300 ), _TAIL )
    again = bounded_gcov_filename( _long_header_stem( padding=300 ), _TAIL )
    other = bounded_gcov_filename( _long_header_stem( padding=301 ), _TAIL )
    assert first == again
    assert first != other


def test_a_bounded_gcov_name_counts_bytes_not_characters():
    stem = "src#widget_test.cpp##" + "\u00e9" * 200
    name = bounded_gcov_filename( stem, _TAIL )
    assert len( name.encode() ) <= GCOV_NAME_LIMIT
    assert name.endswith( _TAIL )


def test_the_limit_is_unchanged_off_windows( tmp_path ):
    if os.name != "nt":
        assert gcov_name_limit( str( tmp_path ) ) == GCOV_NAME_LIMIT


def test_a_bounded_name_can_be_created_where_the_long_one_cannot( tmp_path ):
    stem = _long_header_stem( padding=300 )
    with pytest.raises( OSError ):
        ( tmp_path / ( stem + _TAIL ) ).write_text( "x" )
    bounded = tmp_path / bounded_gcov_filename( stem, _TAIL )
    bounded.write_text( "x" )
    assert bounded.exists()


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
