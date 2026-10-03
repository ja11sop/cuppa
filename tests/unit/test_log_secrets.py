import io
import sys

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


class _PipeBytes( object ):

    def __init__( self, payload ):
        self._buffer = io.BytesIO( payload )

    def readline( self ):
        return self._buffer.readline()


class _FakeProcess(object):

    def __init__( self, stdout_text ):
        self.stdout = _Pipe( stdout_text )
        self.stderr = _Pipe( '' )
        self.returncode = 0
        self.killed = False

    def wait( self ):
        return self.returncode

    def kill( self ):
        self.killed = True

    def terminate( self ):
        return None


def test_run_scons_appends_cuppa_mode_and_masks_stdout( monkeypatch, capsys ):
    monkeypatch.setenv( "CI_JOB_TOKEN", "s3cret-value" )
    captured = {}

    def fake_popen( args, **kwargs ):
        captured['args'] = args
        captured['env'] = kwargs.get( 'env' )
        return _FakeProcess( "token=s3cret-value" )

    monkeypatch.setattr( "cuppa.__main__.subprocess.Popen", fake_popen )
    monkeypatch.setattr( "cuppa.__main__.inject_inventory_ignore_errors", lambda args: args )

    assert run_scons( [ "-D", "--dbg" ] ) == 0
    assert captured['args'][0] == "scons"
    assert captured['args'][-1] == "--cuppa-mode"
    assert captured['env']['PYTHONIOENCODING'] == "utf-8"
    assert captured['env'].get( 'CUPPA_CONSOLE_ENCODING' ) == sys.stdout.encoding
    assert captured['args'][1:-1] == [ "-D", "--dbg" ]
    printed = capsys.readouterr().out
    assert "s3cret-value" not in printed
    assert "CI_JOB_TOKEN" in printed


def test_a_legacy_pipe_byte_does_not_drop_the_terse_status( monkeypatch, capsys ):
    """cp1252 middle dot used to abort the reader before ``[ok]`` was copied."""
    status = "[ok] sconscript \u00b7 compile hello.cpp\n".encode( "cp1252" )
    process = _FakeProcess( "" )
    process.stdout = _PipeBytes( status )

    def fake_popen( args, **kwargs ):
        return process

    monkeypatch.setattr( "cuppa.__main__.subprocess.Popen", fake_popen )
    monkeypatch.setattr( "cuppa.__main__.inject_inventory_ignore_errors", lambda args: args )

    assert run_scons( [] ) == 0
    assert process.killed is False
    printed = capsys.readouterr().out
    assert "[ok]" in printed
    assert "hello.cpp" in printed


class _Cp1252Stdout( object ):

    encoding = "cp1252"

    def __init__( self ):
        self.parts = []

    def write( self, text ):
        text.encode( "cp1252" )
        self.parts.append( text )

    def flush( self ):
        return None


def test_a_glyph_the_console_cannot_encode_does_not_stop_the_transcript( monkeypatch ):
    """Box drawing on a cp1252 console must not kill SCons or drop the heading."""
    out = _Cp1252Stdout()
    monkeypatch.setattr( "cuppa.__main__.sys.stdout", out )
    process = _FakeProcess( "" )
    process.stdout = _PipeBytes( "  \u251c\u2500\u2500 BY TOOLCHAIN VARIANT\n".encode( "utf-8" ) )

    def fake_popen( args, **kwargs ):
        return process

    monkeypatch.setattr( "cuppa.__main__.subprocess.Popen", fake_popen )
    monkeypatch.setattr( "cuppa.__main__.inject_inventory_ignore_errors", lambda args: args )

    assert run_scons( [] ) == 0
    assert process.killed is False
    printed = "".join( out.parts )
    assert "BY TOOLCHAIN VARIANT" in printed
    assert "\u251c" not in printed
