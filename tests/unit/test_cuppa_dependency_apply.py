#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for transitive cuppa-dependency.json apply helpers."""

import json
from pathlib import Path

import pytest
import SCons.Errors

from cuppa.package_managers.cuppa_dependency_apply import (
    apply_transitive_build_with,
    apply_transitive_use_libs,
    list_static_lib_stems,
)
from cuppa.package_managers.cuppa_dependency_manifest import MANIFEST_FILENAME


pytestmark = pytest.mark.unit


def _write_manifest( package_dir: Path, dependencies ):
    package_dir.mkdir( parents=True, exist_ok=True )
    ( package_dir / MANIFEST_FILENAME ).write_text(
            json.dumps( {
                    "cuppa_dependency_format": 1,
                    "dependencies": dependencies,
            } ),
            encoding="utf-8",
    )


class _FakeEnv( dict ):
    def __init__( self ):
        super().__init__()
        self["dependencies"] = {}
        self.build_with_calls = []
        self._instances = {}

    def BuildWith( self, name ):
        self.build_with_calls.append( name )
        factory = self["dependencies"].get( name )
        if factory and name not in self._instances:
            self._instances[name] = factory( self )
        if name not in self._instances:
            self._instances[name] = _FakeDependency( name )
        instance = self._instances[name]
        instance( self, None, "dbg" )
        return instance


class _FakeDependency:
    def __init__( self, name ):
        self._name = name
        self.use_libs_calls = []

    def __call__( self, env, toolchain, variant ):
        return self

    def use_libs( self, libs, depends_on=[] ):
        self.use_libs_calls.append( list( libs ) )


def test_list_static_lib_stems( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    ( lib_dir / "libalpha.a" ).write_text( "x", encoding="utf-8" )
    ( lib_dir / "libbeta.a" ).write_text( "x", encoding="utf-8" )
    ( lib_dir / "readme.txt" ).write_text( "x", encoding="utf-8" )
    assert list_static_lib_stems( str( lib_dir ), "lib", ".a" ) == ["alpha", "beta"]


def test_list_static_lib_stems_strips_library_prefix( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    ( lib_dir / "libcp_fmt.a" ).write_text( "x", encoding="utf-8" )
    assert list_static_lib_stems(
            str( lib_dir ), "lib", ".a", library_prefix="cp_"
    ) == ["fmt"]


def test_apply_transitive_build_with_registers_and_builds( tmp_path: Path, monkeypatch ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "2.0.0",
                    "registry": "same",
            }
    ] )

    created = {}

    def _fake_package_dependency( name, **kwargs ):
        class Factory:
            _name = name
            _version = kwargs.get( "version" )
            _package = kwargs.get( "package" )
            _registry = kwargs.get( "registry" )

            @classmethod
            def create( cls, env ):
                created[name] = kwargs
                return _FakeDependency( name )

        return Factory

    monkeypatch.setattr(
            "cuppa.build_with_package.package_dependency",
            _fake_package_dependency,
    )

    env = _FakeEnv()
    apply_transitive_build_with(
            env,
            str( package_dir ),
            "a",
            "https://gitlab.example/api/v4/projects/1",
    )
    assert "b" in env["dependencies"]
    assert created["b"]["version"] == "2.0.0"
    assert env.build_with_calls == ["b"]


def test_apply_transitive_build_with_detects_cycle( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            { "name": "a", "package": "a", "version": "1.0.0", "registry": "same" }
    ] )
    env = _FakeEnv()
    env["dependencies"]["a"] = lambda e: _FakeDependency( "a" )
    with pytest.raises( SCons.Errors.StopError, match="Cycle" ):
        apply_transitive_build_with(
                env,
                str( package_dir ),
                "a",
                "https://gitlab.example/api/v4/projects/1",
        )


def test_apply_transitive_use_libs_once( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "2.0.0",
                    "registry": "same",
                    "use_libs": ["core"],
            }
    ] )
    env = _FakeEnv()

    class Factory:
        _name = "b"
        _version = "2.0.0"

        @classmethod
        def create( cls, env ):
            return _FakeDependency( "b" )

    env["dependencies"]["b"] = Factory.create

    apply_transitive_use_libs(
            env,
            str( package_dir ),
            "a",
            "https://gitlab.example/api/v4/projects/1",
    )
    apply_transitive_use_libs(
            env,
            str( package_dir ),
            "a",
            "https://gitlab.example/api/v4/projects/1",
    )
    assert env._instances["b"].use_libs_calls == [["core"]]


def test_version_conflict_raises( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "3.0.0",
                    "registry": "same",
            }
    ] )
    env = _FakeEnv()

    class Factory:
        _name = "b"
        _version = "2.0.0"

        @classmethod
        def create( cls, env ):
            return _FakeDependency( "b" )

    env["dependencies"]["b"] = Factory.create

    with pytest.raises( SCons.Errors.StopError, match="version" ):
        apply_transitive_build_with(
                env,
                str( package_dir ),
                "a",
                "https://gitlab.example/api/v4/projects/1",
        )
