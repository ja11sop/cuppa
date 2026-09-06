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
from cuppa.package_managers.gitlab import GitlabPackageDependency


pytestmark = pytest.mark.unit

_REGISTRY = "https://gitlab.example/api/v4/projects/1"


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
    """Mimic ``env.BuildWith`` and optional transitive initialise / use_libs."""

    def __init__( self, package_dirs=None, registry=_REGISTRY ):
        super().__init__()
        self["dependencies"] = {}
        self.build_with_calls = []
        self._instances = {}
        self._package_dirs = package_dirs or {}
        self._registry = registry

    def BuildWith( self, name ):
        self.build_with_calls.append( name )
        factory = self["dependencies"].get( name )
        if factory and name not in self._instances:
            created = factory( self )
            if isinstance( created, list ):
                self._instances[name] = created
            else:
                self._instances[name] = created
        if name not in self._instances:
            self._instances[name] = _FakeDependency(
                    name,
                    package_dir=self._package_dirs.get( name ),
                    registry=self._registry,
            )
        instance = self._instances[name]
        if isinstance( instance, list ):
            return instance
        if callable( instance ):
            instance( self, None, "dbg" )
        return instance


class _FakeDependency:
    def __init__( self, name, package_dir=None, registry=_REGISTRY, support_use_libs=True ):
        self._name = name
        self._package_dir = package_dir
        self._registry = registry
        self._support_use_libs = support_use_libs
        self._env = None
        self.use_libs_calls = []

    def __call__( self, env, toolchain, variant ):
        self._env = env
        # Mimic GitlabPackageDependency.initialise_build_variant transitive apply
        if self._package_dir is not None:
            apply_transitive_build_with(
                    env, str( self._package_dir ), self._name, self._registry
            )
        return self

    def use_libs( self, libs, depends_on=[] ):
        if not self._support_use_libs:
            raise AttributeError( "no use_libs" )
        self.use_libs_calls.append( list( libs ) )
        if self._package_dir is not None and self._env is not None:
            apply_transitive_use_libs(
                    self._env, str( self._package_dir ), self._name, self._registry
            )


def _install_fake_package_dependency( monkeypatch, created=None, package_dirs=None ):
    created = created if created is not None else {}
    package_dirs = package_dirs or {}

    def _fake_package_dependency( name, **kwargs ):
        class Factory:
            _name = name
            _version = kwargs.get( "version" )
            _package = kwargs.get( "package" )
            _registry = kwargs.get( "registry" )

            @classmethod
            def create( cls, env ):
                created[name] = kwargs
                return _FakeDependency(
                        name,
                        package_dir=package_dirs.get( name ),
                        registry=kwargs.get( "registry" ) or _REGISTRY,
                )

        return Factory

    monkeypatch.setattr(
            "cuppa.build_with_package.package_dependency",
            _fake_package_dependency,
    )
    return created


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


def test_list_static_lib_stems_missing_dir_returns_empty( tmp_path: Path ):
    assert list_static_lib_stems( str( tmp_path / "missing" ), "lib", ".a" ) == []
    assert list_static_lib_stems( None, "lib", ".a" ) == []


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

    created = _install_fake_package_dependency( monkeypatch )
    env = _FakeEnv()
    apply_transitive_build_with( env, str( package_dir ), "a", _REGISTRY )
    assert "b" in env["dependencies"]
    assert created["b"]["version"] == "2.0.0"
    assert created["b"]["registry"] == _REGISTRY
    assert env.build_with_calls == ["b"]


def test_apply_chain_a_requires_b_requires_c( tmp_path: Path, monkeypatch ):
    """A's BuildWith pulls B, and B's initialise pulls C (depth-two chain)."""
    dir_a = tmp_path / "a" / "1.0.0"
    dir_b = tmp_path / "b" / "2.0.0"
    dir_c = tmp_path / "c" / "3.0.0"
    dir_c.mkdir( parents=True )
    _write_manifest( dir_a, [
            { "name": "b", "package": "b", "version": "2.0.0", "registry": "same" },
    ] )
    _write_manifest( dir_b, [
            { "name": "c", "package": "c", "version": "3.0.0", "registry": "same" },
    ] )

    package_dirs = { "b": dir_b, "c": dir_c }
    created = _install_fake_package_dependency(
            monkeypatch, package_dirs=package_dirs
    )
    env = _FakeEnv( package_dirs=package_dirs )
    apply_transitive_build_with( env, str( dir_a ), "a", _REGISTRY )

    assert env.build_with_calls == ["b", "c"]
    assert created["b"]["version"] == "2.0.0"
    assert created["c"]["version"] == "3.0.0"
    assert set( env["dependencies"] ) >= { "b", "c" }


def test_apply_chain_use_libs_a_to_b_to_c( tmp_path: Path, monkeypatch ):
    """Linking A applies B's edge libs, and B's use_libs applies C's edge libs."""
    dir_a = tmp_path / "a" / "1.0.0"
    dir_b = tmp_path / "b" / "2.0.0"
    dir_c = tmp_path / "c" / "3.0.0"
    dir_c.mkdir( parents=True )
    _write_manifest( dir_a, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "2.0.0",
                    "use_libs": ["b_core"],
            },
    ] )
    _write_manifest( dir_b, [
            {
                    "name": "c",
                    "package": "c",
                    "version": "3.0.0",
                    "use_libs": ["c_util"],
            },
    ] )

    package_dirs = { "b": dir_b, "c": dir_c }
    _install_fake_package_dependency( monkeypatch, package_dirs=package_dirs )
    env = _FakeEnv( package_dirs=package_dirs )

    apply_transitive_use_libs( env, str( dir_a ), "a", _REGISTRY )

    assert env._instances["b"].use_libs_calls == [["b_core"]]
    assert env._instances["c"].use_libs_calls == [["c_util"]]


