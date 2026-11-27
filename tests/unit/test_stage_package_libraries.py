#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for package shared-library stage / collect helpers."""

from pathlib import Path

import pytest

from cuppa.package_managers.package_link_libs import (
        _LINK_CONTRIB_KEY,
        record_package_link_contribution,
)
from cuppa.package_managers.stage_package_libraries import (
        collect_package_libraries,
        ensure_package_runtime_rpath,
        package_runtime_rpath_linkflags,
        package_shared_library_files,
        should_stage_package_libraries,
        stage_directory_for_program,
        stage_package_libraries_for_programs,
)


pytestmark = pytest.mark.unit


class _FakeNode:
    def __init__( self, path, env=None ):
        self._path = str( path )
        self.env = env

    def get_abspath( self ):
        return self._path

    def get_build_env( self ):
        return self.env

    def __str__( self ):
        return self._path


class _FakeEnv( dict ):
    def __init__( self, **kwargs ):
        super().__init__( **kwargs )
        self.installed = []
        self.requires = []
        self.cleaned = []
        self.appended_unique = []

    def AppendUnique( self, **kwargs ):
        self.appended_unique.append( kwargs )
        for key, value in kwargs.items():
            current = list( self.get( key ) or [] )
            items = value if isinstance( value, ( list, tuple ) ) else [ value ]
            for item in items:
                if item not in current:
                    current.append( item )
            self[key] = current

    def Dir( self, path ):
        return _FakeNode( path )

    def Install( self, dest, source ):
        dest_path = dest.get_abspath() if hasattr( dest, "get_abspath" ) else str( dest )
        node = _FakeNode( str( Path( dest_path ) / Path( str( source ) ).name ) )
        self.installed.append( ( dest_path, str( source ) ) )
        return [ node ]

    def Requires( self, target, dependency ):
        self.requires.append( ( target, dependency ) )

    def Clean( self, target, files ):
        self.cleaned.append( ( target, files ) )


def _env_with_shared( tmp_path: Path, stem="widget", library_prefix="" ):
    lib_dir = tmp_path / "pkg" / "lib"
    lib_dir.mkdir( parents=True )
    so = lib_dir / "lib{}.so".format( stem if not library_prefix else library_prefix + stem )
    so.write_text( "shared", encoding="utf-8" )
    versioned = lib_dir / ( so.name + ".1" )
    versioned.write_text( "shared1", encoding="utf-8" )

    env = _FakeEnv(
            LIBPREFIX="lib",
            LIBSUFFIX=".a",
            SHLIBPREFIX="lib",
            SHLIBSUFFIX=".so",
    )
    record_package_link_contribution(
            env,
            "widget",
            shared=[ stem ],
            libpath=[ str( lib_dir ) ],
            library_prefix=library_prefix,
    )
    return env, lib_dir, so, versioned


def test_package_shared_library_files_includes_sonames( tmp_path: Path ):
    env, _lib_dir, so, versioned = _env_with_shared( tmp_path )
    files = package_shared_library_files( env )
    assert str( so ) in files
    assert str( versioned ) in files


def test_package_shared_library_files_honours_library_prefix( tmp_path: Path ):
    env, _lib_dir, so, _versioned = _env_with_shared(
            tmp_path, stem="filesystem", library_prefix="boost_",
    )
    # Recorded stem without prefix; filename has boost_filesystem.
    files = package_shared_library_files( env )
    assert str( so ) in files


def test_package_shared_library_files_empty_without_contrib():
    env = _FakeEnv( SHLIBPREFIX="lib", SHLIBSUFFIX=".so" )
    assert package_shared_library_files( env ) == []


def test_rpath_linkflags_linux():
    flags = package_runtime_rpath_linkflags( platform_name="Linux" )
    assert "-Wl,-rpath,$$ORIGIN" in flags
    assert "-Wl,-rpath,$$ORIGIN/lib" in flags


def test_rpath_linkflags_darwin():
    flags = package_runtime_rpath_linkflags( platform_name="Darwin" )
    assert "-Wl,-rpath,@loader_path" in flags
    assert "-Wl,-rpath,@loader_path/lib" in flags


