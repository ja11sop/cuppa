#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for scripts.local_gate helpers (no full suite run)."""

from __future__ import annotations

import sys

import pytest

from scripts import local_gate


pytestmark = pytest.mark.unit


def test_module_imports_and_exit_codes():
    assert local_gate.EXIT_OK == 0
    assert local_gate.EXIT_STEP_FAILED == 1
    assert local_gate.EXIT_ENV_BROKEN == 2
    assert local_gate.REPO_ROOT.is_dir()


def test_running_under_repo_venv_matches_resolved_executable( monkeypatch, tmp_path ):
    venv_python = tmp_path / 'venv' / 'bin' / 'python'
    venv_python.parent.mkdir( parents=True )
    venv_python.write_text( '', encoding='utf-8' )
    monkeypatch.setattr( local_gate, 'REPO_ROOT', tmp_path )
    monkeypatch.delenv( 'VIRTUAL_ENV', raising=False )

    assert local_gate.running_under_repo_venv( str( venv_python ) ) is True
    assert local_gate.running_under_repo_venv( str( tmp_path / 'other' / 'python' ) ) is False


def test_running_under_repo_venv_accepts_virtual_env( monkeypatch, tmp_path ):
    venv_python = tmp_path / 'venv' / 'bin' / 'python'
    venv_python.parent.mkdir( parents=True )
    venv_python.write_text( '', encoding='utf-8' )
    monkeypatch.setattr( local_gate, 'REPO_ROOT', tmp_path )
    monkeypatch.setenv( 'VIRTUAL_ENV', str( tmp_path / 'venv' ) )

    assert local_gate.running_under_repo_venv( str( tmp_path / 'elsewhere' ) ) is True


def test_preflight_fails_when_venv_missing( monkeypatch, tmp_path, capsys ):
    monkeypatch.setattr( local_gate, 'REPO_ROOT', tmp_path )
    code = local_gate.preflight( need_cxx=False )
    assert code == local_gate.EXIT_ENV_BROKEN
    err = capsys.readouterr().err
    assert 'env broken' in err
    assert 'venv missing' in err


def test_preflight_fails_when_not_under_venv( monkeypatch, tmp_path, capsys ):
    venv_python = tmp_path / 'venv' / 'bin' / 'python'
    venv_python.parent.mkdir( parents=True )
    venv_python.write_text( '', encoding='utf-8' )
    monkeypatch.setattr( local_gate, 'REPO_ROOT', tmp_path )
    monkeypatch.delenv( 'VIRTUAL_ENV', raising=False )
    monkeypatch.setattr( sys, 'executable', str( tmp_path / 'host-python' ) )

    code = local_gate.preflight( need_cxx=False )
    assert code == local_gate.EXIT_ENV_BROKEN
    assert 'not running under' in capsys.readouterr().err


def test_subprocess_smoke_treats_import_error_as_env_broken( monkeypatch, capsys ):
    class Result:
        returncode = 1
        stdout = "ModuleNotFoundError: No module named 'six'\n"

    monkeypatch.setattr(
            local_gate.subprocess,
            'run',
            lambda *args, **kwargs: Result(),
    )
    code = local_gate._subprocess_cuppa_smoke()
    assert code == local_gate.EXIT_ENV_BROKEN
    assert 'env broken' in capsys.readouterr().err


def test_subprocess_smoke_allows_non_import_configure_noise( monkeypatch ):
    class Result:
        returncode = 2
        stdout = 'cuppa: [error] Options Error: no toolchains matched\n'

    monkeypatch.setattr(
            local_gate.subprocess,
            'run',
            lambda *args, **kwargs: Result(),
    )
    assert local_gate._subprocess_cuppa_smoke() == local_gate.EXIT_OK


def test_build_parser_modes_are_mutually_exclusive():
    parser = local_gate.build_parser()
    args = parser.parse_args( ['--unit'] )
    assert args.unit is True
    assert args.integration is False
    with pytest.raises( SystemExit ):
        parser.parse_args( ['--unit', '--integration'] )


