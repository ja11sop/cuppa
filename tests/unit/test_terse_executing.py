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
def _reset( monkeypatch ):
    hb.reset()
    progress.reset_terse_executing()
    # Unit tests expect synchronous captions unless a case sets a delay.
    monkeypatch.setattr( progress, "_OUTSTANDING_ARM_S", 0 )
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
    # Verb-object: progressive the head.
    assert progress.progressive_terse_action( "compile-scss" ) == "compiling-scss"
    assert progress.progressive_terse_action( "link-shared" ) == "linking-shared"
    assert progress.progressive_terse_action( "remove-empty" ) == "removing-empty"
    assert progress.progressive_terse_action( "collate-coverage" ) == "collating-coverage"
    assert progress.progressive_terse_action( "build-b2" ) == "building-b2"
    # Object-verb: progressive the tail (not the qualifier).
    assert progress.progressive_terse_action( "test-index" ) == "test-indexing"
    assert progress.progressive_terse_action( "test-report" ) == "test-reporting"
    assert progress.progressive_terse_action( "coverage-index" ) == "coverage-indexing"
    assert progress.progressive_terse_action( "cmake-build" ) == "launching-cmake-build"
    assert progress.progressive_terse_action( "cmake-configure" ) == "launching-cmake-configure"
    assert progress.progressive_terse_action( "cmake-install" ) == "launching-cmake-install"
    assert progress.progressive_terse_action( "b2" ) == "launching-b2"
    assert progress.progressive_terse_action( "module-map" ) == "module-mapping"
    assert progress.progressive_terse_action( "bitten-report" ) == "bitten-reporting"
    assert progress.progressive_terse_action( "test" ) == "running-test"
    assert progress.progressive_terse_action( "test-case" ) == "running-test-case"
    assert progress.progressive_terse_action( "coverage" ) == "running-coverage"
    assert progress.progressive_terse_action( "benchmark" ) == "running-benchmark"
    assert progress.progressive_terse_action( "cxx-profiles" ) == "enabling-cxx-profiles"


def test_executing_badge_single_and_parallel():
    assert progress.executing_badge() == "[....]"
    assert progress.executing_badge( index=1, total=1 ) == "[....]"
    assert progress.executing_badge( index=3, total=5 ) == "[...3]"
    assert progress.executing_badge( index=12, total=20 ) == "[..12]"
    assert progress.executing_badge( index=123, total=200 ) == "[.123]"
    assert progress.executing_badge( index=1234, total=2000 ) == "[1234]"
    assert progress.executing_badge( index=12345, total=20000 ) == "[2345]"
    assert len( progress.executing_badge( index=3, total=5 ) ) == progress._STATUS_WIDTH


