#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io
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

    with pytest.raises( SCons.Errors.StopError, match="Set --publisher-root" ):
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


class _PlanEnv( dict ):
    """Tip env with the cascade flags an operator passes, and nothing else set."""

    def __init__( self, options=None, data=None ):
        dict.__init__( self, data or {} )
        self._options = options or {}

    def get_option( self, name, default=None ):
        return self._options.get( name, default )


def test_cascade_plan_requires_the_cascade_flag():
    class _Publisher:
        _dependencies = []
        _package = "widget"
        _version = "1"

    env = _PlanEnv( { "cascade-plan": True } )
    with pytest.raises(
            SCons.Errors.StopError,
            match="--cascade-plan requires --build-and-publish-dependencies",
    ):
        cascade.maybe_run_cascade( env, _Publisher() )


def test_cascade_plan_does_not_require_publish_package( tmp_path, monkeypatch ):
    """Plan mode publishes nothing, so demanding --publish-package is ceremony."""
    leaf = tmp_path / "capy"
    leaf.mkdir()
    ( leaf / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    write_publish_manifest( str( leaf ), "capy", "develop", dependencies=[] )

    class _Publisher:
        _dependencies = [
                {
                        "name": "capy",
                        "package": "capy",
                        "version": "develop",
                        "package_source": str( leaf ),
                }
        ]
        _package = "corosio"
        _version = "0.2.0"

    def _must_not_run( *args, **kwargs ):
        raise AssertionError( "plan mode must not run a nested publish" )

    monkeypatch.setattr( cascade, "run_nested_publish", _must_not_run )
    monkeypatch.setattr( cascade, "refresh_package_consume_cache", _must_not_run )
    cascade.reset_plan_reports()

    env = _PlanEnv( {
            "cascade-plan": True,
            "build-and-publish-dependencies": True,
    } )
    cascade.maybe_run_cascade( env, _Publisher() )

    assert cascade.plan_reports() == [
            { "package": "corosio", "version": "0.2.0", "errors": 0 }
    ]


def test_build_cascade_graph_tolerant_records_unresolved_tree():
    class _Publisher:
        _dependencies = [
                { "name": "widget", "package": "widget", "version": "1.2" }
        ]

    env = _PlanEnv()
    with pytest.raises( SCons.Errors.StopError, match="publisher-root" ):
        cascade.build_cascade_graph( env, _Publisher() )

    nodes, edges = cascade.build_cascade_graph( env, _Publisher(), tolerant=True )
    node = nodes[ ( "widget", "widget", "1.2" ) ]
    assert node["_publisher_dir"] is None
    assert "publisher-root" in node["_resolve_error"]
    assert not edges


def test_cascade_plan_lines_number_the_order_and_name_publisher_trees():
    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": "/home/user/coding/packages/capy",
            },
            ( "widget", "widget", "1.2" ): {
                    "name": "widget", "package": "widget", "version": "1.2",
                    "_publisher_dir": "/home/user/coding/packages/widget",
            },
    }
    order = [ ( "capy", "capy", "develop" ), ( "widget", "widget", "1.2" ) ]
    lines = cascade.cascade_plan_lines( nodes, order, "corosio", "0.2.0" )
    body = "\n".join( lines )

    assert "Cascade plan: 2 package dependencies then tip [corosio]==[0.2.0]" in body
    assert "[0 errors][0 warnings][0 notes]" in body
    assert "1 of 2  capy develop (capy)" in body
    assert "publisher [/home/user/coding/packages/capy]" in body
    assert "2 of 2  widget 1.2 (widget)" in body
    assert body.rstrip().endswith( "then tip [corosio]==[0.2.0] from this tree" )


def test_cascade_plan_lines_count_unresolved_trees_as_errors():
    nodes = {
            ( "widget", "widget", "1.2" ): {
                    "name": "widget", "package": "widget", "version": "1.2",
                    "_publisher_dir": None,
                    "_resolve_error": "no package_source and --publisher-root is not set",
            },
    }
    lines = cascade.cascade_plan_lines(
            nodes, [ ( "widget", "widget", "1.2" ) ], "corosio", "0.2.0"
    )
    body = "\n".join( lines )

    assert "[1 error][0 warnings][0 notes]" in body
    assert "error: no package_source and --publisher-root is not set" in body


def test_finish_plan_only_reports_no_publisher_as_a_failure():
    cascade.reset_plan_reports()
    out = io.StringIO()
    assert cascade.finish_plan_only( out=out ) == 1
    assert "no GitLab package publisher was constructed" in out.getvalue()


def test_finish_plan_only_names_the_missing_cascade_flag():
    """A project with no publisher never reaches the refusal in maybe_run_cascade."""
    cascade.reset_plan_reports()
    out = io.StringIO()
    env = _PlanEnv( { "cascade-plan": True } )
    assert cascade.finish_plan_only( env, out=out ) == 1
    assert "requires --build-and-publish-dependencies" in out.getvalue()


def test_finish_plan_only_exit_status_follows_resolution():
    cascade.reset_plan_reports()
    cascade.record_plan_report( "corosio", "0.2.0", 0 )
    out = io.StringIO()
    assert cascade.finish_plan_only( out=out ) == 0
    assert "nothing was built, published, or uploaded" in out.getvalue()

    cascade.record_plan_report( "widget", "1.2", 2 )
    out = io.StringIO()
    assert cascade.finish_plan_only( out=out ) == 1
    assert "2 dependencies without a publisher tree" in out.getvalue()


def test_session_banners_carry_ordinal_and_total():
    begin = "\n".join( cascade.session_begin_lines(
            1, 2, "capy develop (capy)", "/home/user/coding/packages/capy",
            "python -m cuppa -D --rel --publish-package",
    ) )
    assert "cascade session 1 of 2: capy develop (capy)" in begin
    assert "publisher [/home/user/coding/packages/capy]" in begin
    assert "command [python -m cuppa -D --rel --publish-package]" in begin

    end = "\n".join( cascade.session_end_lines( 1, 2, "capy develop (capy)", 1500000000 ) )
    assert "cascade session 1 of 2 finished: capy develop (capy) in 00:00:01" in end

    complete = "\n".join( cascade.sessions_complete_lines( 2, "corosio", "0.2.0" ) )
    assert "2 nested publishes; resuming tip [corosio]==[0.2.0]" in complete


def test_tip_forward_args_drops_cascade_plan():
    tip = [
            "scons", "-D", "--rel",
            "--build-and-publish-dependencies",
            "--cascade-plan",
    ]
    assert cascade.tip_forward_args( tip ) == [
            "-D",
            "--rel",
            "--publish-package",
    ]


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