def test_apply_transitive_build_with_noop_without_manifest( tmp_path: Path ):
    env = _FakeEnv()
    apply_transitive_build_with( env, str( tmp_path ), "a", _REGISTRY )
    assert env.build_with_calls == []


def test_apply_transitive_build_with_detects_cycle( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            { "name": "a", "package": "a", "version": "1.0.0", "registry": "same" }
    ] )
    env = _FakeEnv()
    env["dependencies"]["a"] = lambda e: _FakeDependency( "a" )
    with pytest.raises( SCons.Errors.StopError, match="Cycle" ):
        apply_transitive_build_with( env, str( package_dir ), "a", _REGISTRY )


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

    apply_transitive_use_libs( env, str( package_dir ), "a", _REGISTRY )
    apply_transitive_use_libs( env, str( package_dir ), "a", _REGISTRY )
    assert env._instances["b"].use_libs_calls == [["core"]]


def test_apply_transitive_use_libs_skips_headers_only_edge( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "2.0.0",
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
    apply_transitive_use_libs( env, str( package_dir ), "a", _REGISTRY )
    assert env.build_with_calls == []
    assert "b" not in env._instances


def test_apply_transitive_use_libs_rejects_missing_use_libs( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "2.0.0",
                    "use_libs": ["core"],
            }
    ] )
    env = _FakeEnv()

    class NoLibs:
        pass

    class Factory:
        _name = "b"
        _version = "2.0.0"

        @classmethod
        def create( cls, env ):
            return NoLibs()

    env["dependencies"]["b"] = Factory.create
    with pytest.raises( SCons.Errors.StopError, match="does not support use_libs" ):
        apply_transitive_use_libs( env, str( package_dir ), "a", _REGISTRY )


def test_apply_transitive_use_libs_unwraps_build_with_list( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "2.0.0",
                    "use_libs": ["core"],
            }
    ] )
    env = _FakeEnv()
    dep = _FakeDependency( "b" )

    class Factory:
        _name = "b"
        _version = "2.0.0"

        @classmethod
        def create( cls, env ):
            return [dep]

    env["dependencies"]["b"] = Factory.create
    apply_transitive_use_libs( env, str( package_dir ), "a", _REGISTRY )
    assert dep.use_libs_calls == [["core"]]


def test_apply_transitive_use_libs_empty_list_raises( tmp_path: Path ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "2.0.0",
                    "use_libs": ["core"],
            }
    ] )
    env = _FakeEnv()

    class Factory:
        _name = "b"
        _version = "2.0.0"

        @classmethod
        def create( cls, env ):
            return []

    env["dependencies"]["b"] = Factory.create
    with pytest.raises( SCons.Errors.StopError, match="could not be created" ):
        apply_transitive_use_libs( env, str( package_dir ), "a", _REGISTRY )


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
        apply_transitive_build_with( env, str( package_dir ), "a", _REGISTRY )


def test_synthesize_requires_registry( tmp_path: Path, monkeypatch ):
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            { "name": "b", "package": "b", "version": "1.0.0", "registry": "same" },
    ] )
    _install_fake_package_dependency( monkeypatch )
    env = _FakeEnv()
    with pytest.raises( SCons.Errors.StopError, match="parent registry is unknown" ):
        apply_transitive_build_with( env, str( package_dir ), "a", None )


def test_explicit_registry_url_is_passed_through( tmp_path: Path, monkeypatch ):
    other = "https://gitlab.example/api/v4/projects/99"
    package_dir = tmp_path / "a" / "1.0.0"
    _write_manifest( package_dir, [
            {
                    "name": "b",
                    "package": "b",
                    "version": "1.0.0",
                    "registry": other,
            },
    ] )
    created = _install_fake_package_dependency( monkeypatch )
    env = _FakeEnv()
    apply_transitive_build_with( env, str( package_dir ), "a", _REGISTRY )
    assert created["b"]["registry"] == other


def test_use_all_libs_selects_stems_and_delegates( tmp_path: Path ):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    ( lib_dir / "libwidget.a" ).write_text( "x", encoding="utf-8" )
    ( lib_dir / "libextra.a" ).write_text( "x", encoding="utf-8" )

    package = GitlabPackageDependency.__new__( GitlabPackageDependency )
    package._lib_dir = str( lib_dir )
    package._library_prefix = ""
    package._package_id = "widget/1.0.0/rel"
    package._package_dir = str( tmp_path )
    package._registry = _REGISTRY
    package._pkg_config_dir = None
    package._include_dir = str( tmp_path / "include" )
    ( tmp_path / "include" ).mkdir()

    selected = []

    def _capture_use_libs( libs, depends_on=[], dependency_name=None ):
        selected.extend( list( libs ) )

    package.use_libs = _capture_use_libs
    package._env = { "LIBPREFIX": "lib", "LIBSUFFIX": ".a" }

    package.use_all_libs()
    assert selected == ["extra", "widget"]
