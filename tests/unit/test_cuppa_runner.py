#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for integration cuppa runner helpers."""

import os
import subprocess

import pytest

from tests.helpers import cuppa_runner
from tests.helpers.toolchains import REPO_ROOT


pytestmark = pytest.mark.unit


def test_default_run_cuppa_timeout_is_longer_on_windows( monkeypatch ):
    monkeypatch.setattr( cuppa_runner.os, 'name', 'nt' )
    assert cuppa_runner.default_run_cuppa_timeout() == 360
    monkeypatch.setattr( cuppa_runner.os, 'name', 'posix' )
    assert cuppa_runner.default_run_cuppa_timeout() == 180


def test_run_cuppa_uses_platform_default_timeout( monkeypatch, tmp_path ):
    captured = {}

    def fake_run( args, cwd=None, env=None, timeout=None, **kwargs ):
        captured['timeout'] = timeout
        return subprocess.CompletedProcess( args, 0, stdout='', stderr='' )

    monkeypatch.setattr( cuppa_runner, 'require_cxx', lambda: None )
    monkeypatch.setattr( cuppa_runner, 'default_run_cuppa_timeout', lambda: 360 )
    monkeypatch.setattr( subprocess, 'run', fake_run )

    cuppa_runner.run_cuppa( tmp_path / 'project', '--dbg' )
    assert captured['timeout'] == 360


def test_run_cuppa_honours_explicit_timeout( monkeypatch, tmp_path ):
    captured = {}

    def fake_run( args, cwd=None, env=None, timeout=None, **kwargs ):
        captured['timeout'] = timeout
        return subprocess.CompletedProcess( args, 0, stdout='', stderr='' )

    monkeypatch.setattr( cuppa_runner, 'require_cxx', lambda: None )
    monkeypatch.setattr( subprocess, 'run', fake_run )

    cuppa_runner.run_cuppa( tmp_path / 'project', '--dbg', timeout=120 )
    assert captured['timeout'] == 120


def test_run_cuppa_keeps_repo_root_when_extra_pythonpath( monkeypatch, tmp_path ):
    """Plugin tests put a site-packages first; REPO_ROOT must remain importable."""
    captured = {}

    def fake_run( args, cwd=None, env=None, **kwargs ):
        captured['env'] = env
        return subprocess.CompletedProcess( args, 0, stdout='', stderr='' )

    monkeypatch.setattr( cuppa_runner, 'require_cxx', lambda: None )
    monkeypatch.setattr( subprocess, 'run', fake_run )

    plugin_site = str( tmp_path / 'plugin_site' )
    cuppa_runner.run_cuppa(
            tmp_path / 'project',
            '--dbg',
            extra_env={ 'PYTHONPATH': plugin_site },
    )
    parts = captured['env']['PYTHONPATH'].split( os.pathsep )
    assert parts[0] == plugin_site
    assert str( REPO_ROOT ) in parts
