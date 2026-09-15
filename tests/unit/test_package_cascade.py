#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest
import SCons.Errors

from cuppa.package_managers import package_cascade as cascade
from cuppa.package_managers.cuppa_publish_manifest import write_publish_manifest


pytestmark = pytest.mark.unit


def test_topological_publish_order_leaves_first():
    nodes = {
            ( "a", "a", "1" ): {},
            ( "b", "b", "1" ): {},
            ( "c", "c", "1" ): {},
    }
    # c depends on b; b depends on a → a, b, c
    edges = {
            ( "c", "c", "1" ): { ( "b", "b", "1" ) },
            ( "b", "b", "1" ): { ( "a", "a", "1" ) },
    }
    assert cascade.topological_publish_order( nodes, edges ) == [
            ( "a", "a", "1" ),
            ( "b", "b", "1" ),
            ( "c", "c", "1" ),
    ]


def test_topological_publish_order_detects_cycle():
    nodes = {
            ( "a", "a", "1" ): {},
            ( "b", "b", "1" ): {},
    }
    edges = {
            ( "a", "a", "1" ): { ( "b", "b", "1" ) },
            ( "b", "b", "1" ): { ( "a", "a", "1" ) },
    }
    with pytest.raises( SCons.Errors.StopError, match="cycle" ):
        cascade.topological_publish_order( nodes, edges )


