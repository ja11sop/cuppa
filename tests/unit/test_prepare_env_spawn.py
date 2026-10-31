#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json
import os
import sys

import pytest

import cuppa.cpp.run_boost_test as run_boost_test
import cuppa.cpp.run_patched_boost_test as run_patched_boost_test
import cuppa.cpp.run_process_test as run_process_test
import cuppa.output_processor as output_processor
from cuppa.output_processor import IncrementalSubProcess

pytestmark = pytest.mark.unit

PARENT_ONLY = "CUPPA_TEST_PARENT_ONLY_TOKEN"


class _SconsEnv( dict ):
    def get_option( self, name ):
        return None


def _construction_env( **extra ):
    construction = { "PATH": os.environ.get( "PATH", "" ) }
    construction.update( extra )
    return construction


def _add_marker( child_env ):
    child_env["CUPPA_PREPARED"] = "1"
    return child_env


def _child_environment( **kwargs ):
    lines = []
    script = "import json, os; print(json.dumps(dict(os.environ)))"
    IncrementalSubProcess.Popen2(
            lines.append,
            lines.append,
            [ sys.executable, "-c", script ],
            suppress_output=True,
            **kwargs
    )
    return json.loads( lines[0] )


@pytest.fixture
def parent_secret( monkeypatch ):
    monkeypatch.setenv( PARENT_ONLY, "secret" )


def test_step_runs_on_construction_env_and_does_not_widen_it( parent_secret ):
    construction = _construction_env( KEEP="construction" )

    child = _child_environment( scons_env=_SconsEnv( ENV=construction ), prepare_env=_add_marker )

    assert child["KEEP"] == "construction"
    assert child["CUPPA_PREPARED"] == "1"
    assert PARENT_ONLY not in child
    assert "CUPPA_PREPARED" not in construction


def test_step_respects_inherit_process_env( parent_secret ):
    child = _child_environment(
            scons_env=_SconsEnv( ENV=_construction_env() ),
            inherit_process_env=True,
            prepare_env=_add_marker,
    )

    assert child[PARENT_ONLY] == "secret"
    assert child["CUPPA_PREPARED"] == "1"


def test_step_runs_on_a_copy_of_an_explicit_env( parent_secret ):
    explicit = _construction_env( ONLY="explicit" )

    child = _child_environment( env=explicit, prepare_env=_add_marker )

    assert child["ONLY"] == "explicit"
    assert child["CUPPA_PREPARED"] == "1"
    assert PARENT_ONLY not in child
    assert "CUPPA_PREPARED" not in explicit


def test_step_is_skipped_when_no_env_was_chosen( monkeypatch ):
    calls = []

    def _record( child_env ):
        calls.append( child_env )
        return child_env

    seen = {}

    def _fake_popen( args, **kwargs ):
        seen.update( kwargs )
        raise OSError( "stop before spawning" )

    monkeypatch.setattr( output_processor.subprocess, "Popen", _fake_popen )
    with pytest.raises( OSError ):
        IncrementalSubProcess.Popen2( lambda line: None, lambda line: None, [ "true" ],
                                      suppress_output=True, prepare_env=_record )

    assert calls == []
    assert "env" not in seen


def _capture_spawn( monkeypatch, module ):
    seen = {}

    def _fake_popen2( stdout, stderr, args, **kwargs ):
        seen.update( kwargs )
        return 0

    monkeypatch.setattr( module.IncrementalSubProcess, "Popen2", staticmethod( _fake_popen2 ) )
    return seen


def _run( module, tmp_path, env ):
    program_path = str( tmp_path / "alpha" )
    if module is run_process_test:
        runner = module.RunProcessTest( "passed", str( tmp_path ) )
        runner._run_test( { "stdout": [], "stderr": [] }, False, program_path, "alpha", str( tmp_path ), env )
    elif module is run_boost_test:
        runner = module.RunBoostTest( "passed", str( tmp_path ) )
        runner._RunBoostTest__run_test( program_path, "alpha", str( tmp_path ), None, None, env )
    else:
        runner = module.RunPatchedBoostTest( "passed", str( tmp_path ) )
        runner._run_test( program_path, "alpha", str( tmp_path ), str( tmp_path ), None, None, env )


RUNNERS = [ run_process_test, run_boost_test, run_patched_boost_test ]


def _runner_id( module ):
    return module.__name__.rsplit( ".", 1 )[1]


@pytest.mark.parametrize( "module", RUNNERS, ids=_runner_id )
def test_runner_step_adds_only_the_gcov_prefix_under_cov( monkeypatch, tmp_path, module ):
    seen = _capture_spawn( monkeypatch, module )
    env = _SconsEnv( variant_actions={ "cov": True, "test": True }, abs_build_dir=str( tmp_path / "_build" ) )

    _run( module, tmp_path, env )

    prepared = seen["prepare_env"]( { "KEEP": "1" } )
    assert prepared == {
            "KEEP": "1",
            "GCOV_PREFIX": os.path.join( str( tmp_path / "_build" ), "gcov-data", "alpha" ),
            "GCOV_PREFIX_STRIP": "0",
    }
    assert seen["scons_env"] is env
    assert "env" not in seen


@pytest.mark.parametrize( "module", RUNNERS, ids=_runner_id )
def test_runner_has_no_step_without_cov( monkeypatch, tmp_path, module ):
    seen = _capture_spawn( monkeypatch, module )
    env = _SconsEnv( variant_actions={ "test": True }, abs_build_dir=str( tmp_path / "_build" ) )

    _run( module, tmp_path, env )

    assert seen["prepare_env"] is None