def test_format_terse_executing_caption_aligns_and_progresses():
    from cuppa.colourise import (
            as_emphasised, as_info, as_subdued, colouriser,
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
        # Identity / source use durable colours. The in-flight verb and the
        # pending product leaf are muted+bold (not plain bold / info green).
        assert as_info( "orders" ) in caption
        assert as_emphasised( as_subdued( "compiling" ) ) in caption
        assert as_emphasised( as_info( "a.cpp" ) ) in caption
        assert as_emphasised( as_subdued( "a.o" ) ) in caption
        assert as_emphasised( as_info( "a.o" ) ) not in caption
    finally:
        colouriser.use_colour = was


def test_format_terse_executing_caption_parallel_badge():
    env = _env()
    caption = progress.format_terse_executing_caption(
            "g++ -c a.cpp -o a.o", [ _node() ], [ _node( "a.cpp" ) ], env,
            index=3, total=5,
    )
    plain = strip_ansi( caption )
    assert plain.startswith( "[...3] " )
    assert "compiling" in plain


def test_format_terse_executing_caption_execute_copy_recovers_paths():
    """``Execute(Copy(...))`` passes empty target/source — paths are in the text."""
    env = _env()
    env["abs_final_dir"] = "/proj/_build/gcc15_dbg/final"
    env["final_dir"] = "_build/gcc15_dbg/final"
    dest = "/proj/_build/gcc15_dbg/final/prices.json"
    src = "/proj/test/prices/prices.json"
    caption = progress.format_terse_executing_caption(
            'Copy("{}", "{}")'.format( dest, src ),
            [],
            [],
            env,
    )
    plain = strip_ansi( caption )
    assert plain.startswith( "[....] " )
    assert "copying" in plain
    assert "prices.json" in plain
    assert "→" in plain
    # Must not stop at the action word with no file cell.
    assert not plain.rstrip().endswith( "copying" )


def test_wrapped_execute_copy_does_not_leak_outstanding( monkeypatch, capsys ):
    """Finished ``Execute(Copy)`` must leave the outstanding set (not queue)."""
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )
    monkeypatch.setattr( progress, "_arm_outstanding_rotate", lambda: None )

    class ExecuteEnv( dict ):
        def Execute( self, action ):
            progress.terse_print_cmd_line( action, [], [], self )
            return 0

    env = ExecuteEnv( _env() )
    env["terse_output"] = True
    env["abs_final_dir"] = "/proj/_build/gcc15_dbg/final"
    progress.enable_terse_python_actions( env )

    parent_key = progress.begin_terse_executing(
            "g++ -c parent.cpp", [ _node( "parent.o" ) ], [ _node( "parent.cpp" ) ], env,
    )
    assert parent_key is not None
    assert len( progress._outstanding ) == 1  # noqa: SLF001

    env.Execute( 'Copy("/proj/_build/gcc15_dbg/final/a.json", "/proj/a.json")' )
    env.Execute( 'Copy("/proj/_build/gcc15_dbg/final/b.json", "/proj/b.json")' )

    # Nested copies finished — only the parent compile may remain in-flight.
    assert list( progress._outstanding.keys() ) == [ parent_key ]  # noqa: SLF001
    out = capsys.readouterr().out
    assert out.count( " · copy · " ) == 2

    progress.end_terse_executing( parent_key )
    progress.refresh_terse_executing()
    assert list( progress._outstanding ) == []  # noqa: SLF001


def test_fast_action_ends_before_arm_never_paints( monkeypatch ):
    """Actions that finish inside the arm delay skip the status row entirely."""
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )
    monkeypatch.setattr( progress, "_OUTSTANDING_ARM_S", 0.20 )

    scheduled = []

    def capture_timer( delay, fn, args=None ):
        scheduled.append( ( delay, fn, args or () ) )

        class _T( object ):
            def start( self ):
                return None

            def cancel( self ):
                return None

            daemon = True

        return _T()

    monkeypatch.setattr( progress.threading, "Timer", capture_timer )

    env = _env()
    key = progress.begin_terse_executing(
            'Copy("/proj/a", "/proj/b")', [], [], env,
    )
    assert key is not None
    assert key in progress._pending_outstanding  # noqa: SLF001
    assert list( progress._outstanding ) == []  # noqa: SLF001
    assert "[....]" not in stream.getvalue()
    assert scheduled and scheduled[0][0] == 0.20

    progress.end_terse_executing( key )
    progress.refresh_terse_executing()
    # Arm callback must be a no-op after end.
    delay, fn, args = scheduled[0]
    fn( *args )
    assert list( progress._outstanding ) == []  # noqa: SLF001
    assert list( progress._pending_outstanding ) == []  # noqa: SLF001
    assert "[....]" not in stream.getvalue()


