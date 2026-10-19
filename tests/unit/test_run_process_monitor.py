#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""``Monitor`` / process transcript under terse and quiet+TTY."""

import pytest

from cuppa.method_helpers import run_process as rp
from cuppa.utility import heartbeat as hb


pytestmark = pytest.mark.unit


class _Env( dict ):
    def get( self, key, default=None ):
        return dict.get( self, key, default )


def test_short_run_summary_truncates():
    long_cmd = "docker run " + ( "x" * 80 )
    shown = rp.short_run_summary( long_cmd, limit=40 )
    assert len( shown ) == 40
    assert shown.endswith( "…" )


def test_short_run_summary_keeps_full_command_without_limit():
    long_cmd = "docker run --rm -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:17.6"
    assert rp.short_run_summary( long_cmd ) == long_cmd


def test_fit_terse_file_field_is_opt_in( monkeypatch ):
    """Default paint keeps the full command; truncate_file=True may ellipsis-fit."""
    from types import SimpleNamespace

    from cuppa import progress
    from cuppa.utility import terminal as term

    monkeypatch.setattr( term, "terminal_columns", lambda: 100 )
    head = [ "  1/2 · 10% ", "[ok]" ]
    fields = [ "test", "gcc15_dbg", "run", "262 ms" ]
    long_cmd = (
            'docker run --rm -p "54301:5432" -d '
            "-e POSTGRES_PASSWORD=password -e POSTGRES_HOST_AUTH_METHOD=md5 postgres:17.6"
    )
    fitted = progress._fit_terse_file_field( long_cmd, head, fields )
    assert fitted.endswith( "…" )
    assert "docker run" in fitted

    node = SimpleNamespace(
            path="stamp.success",
            attributes=SimpleNamespace(
                    cuppa_terse_action="run",
                    cuppa_terse_summary=long_cmd,
            ),
    )
    env = _Env(
            terse_output=True,
            sconscript_file="./test/orders/sconscript",
            variant_dir_name="gcc15_dbg",
            current_build_dir=".",
            base_path=".",
            offset_dir=".",
            abs_final_dir=".",
            final_dir=".",
    )
    line = progress.format_terse_line(
            "ok", "RunProcess", [ node ], [], env, duration="262 ms",
    )
    assert long_cmd in line
    assert "…" not in line

    truncated = progress.format_terse_line(
            "ok", "RunProcess", [ node ], [], env, duration="262 ms",
            truncate_file=True,
    )
    assert truncated.endswith( "…" ) or "…" in truncated
    assert long_cmd not in truncated


def test_monitor_silent_under_terse( monkeypatch ):
    from cuppa import progress

    written = []

    def _capture( text, *, dwell=True ):
        written.append( text )

    monkeypatch.setattr( hb, "write_transcript", _capture )
    env = _Env( terse_output=True )
    monitor = rp.Monitor( "docker-run", env )
    monitor.start()
    monitor.stop( status="success" )
    assert written == []
    # Wall time is stashed for the durable ``[ok]`` line; this unit has none.
    progress.take_terse_duration()


def test_monitor_clears_status_before_banner( monkeypatch ):
    calls = []

    def _capture( text, *, dwell=True ):
        calls.append( text )

    monkeypatch.setattr( hb, "write_transcript", _capture )
    env = _Env( terse_output=False )
    monitor = rp.Monitor( "tool", env )
    assert any( "Running Process" in part for part in calls )
    monitor.start()
    # Advance the timer so stop has elapsed times to format.
    monitor.stop( status="success" )
    assert any( " = done = " in part for part in calls )
    assert all( not part.startswith( "Running Process" ) or "\n" in calls[0] for part in calls )


def test_process_stdout_routes_through_transcript( monkeypatch, tmp_path ):
    written = []

    def _capture( text, *, dwell=True ):
        written.append( text )

    monkeypatch.setattr( hb, "write_transcript", _capture )
    log = tmp_path / "out.log"
    sink = rp.ProcessStdout( show_output=True, log=str( log ) )
    sink( "hello from child" )
    sink.__exit__( None, None, None )
    assert written == [ "hello from child\n" ]
    assert "hello from child" in log.read_text( encoding="utf-8" )


def test_process_stdout_suppressed_still_logs( tmp_path ):
    log = tmp_path / "out.log"
    sink = rp.ProcessStdout( show_output=False, log=str( log ) )
    sink( "secret" )
    sink.__exit__( None, None, None )
    assert "secret" in log.read_text( encoding="utf-8" )


def test_run_terse_summary_skips_format_holes():
    from cuppa.methods.run import _run_terse_summary

    assert _run_terse_summary( "docker run {image}" ) is None
    assert _run_terse_summary( "docker stop box" ) == "docker stop box"

    def helper( target, source, env ):
        return 0

    assert _run_terse_summary( helper ) == "helper"


def test_run_terse_action_is_run_under_test_variant():
    """Fixtures via ``env.Run`` under ``--test`` spell ``run``, not ``test``."""
    from cuppa.methods.run import _run_terse_action

    env = _Env( variant_actions={ "test": True, "force_test": True } )
    assert _run_terse_action( env ) == "run"
    env = _Env( variant_actions={ "benchmark": True } )
    assert _run_terse_action( env ) == "benchmark"
    env = _Env( variant_actions={ "run": True } )
    assert _run_terse_action( env ) == "run"


def test_monitor_stashes_duration_under_terse( monkeypatch ):
    stashed = []

    monkeypatch.setattr(
            rp.cuppa.progress, "stash_terse_duration",
            lambda nanos: stashed.append( nanos ),
    )
    env = _Env( terse_output=True )
    monitor = rp.Monitor( "docker-run", env )
    monitor.start()
    monitor.stop( status="success" )
    assert len( stashed ) == 1
    assert stashed[0] >= 0


def test_run_passes_suppress_output_to_popen2( monkeypatch, tmp_path ):
    """Terse must suppress ``Popen2`` argv echo (bare ``docker run …`` line)."""
    captured = {}

    def _fake_popen2( stdout_processor, stderr_processor, args_list, **kwargs ):
        captured.update( kwargs )
        return 0

    monkeypatch.setattr(
            rp.IncrementalSubProcess, "Popen2", staticmethod( _fake_popen2 )
    )
    action = rp.RunProcessAction( str( tmp_path ) )
    program = str( tmp_path / "tool" )
    ( tmp_path / "tool.stdout.log" ).write_text( "", encoding="utf-8" )
    ( tmp_path / "tool.stderr.log" ).write_text( "", encoding="utf-8" )
    action._run(
            suppress_output=True,
            program_path=program,
            command="true",
            working_dir=str( tmp_path ),
            env=_Env( terse_output=True ),
    )
    assert captured.get( "suppress_output" ) is True
