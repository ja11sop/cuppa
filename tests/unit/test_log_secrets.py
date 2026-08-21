import io

import pytest

from cuppa import log
from cuppa.__main__ import MaskSecrets, run_scons


pytestmark = pytest.mark.unit


def test_register_and_mask_secrets():
    log.register_secret("super-secret-token", "XXXX")
    assert log.mask_secrets("using super-secret-token here") == "using XXXX here"
    log.unregister_secret("super-secret-token")
    assert log.mask_secrets("using super-secret-token here") == "using super-secret-token here"


def test_mask_secrets_wrapper_masks_token_env(monkeypatch):
    monkeypatch.setenv("MY_CI_TOKEN", "abc123xyz")
    masker = MaskSecrets()
    assert "abc123xyz" not in masker.mask("token=abc123xyz")
    assert "MY_CI_TOKEN" in masker.mask("token=abc123xyz")


def test_mask_secrets_wrapper_ignores_non_token_env(monkeypatch):
    monkeypatch.setenv("MY_PASSWORD", "hunter2")
    masker = MaskSecrets()
    assert masker.mask("password=hunter2") == "password=hunter2"


def test_mask_secrets_wrapper_skips_empty_token_value(monkeypatch):
    monkeypatch.setenv("EMPTY_TOKEN", "")
    masker = MaskSecrets()
    assert masker.mask("keep this intact") == "keep this intact"


class _Pipe(object):

    def __init__( self, text ):
        self._buffer = io.BytesIO( text.encode( 'utf-8' ) + b'\n' )

    def readline( self ):
        return self._buffer.readline()


class _FakeProcess(object):

    def __init__( self, stdout_text ):
        self.stdout = _Pipe( stdout_text )
        self.stderr = _Pipe( '' )
        self.returncode = 0

    def wait( self ):
        return self.returncode

    def kill( self ):
        return None

    def terminate( self ):
        return None


def test_run_scons_appends_cuppa_mode_and_masks_stdout( monkeypatch, capsys ):
    monkeypatch.setenv( "CI_JOB_TOKEN", "s3cret-value" )
    captured = {}

    def fake_popen( args, **kwargs ):
        captured['args'] = args
        return _FakeProcess( "token=s3cret-value" )

    monkeypatch.setattr( "cuppa.__main__.subprocess.Popen", fake_popen )
    monkeypatch.setattr( "cuppa.__main__.inject_inventory_ignore_errors", lambda args: args )

    assert run_scons( [ "-D", "--dbg" ] ) == 0
    assert captured['args'][0] == "scons"
    assert captured['args'][-1] == "--cuppa-mode"
    assert captured['args'][1:-1] == [ "-D", "--dbg" ]
    printed = capsys.readouterr().out
    assert "s3cret-value" not in printed
    assert "CI_JOB_TOKEN" in printed