def test_terse_interrupt_stream_clears_status_before_stderr( monkeypatch ):
    """``scons: ***`` must not concatenate onto a live ``[....]`` caption."""
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )
    env = _env()
    progress.begin_terse_executing(
            "g++ -c a.cpp", [ _node( "a.o" ) ], [ _node( "a.cpp" ) ], env,
    )
    assert "[....]" in strip_ansi( stream.getvalue() )
    assert hb.status_row_active()

    written = []

    class Real( object ):
        def write( self, text ):
            written.append( text )
            return len( text )

        def flush( self ):
            return None

    wrapper = progress._TerseInterruptStream( Real() )
    wrapper.write( "scons: *** [_build/test/a] Error 1\n" )
    assert written == [ "scons: *** [_build/test/a] Error 1\n" ]
    # Status row cleared so the error cannot glue onto the caption.
    assert hb._last_line == ""  # noqa: SLF001


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
        assert "running-test" in plain
        assert "ms" not in plain
        assert "cases" not in plain
        assert "assertions" not in plain
        assert "position_calculations" in plain
        assert as_emphasised( as_subdued( "position_calculations" ) ) in caption
        assert as_emphasised( as_info( "position_calculations" ) ) not in caption
    finally:
        colouriser.use_colour = was


def test_begin_end_refresh_retains_displayed_job( monkeypatch ):
    """Appends / durable refresh keep the carousel member; removal slides next in."""
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )
    # Do not let the dwell timer fire during the test.
    monkeypatch.setattr( progress, "_arm_outstanding_rotate", lambda: None )

    env = _env()
    key_a = progress.begin_terse_executing(
            "g++ -c a.cpp", [ _node( "a.o" ) ], [ _node( "a.cpp" ) ], env,
    )
    key_b = progress.begin_terse_executing(
            "g++ -c b.cpp", [ _node( "b.o" ) ], [ _node( "b.cpp" ) ], env,
    )
    assert key_a is not None and key_b is not None
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    # First armed job stays shown; count updates; badge is 1-based index.
    assert "[...1]" in body
    assert "a.cpp" in body
    assert hb.compact_bridge() == "2"
    assert "→" not in body.split( "[", 1 )[0]

    # Ending the non-displayed job must not steal the carousel away from a.
    progress.end_terse_executing( key_b )
    progress.refresh_terse_executing()
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[....]" in body
    assert "a.cpp" in body
    assert hb.compact_bridge() is None

    progress.end_terse_executing( key_a )
    progress.refresh_terse_executing()
    assert list( progress._outstanding ) == []  # noqa: SLF001
    assert hb.compact_bridge() is None


def test_removing_displayed_job_lands_on_successor( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )
    monkeypatch.setattr( progress, "_arm_outstanding_rotate", lambda: None )

    env = _env()
    key_a = progress.begin_terse_executing(
            "g++ -c a.cpp", [ _node( "a.o" ) ], [ _node( "a.cpp" ) ], env,
    )
    key_b = progress.begin_terse_executing(
            "g++ -c b.cpp", [ _node( "b.o" ) ], [ _node( "b.cpp" ) ], env,
    )
    key_c = progress.begin_terse_executing(
            "g++ -c c.cpp", [ _node( "c.o" ) ], [ _node( "c.cpp" ) ], env,
    )
    assert key_a and key_b and key_c
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[...1]" in body and "a.cpp" in body

    # Drop the displayed job — successor (b) slides into the same slot.
    progress.end_terse_executing( key_a )
    progress.refresh_terse_executing()
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[...1]" in body
    assert "b.cpp" in body
    assert hb.compact_bridge() == "2"

    # Append must not jump the carousel to the newest job.
    key_d = progress.begin_terse_executing(
            "g++ -c d.cpp", [ _node( "d.o" ) ], [ _node( "d.cpp" ) ], env,
    )
    assert key_d
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[...1]" in body
    assert "b.cpp" in body
    assert hb.compact_bridge() == "3"


