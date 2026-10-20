#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Sticky ``[....]`` caption for in-flight terse actions."""

import io
from types import SimpleNamespace

import pytest

from cuppa import progress
from cuppa.output_processor import strip_ansi
from cuppa.utility import heartbeat as hb


pytestmark = pytest.mark.unit


class FakeClock( object ):
    def __init__( self, start=1000.0 ):
        self.now = start

    def __call__( self ):
        return self.now

    def advance( self, seconds ):
        self.now += seconds


def _env():
    return {
            "terse_output": True,
            "sconscript_file": "./test/orders/sconscript",
            "variant_dir_name": "gcc15_dbg_x86_64_cxx2c",
            "variant": SimpleNamespace( name=lambda: "dbg" ),
            "toolchain": SimpleNamespace( name=lambda: "gcc15" ),
            "target_arch": "x86_64",
            "abi": "cxx2c",
            "current_build_dir": ".",
            "base_path": ".",
            "offset_dir": ".",
            "abs_final_dir": ".",
            "final_dir": ".",
    }


def _node( path="a.o" ):
    return SimpleNamespace( path=path, attributes=SimpleNamespace() )


@pytest.fixture( autouse=True )
def _reset():
    hb.reset()
    progress.reset_terse_executing()
    yield
    progress.reset_terse_executing()
    hb.reset()


def _arm_status_row( stream, clock, monkeypatch ):
    def sleep( seconds ):
        clock.advance( seconds )

    hb.set_presentation( style="pulse", compact=True )
    monkeypatch.setattr(
            hb, "open_progress_stream",
            lambda: ( stream, True, False ),
    )
    monkeypatch.setattr( hb, "_clock", clock )
    monkeypatch.setattr( hb, "_sleep", sleep )
    monkeypatch.setattr( hb, "_columns", 120 )
    assert hb.ensure_status_row() is True
    assert hb.status_row_active() is True


def test_progressive_terse_action_verbs():
    assert progress.progressive_terse_action( "compile" ) == "compiling"
    assert progress.progressive_terse_action( "copy" ) == "copying"
    assert progress.progressive_terse_action( "index" ) == "indexing"
    assert progress.progressive_terse_action( "link" ) == "linking"
    assert progress.progressive_terse_action( "run" ) == "running"
    assert progress.progressive_terse_action( "compile-scss" ) == "compiling-scss"
    assert progress.progressive_terse_action( "cmake-build" ) == "cmake-building"


def test_format_terse_executing_caption_aligns_and_progresses():
    from cuppa.colourise import (
            as_emphasised, as_emphasised_plain, as_info, as_subdued, colouriser,
    )

    was = colouriser.use_colour
    colouriser.enable()
    try:
        env = _env()
        caption = progress.format_terse_executing_caption(
                "g++ -c a.cpp -o a.o", [ _node() ], [ _node( "a.cpp" ) ], env,
        )
        plain = strip_ansi( caption )
        assert plain.startswith( "[....] " )
        assert len( "[....]" ) == progress._STATUS_WIDTH
        assert "compiling" in plain
        assert " · compiling · " in plain
        assert "test/orders" in plain
        assert "a.cpp" in plain
        # Identity / source / action use durable colours.
        assert as_info( "orders" ) in caption
        assert as_emphasised_plain( "compiling" ) in caption
        assert as_emphasised( as_info( "a.cpp" ) ) in caption
        # Pending product leaf is muted+bold (not info green).
        assert as_emphasised( as_subdued( "a.o" ) ) in caption
        assert as_emphasised( as_info( "a.o" ) ) not in caption
    finally:
        colouriser.use_colour = was


def test_format_terse_executing_caption_test_product_is_muted_bold():
    from cuppa.colourise import as_emphasised, as_info, as_subdued, colouriser

    was = colouriser.use_colour
    colouriser.enable()
    try:
        env = _env()
        env["sconscript_file"] = "./test/positions/sconscript"
        program = _node( "_build/gcc15_dbg/final/position_calculations" )
        # Locate tokens need abs_final_dir-style roots; force summary-free test
        # action with an explicit product path style.
        program.attributes.cuppa_terse_action = "test"
        caption = progress.format_terse_executing_caption(
                "./position_calculations", [ program ], [ program ], env,
        )
        plain = strip_ansi( caption )
        assert plain.startswith( "[....] " )
        assert "testing" in plain
        assert "ms" not in plain
        assert "cases" not in plain
        assert "assertions" not in plain
        assert "position_calculations" in plain
        assert as_emphasised( as_subdued( "position_calculations" ) ) in caption
        assert as_emphasised( as_info( "position_calculations" ) ) not in caption
    finally:
        colouriser.use_colour = was


def test_begin_end_refresh_cycles_outstanding_captions( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )

    env = _env()
    key_a = progress.begin_terse_executing(
            "g++ -c a.cpp", [ _node( "a.o" ) ], [ _node( "a.cpp" ) ], env,
    )
    key_b = progress.begin_terse_executing(
            "g++ -c b.cpp", [ _node( "b.o" ) ], [ _node( "b.cpp" ) ], env,
    )
    assert key_a is not None and key_b is not None
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[....]" in body
    assert "compiling" in body
    assert "b.cpp" in body or "a.cpp" in body

    progress.end_terse_executing( key_b )
    progress.refresh_terse_executing()
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[....]" in body
    assert "a.cpp" in body

    progress.end_terse_executing( key_a )
    progress.refresh_terse_executing()
    assert list( progress._outstanding ) == []  # noqa: SLF001


def test_begin_is_noop_without_terse_output( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )
    env = _env()
    env["terse_output"] = False
    assert progress.begin_terse_executing(
            "g++ -c a.cpp", [ _node() ], [ _node( "a.cpp" ) ], env,
    ) is None
    assert "[....]" not in stream.getvalue()


def test_write_terse_launch_drops_executing_caption( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )
    env = _env()
    progress.begin_terse_executing(
            "cmake --build x", [ _node( "stamp" ) ], [], env,
    )
    assert list( progress._outstanding )  # noqa: SLF001

    written = []
    monkeypatch.setattr(
            progress, "_write_terse_stdout",
            lambda text, *, dwell=True: written.append( text ),
    )
    progress.write_terse_launch( "cmake-build", "-B x", env, command="cmake --build x" )
    assert list( progress._outstanding ) == []  # noqa: SLF001
    assert written and "[launch]" in written[0]