def test_rpath_linkflags_windows_empty():
    assert package_runtime_rpath_linkflags( platform_name="Windows" ) == []


def test_ensure_package_runtime_rpath_appends( monkeypatch ):
    monkeypatch.setattr( "cuppa.build_platform.name", lambda: "Linux" )
    env = _FakeEnv()
    ensure_package_runtime_rpath( env )
    assert env["LINKFLAGS"] == [
            "-Wl,-rpath,$$ORIGIN",
            "-Wl,-rpath,$$ORIGIN/lib",
    ]
    ensure_package_runtime_rpath( env )
    assert env["LINKFLAGS"] == [
            "-Wl,-rpath,$$ORIGIN",
            "-Wl,-rpath,$$ORIGIN/lib",
    ]


def test_stage_directory_linux_uses_lib( monkeypatch, tmp_path: Path ):
    monkeypatch.setattr( "cuppa.build_platform.name", lambda: "Linux" )
    prog = _FakeNode( tmp_path / "final" / "server" )
    assert stage_directory_for_program( prog ) == str( tmp_path / "final" / "lib" )


def test_stage_directory_windows_beside_exe( monkeypatch, tmp_path: Path ):
    monkeypatch.setattr( "cuppa.build_platform.name", lambda: "Windows" )
    prog = _FakeNode( tmp_path / "final" / "server.exe" )
    assert stage_directory_for_program( prog ) == str( tmp_path / "final" )


def test_stage_package_libraries_installs_requires_clean( monkeypatch, tmp_path: Path ):
    monkeypatch.setattr( "cuppa.build_platform.name", lambda: "Linux" )
    env, _lib_dir, so, versioned = _env_with_shared( tmp_path )
    prog_env = _FakeEnv()
    prog = _FakeNode( tmp_path / "final" / "server", env=prog_env )

    installed = stage_package_libraries_for_programs( env, prog )
    assert len( installed ) == 2
    dest = str( tmp_path / "final" / "lib" )
    assert ( dest, str( so ) ) in env.installed
    assert ( dest, str( versioned ) ) in env.installed
    assert env.requires
    assert env.cleaned
    assert prog_env["LINKFLAGS"] == [
            "-Wl,-rpath,$$ORIGIN",
            "-Wl,-rpath,$$ORIGIN/lib",
    ]


def test_stage_skips_rpath_when_disabled( monkeypatch, tmp_path: Path ):
    monkeypatch.setattr( "cuppa.build_platform.name", lambda: "Linux" )
    env, _lib_dir, _so, _versioned = _env_with_shared( tmp_path )
    prog_env = _FakeEnv()
    prog = _FakeNode( tmp_path / "final" / "server", env=prog_env )
    stage_package_libraries_for_programs( env, prog, apply_rpath=False )
    assert "LINKFLAGS" not in prog_env


def test_collect_package_libraries( tmp_path: Path ):
    env, _lib_dir, so, versioned = _env_with_shared( tmp_path )
    dest = tmp_path / "artifacts" / "libs"
    installed = collect_package_libraries( env, str( dest ) )
    assert len( installed ) == 2
    assert ( str( dest ), str( so ) ) in env.installed
    assert ( str( dest ), str( versioned ) ) in env.installed


def test_should_stage_package_libraries_flag():
    env = _FakeEnv()
    assert should_stage_package_libraries( env ) is True
    assert should_stage_package_libraries( env, stage_package_libraries=False ) is False
    env["stage_package_libraries"] = False
    assert should_stage_package_libraries( env ) is False
    assert should_stage_package_libraries( env, stage_package_libraries=True ) is True


def test_static_only_contribution_yields_no_files( tmp_path: Path ):
    env = _FakeEnv( SHLIBPREFIX="lib", SHLIBSUFFIX=".so" )
    record_package_link_contribution(
            env,
            "widget",
            static=[ "libwidget.a" ],
            shared=[],
            libpath=[ str( tmp_path ) ],
    )
    assert package_shared_library_files( env ) == []
    assert env.get( _LINK_CONTRIB_KEY )