def test_parallel_dwell_rotates_displayed_job( monkeypatch ):
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )

    fired = []

    def capture_arm():
        fired.append( True )

    monkeypatch.setattr( progress, "_arm_outstanding_rotate", capture_arm )

    env = _env()
    progress.begin_terse_executing(
            "g++ -c a.cpp", [ _node( "a.o" ) ], [ _node( "a.cpp" ) ], env,
    )
    progress.begin_terse_executing(
            "g++ -c b.cpp", [ _node( "b.o" ) ], [ _node( "b.cpp" ) ], env,
    )
    progress.begin_terse_executing(
            "g++ -c c.cpp", [ _node( "c.o" ) ], [ _node( "c.cpp" ) ], env,
    )
    assert fired  # armed while N > 1
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    # Carousel stays on the first member; count reflects all three.
    assert "[...1]" in body
    assert "a.cpp" in body
    assert hb.compact_bridge() == "3"

    # Repaint without advance must not rotate.
    progress.refresh_terse_executing()
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[...1]" in body
    assert "a.cpp" in body

    progress.refresh_terse_executing( advance=True )
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[...2]" in body
    assert "b.cpp" in body

    progress.refresh_terse_executing( advance=True )
    body = strip_ansi( stream.getvalue().split( "\r" )[-1] )
    assert "[...3]" in body
    assert "c.cpp" in body


def test_repaint_does_not_reset_dwell_timer( monkeypatch ):
    """Fast durable refreshes must not restart the ~2s carousel dwell."""
    stream = io.StringIO()
    clock = FakeClock()
    _arm_status_row( stream, clock, monkeypatch )

    started = []
    cancelled = []

    class _Timer( object ):
        def __init__( self, delay, fn, args=None ):
            self.delay = delay
            self.fn = fn
            self.daemon = False

        def start( self ):
            started.append( self )

        def cancel( self ):
            cancelled.append( self )

    monkeypatch.setattr( progress.threading, "Timer", _Timer )

    env = _env()
    progress.begin_terse_executing(
            "g++ -c a.cpp", [ _node( "a.o" ) ], [ _node( "a.cpp" ) ], env,
    )
    progress.begin_terse_executing(
            "g++ -c b.cpp", [ _node( "b.o" ) ], [ _node( "b.cpp" ) ], env,
    )
    dwells = [ timer for timer in started if timer.fn is progress._on_outstanding_rotate ]
    assert len( dwells ) == 1
    assert dwells[0].delay == progress._OUTSTANDING_DWELL_S
    dwell = dwells[0]

    # Several repaints (durable [ok] chase / count updates) must keep the same timer.
    progress.refresh_terse_executing()
    progress.refresh_terse_executing()
    progress.begin_terse_executing(
            "g++ -c c.cpp", [ _node( "c.o" ) ], [ _node( "c.cpp" ) ], env,
    )
    dwells = [ timer for timer in started if timer.fn is progress._on_outstanding_rotate ]
    assert dwells == [ dwell ]
    assert dwell not in cancelled

    # Dropping to one job cancels the dwell.
    keys = list( progress._outstanding )  # noqa: SLF001
    progress.end_terse_executing( keys[1] )
    progress.end_terse_executing( keys[2] )
    progress.refresh_terse_executing()
    assert dwell in cancelled


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
    assert hb.compact_bridge() is None


def test_compact_bridge_right_aligns_job_count( monkeypatch ):
    """Multi-digit job counts grow left; ones align with the ``→`` column."""
    monkeypatch.setattr( hb, "_arrow_column", lambda: 14 )
    hb.set_presentation( style="pulse", compact=True )
    hb.set_compact_bridge( None )
    arrow = hb._with_aligned_bridge( "|--------•|" )
    assert arrow.endswith( "→ " )
    arrow_at = len( arrow ) - 2

    hb.set_compact_bridge( "5" )
    one = hb._with_aligned_bridge( "|--------•|" )
    assert one.endswith( "5 " )
    assert len( one ) - 2 == arrow_at

    hb.set_compact_bridge( "12" )
    two = hb._with_aligned_bridge( "|--------•|" )
    assert two.endswith( "12 " )
    assert len( two ) - 2 == arrow_at  # rightmost digit on the arrow column