def test_resolve_publisher_dir_from_filesystem_source( tmp_path ):
    pub = tmp_path / "fmt"
    pub.mkdir()
    ( pub / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    env = {}
    path = cascade.resolve_publisher_dir(
            env,
            {
                    "name": "fmt",
                    "package": "fmt",
                    "version": "1",
                    "package_source": str( pub ),
            },
    )
    assert path == str( pub )


def test_resolve_publisher_dir_under_publisher_root( tmp_path ):
    root = tmp_path / "packages"
    nested = root / "google" / "protobuf"
    nested.mkdir( parents=True )
    ( nested / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )

    class _Env:
        def get_option( self, name, default=None ):
            if name == "publisher-root":
                return str( root )
            return default

        def get( self, name, default=None ):
            return default

    path = cascade.resolve_publisher_dir(
            _Env(),
            { "name": "protobuf", "package": "protobuf", "version": "1" },
    )
    assert path == str( nested )


def test_publisher_root_relative_anchors_to_sconstruct_dir( tmp_path ):
    """``--publisher-root=../../`` must not depend on process cwd."""
    packages = tmp_path / "packages"
    tip = packages / "cppalliance" / "corosio"
    capy = packages / "cppalliance" / "capy"
    tip.mkdir( parents=True )
    capy.mkdir( parents=True )
    ( capy / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )

    class _Env:
        def __init__( self ):
            self._data = { "sconstruct_dir": str( tip ) }

        def get_option( self, name, default=None ):
            if name == "publisher-root":
                return "../../"
            return default

        def get( self, name, default=None ):
            return self._data.get( name, default )

    # Deliberately not under tip — cwd must not matter.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    old = os.getcwd()
    try:
        os.chdir( elsewhere )
        root = cascade.publisher_root_option( _Env() )
        assert root == str( packages.resolve() )
        path = cascade.resolve_publisher_dir(
                _Env(),
                {
                        "name": "capy",
                        "package": "capy",
                        "version": "develop",
                        "package_source": "git@git.example/packages/cppalliance/capy",
                },
        )
        assert path == str( capy.resolve() )
    finally:
        os.chdir( old )


def test_resolve_url_without_publisher_root_mentions_flag():
    class _Env:
        def get_option( self, name, default=None ):
            return default

        def get( self, name, default=None ):
            return default

    with pytest.raises( SCons.Errors.StopError, match="requires --publisher-root" ):
        cascade.resolve_publisher_dir(
                _Env(),
                {
                        "name": "capy",
                        "package": "capy",
                        "version": "1",
                        "package_source": "git@git.example/org/capy",
                },
        )


def test_build_cascade_graph_reads_nested_publish_file( tmp_path ):
    leaf = tmp_path / "fmt"
    leaf.mkdir()
    ( leaf / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    write_publish_manifest( str( leaf ), "fmt", "12.2.0", dependencies=[] )

    mid = tmp_path / "date"
    mid.mkdir()
    ( mid / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    write_publish_manifest(
            str( mid ),
            "date",
            "3.0.5",
            dependencies=[
                    {
                            "name": "fmt",
                            "package": "fmt",
                            "version": "12.2.0",
                            "package_source": str( leaf ),
                    }
            ],
    )

    class _Publisher:
        _dependencies = [
                {
                        "name": "date",
                        "package": "date",
                        "version": "3.0.5",
                        "package_source": str( mid ),
                }
        ]

    class _Env( dict ):
        def get_option( self, name, default=None ):
            return default

    nodes, edges = cascade.build_cascade_graph( _Env(), _Publisher() )
    assert ( "date", "date", "3.0.5" ) in nodes
    assert ( "fmt", "fmt", "12.2.0" ) in nodes
    assert ( "fmt", "fmt", "12.2.0" ) in edges[ ( "date", "date", "3.0.5" ) ]
    order = cascade.topological_publish_order( nodes, edges )
    assert order[0] == ( "fmt", "fmt", "12.2.0" )
    assert order[1] == ( "date", "date", "3.0.5" )


def test_maybe_run_cascade_requires_publish_package():
    class _Env:
        def get_option( self, name, default=None ):
            return name == "build-and-publish-dependencies"

    class _Publisher:
        _dependencies = []
        _package = "widget"
        _version = "1"

    with pytest.raises( SCons.Errors.StopError, match="publish-package" ):
        cascade.maybe_run_cascade( _Env(), _Publisher() )


def test_tip_forward_args_keeps_variant_and_toolchains_drops_cascade():
    tip = [
            "scons",
            "-D",
            "--rel",
            "--toolchains=gcc15",
            "--publish-package",
            "--build-and-publish-dependencies",
            "--publisher-root=../../",
            "--cuppa-mode",
    ]
    forwarded = cascade.tip_forward_args( tip )
    assert forwarded == [
            "-D",
            "--rel",
            "--toolchains=gcc15",
            "--publish-package",
    ]
    nested = cascade.argv_for_nested_publish( tip )
    assert nested[:3] == [ nested[0], "-m", "cuppa" ]
    assert nested[3:] == forwarded


def test_tip_forward_args_drops_publisher_root_separate_value():
    tip = [
            "scons",
            "-D",
            "--dbg",
            "--publish-package",
            "--publisher-root",
            "/pubs",
            "--build-and-publish-dependencies",
    ]
    assert cascade.tip_forward_args( tip ) == [
            "-D",
            "--dbg",
            "--publish-package",
    ]


def test_tip_forward_args_adds_publish_package_and_descend_when_missing():
    tip = [ "scons", "--rel", "--toolchains=gcc" ]
    assert cascade.tip_forward_args( tip ) == [
            "-D",
            "--rel",
            "--toolchains=gcc",
            "--publish-package",
    ]


def test_refresh_package_consume_cache_refetches_via_tip_factory( tmp_path, monkeypatch ):
    downloads = tmp_path / "downloads" / "packages" / "capy" / "develop"
    extract = tmp_path / "deps" / "gcc15_rel_x86_64_cxx2c" / "capy" / "develop"
    downloads.mkdir( parents=True )
    extract.mkdir( parents=True )
    ( extract / "include" ).mkdir()
    ( extract / "lib" ).mkdir()

    class _Package:
        def __init__( self ):
            self._package = "capy"
            self._version = "develop"

        def package_dir( self ):
            return str( extract )

    class _Built:
        def package( self ):
            return _Package()

    class _Factory:
        _cached_packages = { ( "gitlab", ( "reg", "capy", "develop" ) ): _Package() }
        _package = "capy"
        _name = "capy"

        @classmethod
        def create( cls, env ):
            return _Built()

    class _Env( dict ):
        def get_option( self, name, default=None ):
            if name == "toolchains":
                return ["gcc15"]
            return default

    # Real cuppa stores ``cls.create``, not the class (build_with_package.add_to_env).
    env = _Env(
            {
                    "downloads_root": str( tmp_path / "downloads" ),
                    "dependencies_root": str( tmp_path / "deps" ),
                    "dependencies": { "capy": _Factory.create },
            }
    )
    monkeypatch.setattr(
            cascade,
            "invalidate_package_consume_cache",
            lambda env, package, version: [str( extract )],
    )

    removed = cascade.refresh_package_consume_cache(
            env,
            { "name": "capy", "package": "capy", "version": "develop" },
    )
    assert removed == [str( extract )]
    assert _Factory._cached_packages == {}


def test_call_tip_dependency_factory_accepts_create_method():
    class _Factory:
        @classmethod
        def create( cls, env ):
            return "built"

    assert cascade._call_tip_dependency_factory( _Factory.create, {} ) == "built"
    assert cascade._call_tip_dependency_factory( _Factory, {} ) == "built"


def test_evict_cached_package_matches_pin():
    class _Inst:
        def __init__( self, package, version ):
            self._package = package
            self._version = version

    class _Factory:
        _cached_packages = {
                "keep": _Inst( "other", "1" ),
                "drop": _Inst( "capy", "develop" ),
        }

        @classmethod
        def create( cls, env ):
            return None

    assert cascade._evict_cached_package( _Factory, "capy", "develop" ) == 1
    assert "drop" not in _Factory._cached_packages
    assert "keep" in _Factory._cached_packages

    _Factory._cached_packages["drop2"] = _Inst( "capy", "develop" )
    assert cascade._evict_cached_package( _Factory.create, "capy", "develop" ) == 1
    assert "drop2" not in _Factory._cached_packages