def test_main_preflight_only_skips_gate( monkeypatch ):
    calls = []

    monkeypatch.setattr( local_gate, 'maybe_reexec_into_venv', lambda argv: None )
    monkeypatch.setattr(
            local_gate,
            'preflight',
            lambda need_cxx: calls.append( ( 'preflight', need_cxx ) ) or local_gate.EXIT_OK,
    )

    def boom( **kwargs ):
        raise AssertionError( 'run_gate should not run' )

    monkeypatch.setattr( local_gate, 'run_gate', boom )
    code = local_gate.main( ['local_gate', '--preflight-only', '--no-reexec'] )
    assert code == local_gate.EXIT_OK
    assert calls == [ ( 'preflight', False ) ]


def test_main_unit_runs_lint_and_unit( monkeypatch ):
    seen = {}

    monkeypatch.setattr( local_gate, 'maybe_reexec_into_venv', lambda argv: None )

    def fake_preflight( need_cxx ):
        seen['cxx'] = need_cxx
        return local_gate.EXIT_OK

    def fake_gate( *, unit, integration, lint, serial_integration=False ):
        seen['gate'] = ( unit, integration, lint, serial_integration )
        return local_gate.EXIT_OK

    monkeypatch.setattr( local_gate, 'preflight', fake_preflight )
    monkeypatch.setattr( local_gate, 'run_gate', fake_gate )
    code = local_gate.main( ['local_gate', '--unit', '--no-reexec'] )
    assert code == local_gate.EXIT_OK
    assert seen['cxx'] is False
    assert seen['gate'] == ( True, False, True, False )


def test_main_default_needs_cxx_and_full_gate( monkeypatch ):
    seen = {}

    monkeypatch.setattr( local_gate, 'maybe_reexec_into_venv', lambda argv: None )

    def fake_preflight( need_cxx ):
        seen['cxx'] = need_cxx
        return local_gate.EXIT_OK

    def fake_gate( *, unit, integration, lint, serial_integration=False ):
        seen['gate'] = ( unit, integration, lint, serial_integration )
        return local_gate.EXIT_OK

    monkeypatch.setattr( local_gate, 'preflight', fake_preflight )
    monkeypatch.setattr( local_gate, 'run_gate', fake_gate )
    code = local_gate.main( ['local_gate', '--no-reexec'] )
    assert code == local_gate.EXIT_OK
    assert seen['cxx'] is True
    assert seen['gate'] == ( True, True, True, False )


def test_main_serial_integration_flag( monkeypatch ):
    seen = {}

    monkeypatch.setattr( local_gate, 'maybe_reexec_into_venv', lambda argv: None )
    monkeypatch.setattr(
            local_gate, 'preflight', lambda need_cxx: local_gate.EXIT_OK
    )

    def fake_gate( *, unit, integration, lint, serial_integration=False ):
        seen['serial'] = serial_integration
        return local_gate.EXIT_OK

    monkeypatch.setattr( local_gate, 'run_gate', fake_gate )
    code = local_gate.main(
            ['local_gate', '--integration', '--serial-integration', '--no-reexec']
    )
    assert code == local_gate.EXIT_OK
    assert seen['serial'] is True


def test_integration_pytest_cmd_parallel_when_xdist( monkeypatch ):
    monkeypatch.setattr( local_gate, 'xdist_available', lambda: True )
    monkeypatch.setattr( local_gate, 'integration_worker_count', lambda: 4 )
    cmd = local_gate.integration_pytest_cmd( serial=False )
    assert '-m' in cmd and 'integration' in cmd
    assert cmd[ cmd.index( '-n' ) + 1 ] == '4'
    assert '--dist=loadfile' in cmd


def test_integration_pytest_cmd_serial_skips_xdist( monkeypatch ):
    monkeypatch.setattr( local_gate, 'xdist_available', lambda: True )
    cmd = local_gate.integration_pytest_cmd( serial=True )
    assert '-n' not in cmd
    assert cmd[-2:] == [ '-m', 'integration' ]


def test_integration_worker_count_caps_at_four( monkeypatch ):
    monkeypatch.setattr( local_gate.os, 'cpu_count', lambda: 32 )
    assert local_gate.integration_worker_count() == 4
    monkeypatch.setattr( local_gate.os, 'cpu_count', lambda: 2 )
    assert local_gate.integration_worker_count() == 1
    monkeypatch.setattr( local_gate.os, 'cpu_count', lambda: 6 )
    assert local_gate.integration_worker_count() == 3
