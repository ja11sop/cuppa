#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io
import logging
import os
import shutil
import subprocess

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

    with pytest.raises(
            SCons.Errors.StopError,
            match="Pass --clone-publishers to clone it, set --publisher-root",
    ):
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
            { "package": "corosio", "version": "0.2.0", "errors": 0, "clones": 0 }
    ]


def test_build_cascade_graph_tolerant_records_unresolved_tree( tmp_path ):
    class _Publisher:
        _dependencies = [
                { "name": "widget", "package": "widget", "version": "1.2" }
        ]

    env = _PlanEnv( {}, { "storage_root": str( tmp_path / "store" ) } )
    with pytest.raises( SCons.Errors.StopError, match="no publisher tree was found" ):
        cascade.build_cascade_graph( env, _Publisher() )

    nodes, edges = cascade.build_cascade_graph( env, _Publisher(), tolerant=True )
    node = nodes[ ( "widget", "widget", "1.2" ) ]
    assert node["_publisher_dir"] is None
    assert "no publisher tree was found" in node["_resolve_error"]
    assert not edges


def test_an_existing_tree_under_storage_publishers_is_found_without_publisher_root(
        tmp_path, monkeypatch
):
    """``<storage-root>/publishers`` is the default lookup forest, like downloads."""
    planted = tmp_path / "store" / "publishers" / "capy"
    planted.mkdir( parents=True )
    ( planted / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )

    def _must_not_clone( *args, **kwargs ):
        raise AssertionError( "an existing storage publisher must not be re-cloned" )

    monkeypatch.setattr( cascade, "clone_publisher", _must_not_clone )
    env = _PlanEnv( {}, { "storage_root": str( tmp_path / "store" ) } )
    path = cascade.resolve_publisher_dir(
            env,
            {
                    "name": "capy",
                    "package": "capy",
                    "version": "develop",
                    "package_source": "git@git.example:packages/capy",
            },
    )
    assert path == str( planted )


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

    assert "Cascade plan: 2 package dependencies then this package [corosio]==[0.2.0]" in body
    assert "[0 errors][0 warnings][0 notes]" in body
    assert "1 of 2  capy develop (capy)" in body
    assert "publisher [/home/user/coding/packages/capy]" in body
    assert "2 of 2  widget 1.2 (widget)" in body
    assert body.rstrip().endswith( "then this package [corosio]==[0.2.0] from this tree" )


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
    assert "nothing was built, published, uploaded, or cloned" in out.getvalue()

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
    assert "2 nested publishes; resuming this package [corosio]==[0.2.0]" in complete


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

# Clone on demand (slice 2b)


@pytest.mark.parametrize( "source, url, revision", [
        # The user separator in the scp-like form is not a pin.
        ( "git@git.example:packages/capy", "git@git.example:packages/capy", None ),
        (
                "git@git.example:packages/capy@develop",
                "git@git.example:packages/capy",
                "develop",
        ),
        # A slashy revision stays whole; #302 made it safe on disk.
        (
                "git@git.example:packages/capy@feature/cascade",
                "git@git.example:packages/capy",
                "feature/cascade",
        ),
        ( "https://git.example/packages/capy.git@v1.2.0",
                "https://git.example/packages/capy.git", "v1.2.0" ),
        # Credentials in the URL are not a pin either.
        ( "https://user@git.example/packages/capy",
                "https://user@git.example/packages/capy", None ),
        ( "ssh://git@git.example/packages/capy@develop",
                "ssh://git@git.example/packages/capy", "develop" ),
        # A trailing @ pins nothing, so it is left where it is.
        ( "git@git.example:packages/capy@", "git@git.example:packages/capy@", None ),
] )
def test_split_source_pin( source, url, revision ):
    assert cascade.split_source_pin( source ) == ( url, revision )


def test_clone_destination_defaults_to_a_cuppa_owned_tree( tmp_path ):
    """A bare cascade must not populate the operator's working area."""
    env = _PlanEnv( {}, { "storage_root": str( tmp_path / "store" ) } )
    destination = cascade.publisher_clone_destination(
            env, { "name": "capy", "package": "capy" }
    )
    assert destination == str( tmp_path / "store" / "publishers" / "capy" )


def test_clone_destination_follows_an_explicit_publisher_root( tmp_path ):
    """Asking cascade to search a forest is permission to populate it."""
    root = tmp_path / "packages"
    env = _PlanEnv(
            { "publisher-root": str( root ) },
            { "storage_root": str( tmp_path / "store" ) },
    )
    destination = cascade.publisher_clone_destination(
            env, { "name": "capy", "package": "capy" }
    )
    assert destination == str( root / "capy" )


def test_plan_mode_records_the_clone_instead_of_doing_it( tmp_path ):
    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    entry = {
            "name": "capy",
            "package": "capy",
            "version": "develop",
            "package_source": "git@git.example:packages/capy@develop",
    }
    assert cascade.resolve_publisher_dir( env, entry, allow_clone=False ) is None
    assert entry["_clone_url"] == "git@git.example:packages/capy"
    assert entry["_clone_revision"] == "develop"
    assert entry["_clone_dir"] == str( tmp_path / "publishers" / "capy" )


def test_an_existing_tree_wins_over_cloning( tmp_path, monkeypatch ):
    """What the operator planted is used as it stands, and keeps cascade offline."""
    root = tmp_path / "packages"
    planted = root / "capy"
    planted.mkdir( parents=True )
    ( planted / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )

    def _must_not_clone( *args, **kwargs ):
        raise AssertionError( "an existing tree must not be re-cloned" )

    monkeypatch.setattr( cascade, "clone_publisher", _must_not_clone )
    env = _PlanEnv(
            { "clone-publishers": True, "publisher-root": str( root ) },
            { "sconstruct_dir": str( tmp_path ) },
    )
    path = cascade.resolve_publisher_dir(
            env,
            {
                    "name": "capy",
                    "package": "capy",
                    "version": "develop",
                    "package_source": "git@git.example:packages/capy",
            },
    )
    assert path == str( planted )


def test_cloning_refuses_while_offline( tmp_path ):
    env = _PlanEnv(
            { "clone-publishers": True, "offline": True },
            { "storage_root": str( tmp_path ) },
    )
    with pytest.raises( SCons.Errors.StopError, match="--offline" ):
        cascade.resolve_publisher_dir(
                env,
                {
                        "name": "capy",
                        "package": "capy",
                        "version": "develop",
                        "package_source": "git@git.example:packages/capy",
                },
        )


class _FakeGit:
    """Records what cascade asked git to do, without a repository."""

    class Error( Exception ):
        pass

    def __init__( self, origin=None, tracking=(), clone_fails=False ):
        self.origin = origin
        self.tracking = set( tracking )
        self.clone_fails = clone_fails
        self.calls = []
        self.branch = "master"

    def remote_url( self, path, remote='origin' ):
        return self.origin

    def get_branch( self, path ):
        return ( self.branch, None )

    def clone( self, repository, path, branch=None, recurse_submodules=True ):
        self.calls.append( ( "clone", repository, path, branch, recurse_submodules ) )
        os.makedirs( path, exist_ok=True )
        if self.clone_fails:
            raise self.Error( "remote hung up" )
        with open( os.path.join( path, "sconstruct" ), "w", encoding="utf-8" ) as handle:
            handle.write( "import cuppa\n" )

    def remote_tracking_branch_exists( self, path, branch, remote='origin' ):
        return branch in self.tracking

    def checkout_tracking_branch( self, path, branch, remote='origin' ):
        self.calls.append( ( "checkout_tracking_branch", branch ) )

    def checkout_branch( self, path, branch ):
        self.calls.append( ( "checkout_branch", branch ) )

    def update_submodules( self, path ):
        self.calls.append( ( "update_submodules", ) )


def test_cloning_a_branch_pin_lands_on_a_tracking_branch( tmp_path, monkeypatch ):
    git = _FakeGit( tracking=[ "develop" ] )
    monkeypatch.setattr( cascade, "Git", git )
    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    destination = cascade.clone_publisher(
            env,
            { "name": "capy", "package": "capy", "version": "develop" },
            "git@git.example:packages/capy",
            "develop",
            str( tmp_path / "publishers" / "capy" ),
    )
    assert destination == str( tmp_path / "publishers" / "capy" )
    assert ( "checkout_tracking_branch", "develop" ) in git.calls
    assert ( "update_submodules", ) in git.calls
    assert git.calls[0][4] is True    # submodules recursed on clone


def test_cloning_a_tag_pin_is_allowed_and_lands_detached( tmp_path, monkeypatch ):
    """Unlike --clone-develop: publishing version X from tag vX is the normal case."""
    git = _FakeGit( tracking=[] )
    monkeypatch.setattr( cascade, "Git", git )
    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    cascade.clone_publisher(
            env,
            { "name": "capy", "package": "capy", "version": "1.2.0" },
            "git@git.example:packages/capy",
            "v1.2.0",
            str( tmp_path / "publishers" / "capy" ),
    )
    assert ( "checkout_branch", "v1.2.0" ) in git.calls


def test_a_failed_clone_takes_its_directory_with_it( tmp_path, monkeypatch ):
    """A half-clone would be mistaken for a usable tree on the next run."""
    git = _FakeGit( clone_fails=True )
    monkeypatch.setattr( cascade, "Git", git )
    destination = tmp_path / "publishers" / "capy"
    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    with pytest.raises( SCons.Errors.StopError, match="could not clone" ):
        cascade.clone_publisher(
                env,
                { "name": "capy", "package": "capy", "version": "develop" },
                "git@git.example:packages/capy",
                None,
                str( destination ),
        )
    assert not destination.exists()


def test_a_foreign_tree_in_the_destination_is_refused( tmp_path, monkeypatch ):
    destination = tmp_path / "publishers" / "capy"
    destination.mkdir( parents=True )
    ( destination / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    monkeypatch.setattr(
            cascade, "Git", _FakeGit( origin="git@git.example:someone/else" )
    )
    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    with pytest.raises(
            SCons.Errors.StopError, match="is not a clone of"
    ) as failure:
        cascade.clone_publisher(
                env,
                { "name": "capy", "package": "capy", "version": "develop" },
                "git@git.example:packages/capy",
                None,
                str( destination ),
        )
    assert "someone/else" in str( failure.value )
    assert ( destination / "sconstruct" ).exists()    # never clobbered


def test_a_matching_clone_is_reused_as_it_stands( tmp_path, monkeypatch ):
    destination = tmp_path / "publishers" / "capy"
    destination.mkdir( parents=True )
    ( destination / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    git = _FakeGit( origin="git@git.example:packages/capy.git" )
    git.branch = "master"
    monkeypatch.setattr( cascade, "Git", git )
    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    # Pinned to develop but sitting on master: reported, not switched.
    path = cascade.clone_publisher(
            env,
            { "name": "capy", "package": "capy", "version": "develop" },
            "git@git.example:packages/capy",
            "develop",
            str( destination ),
    )
    assert path == str( destination )
    assert not git.calls


def test_a_clone_without_a_publisher_tree_is_refused( tmp_path, monkeypatch ):
    class _EmptyClone( _FakeGit ):
        def clone( self, repository, path, branch=None, recurse_submodules=True ):
            os.makedirs( path, exist_ok=True )

    monkeypatch.setattr( cascade, "Git", _EmptyClone() )
    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    with pytest.raises( SCons.Errors.StopError, match="cannot publish anything" ):
        cascade.clone_publisher(
                env,
                { "name": "capy", "package": "capy", "version": "develop" },
                "git@git.example:packages/capy",
                None,
                str( tmp_path / "publishers" / "capy" ),
        )


def test_two_repositories_cannot_claim_one_clone_destination( tmp_path ):
    class _Publisher:
        _dependencies = [
                {
                        "name": "capy",
                        "package": "capy",
                        "version": "1",
                        "package_source": "git@git.example:one/capy",
                },
                {
                        "name": "capy",
                        "package": "capy-extras",
                        "version": "1",
                        "package_source": "git@git.example:two/capy",
                },
        ]

    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    with pytest.raises(
            SCons.Errors.StopError, match="two repositories claim one directory"
    ):
        cascade.build_cascade_graph( env, _Publisher(), allow_clone=False )


def test_plan_mode_does_not_walk_beneath_a_tree_it_would_clone( tmp_path ):
    """Edges live in the tree's cuppa-publish.json, which does not exist yet."""
    class _Publisher:
        _dependencies = [
                {
                        "name": "capy",
                        "package": "capy",
                        "version": "develop",
                        "package_source": "git@git.example:packages/capy@develop",
                },
        ]

    env = _PlanEnv( { "clone-publishers": True }, { "storage_root": str( tmp_path ) } )
    nodes, edges = cascade.build_cascade_graph(
            env, _Publisher(), tolerant=True, allow_clone=False
    )
    node = nodes[ ( "capy", "capy", "develop" ) ]
    assert node["_publisher_dir"] is None
    assert "_resolve_error" not in node
    assert node["_clone_dir"] == str( tmp_path / "publishers" / "capy" )
    assert not edges


def test_cascade_plan_lines_report_a_planned_clone_as_a_note():
    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": None,
                    "_clone_url": "git@host:capy",
                    "_clone_revision": "develop",
                    "_clone_dir": "/store/publishers/capy",
            },
    }
    lines = cascade.cascade_plan_lines(
            nodes, [ ( "capy", "capy", "develop" ) ], "corosio", "0.2.0"
    )
    body = "\n".join( lines )

    # A tree cascade can fetch is not a failure, unlike one it cannot find.
    assert "[0 errors][0 warnings][1 note]" in body
    assert "note: would clone [git@host:capy] at [develop] into" in body
    assert "/store/publishers/capy" in body
    assert "not known until that tree exists" in body


def test_finish_plan_only_counts_the_trees_it_would_clone():
    cascade.reset_plan_reports()
    cascade.record_plan_report( "corosio", "0.2.0", 0, clone_count=2 )
    out = io.StringIO()
    status = cascade.finish_plan_only( out=out )
    report = out.getvalue()

    assert status == 0
    assert "2 publisher trees to clone first" in report
    assert "nothing was built, published, uploaded, or cloned" in report


def test_finish_plan_only_names_the_clone_flag_when_a_tree_is_missing():
    cascade.reset_plan_reports()
    cascade.record_plan_report( "corosio", "0.2.0", 1 )
    out = io.StringIO()
    status = cascade.finish_plan_only( out=out )

    assert status == 1
    assert "--clone-publishers" in out.getvalue()


def test_tip_forward_args_drops_clone_publishers():
    """Only the tip cascades, so a nested session has nothing to clone."""
    argv = cascade.tip_forward_args( [
            "scons", "--dbg", "--clone-publishers",
            "--publisher-root=/forest", "--publish-package",
    ] )
    assert "--clone-publishers" not in argv
    assert "--dbg" in argv


@pytest.mark.skipif( shutil.which( "git" ) is None, reason="needs a git binary" )
def test_cloning_a_real_repository_honours_the_pin( tmp_path ):
    """End to end against a local repository: clone, then land on the pinned tag."""
    origin = tmp_path / "origin"
    origin.mkdir()

    def git( *args ):
        subprocess.check_call(
                [ "git" ] + list( args ),
                cwd=str( origin ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
        )

    ( origin / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    git( "init", "--quiet" )
    git( "-c", "user.email=t@example", "-c", "user.name=t", "add", "sconstruct" )
    git( "-c", "user.email=t@example", "-c", "user.name=t", "commit", "-qm", "first" )
    git( "tag", "v1" )
    ( origin / "later.txt" ).write_text( "after the tag\n", encoding="utf-8" )
    git( "-c", "user.email=t@example", "-c", "user.name=t", "add", "later.txt" )
    git( "-c", "user.email=t@example", "-c", "user.name=t", "commit", "-qm", "second" )

    env = _PlanEnv(
            { "clone-publishers": True },
            { "storage_root": str( tmp_path / "store" ) },
    )
    path = cascade.resolve_publisher_dir(
            env,
            {
                    "name": "capy",
                    "package": "capy",
                    "version": "1",
                    "package_source": "file://{}@v1".format( origin ),
            },
    )
    assert path == str( tmp_path / "store" / "publishers" / "capy" )
    assert os.path.isfile( os.path.join( path, "sconstruct" ) )
    assert not os.path.exists( os.path.join( path, "later.txt" ) )
# Develop trees as publisher trees (slice B)


def _package_dependency( name, develop, package=None ):
    """A dependency shaped the way cuppa registers a package one."""
    return type( name, (object,), {
            "_name": name,
            "_package_manager": "gitlab",
            "_package": package or name,
            "_develop": develop,
    } )


def _develop_env( tmp_path, name, develop_path, **options ):
    return _PlanEnv(
            options,
            {
                    "sconstruct_dir": str( tmp_path / "project" ),
                    "dependencies": { name: _package_dependency( name, develop_path ) },
            },
    )


def _publisher_tree( path ):
    path.mkdir( parents=True, exist_ok=True )
    ( path / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    return path


def test_a_develop_tree_outranks_package_source_and_the_publisher_root( tmp_path ):
    """The develop path is the operator naming the copy they mean for this run."""
    ( tmp_path / "project" ).mkdir()
    mine = _publisher_tree( tmp_path / "capy" )
    elsewhere = _publisher_tree( tmp_path / "packages" / "capy" )

    env = _develop_env(
            tmp_path, "capy", "../capy",
            develop=True,
            **{ "publisher-root": str( tmp_path / "packages" ) },
    )
    entry = {
            "name": "capy",
            "package": "capy",
            "version": "develop",
            "package_source": str( elsewhere ),
    }
    path = cascade.resolve_publisher_dir( env, entry )

    assert os.path.samefile( path, mine )
    assert entry["_from_develop"] is True


def test_a_develop_tree_is_not_used_without_the_develop_flag( tmp_path ):
    ( tmp_path / "project" ).mkdir()
    _publisher_tree( tmp_path / "capy" )
    authored = _publisher_tree( tmp_path / "authored" / "capy" )

    env = _develop_env( tmp_path, "capy", "../capy" )
    entry = {
            "name": "capy",
            "package": "capy",
            "version": "develop",
            "package_source": str( authored ),
    }
    path = cascade.resolve_publisher_dir( env, entry )

    assert path == str( authored )
    assert entry["_develop_unused"] is True
    assert "_from_develop" not in entry


def test_a_develop_path_holding_a_built_package_names_both_meanings( tmp_path ):
    """A package develop path has meant a built prefix; say which tree is wanted."""
    ( tmp_path / "project" ).mkdir()
    prefix = tmp_path / "capy"
    ( prefix / "include" ).mkdir( parents=True )
    ( prefix / "lib" ).mkdir()

    env = _develop_env( tmp_path, "capy", "../capy", develop=True )
    with pytest.raises( SCons.Errors.StopError ) as failure:
        cascade.resolve_publisher_dir(
                env, { "name": "capy", "package": "capy", "version": "develop" }
        )
    message = str( failure.value )

    assert "holds a built package" in message
    assert "publisher project" in message
    assert "drop --develop" in message


def test_a_missing_develop_tree_is_refused_rather_than_cloned( tmp_path ):
    """--clone-develop fills develop paths; cascade does not clone into them."""
    ( tmp_path / "project" ).mkdir()
    env = _develop_env(
            tmp_path, "capy", "../capy",
            develop=True,
            **{ "clone-publishers": True },
    )
    entry = {
            "name": "capy",
            "package": "capy",
            "version": "develop",
            "package_source": "git@git.example:packages/capy",
    }
    with pytest.raises( SCons.Errors.StopError, match="is not a directory" ):
        cascade.resolve_publisher_dir( env, entry )

    assert not ( tmp_path / "publishers" ).exists()


@pytest.mark.parametrize( "copy_fields, expected", [
        (
                { "modified": True, "branch": "develop", "upstream": "origin/develop" },
                [ "uncommitted changes" ],
        ),
        ( { "ahead": 1, "upstream": "origin/develop" }, [ "1 commit not pushed" ] ),
        ( { "ahead": 3, "upstream": "origin/develop" }, [ "3 commits not pushed" ] ),
        (
                { "branch": "develop" },
                [ "no upstream, so its commits are only on this machine" ],
        ),
        # A detached head is a named commit, which is what a tag pin produces.
        ( { "detached": True }, [] ),
        ( { "upstream": "origin/develop", "ahead": 0, "behind": 4 }, [] ),
] )
def test_develop_publish_objections( copy_fields, expected ):
    from cuppa.develop import Copy

    copy = Copy(
            name="capy", path="/tree", exists=True, is_working_copy=True, scm="git",
            **copy_fields
    )
    assert cascade.develop_publish_objections( copy ) == expected


def test_an_unreadable_working_copy_raises_no_objection():
    """Being unable to inspect a tree is not evidence of local work."""
    from cuppa.develop import Copy

    copy = Copy( name="capy", path="/tree", exists=True )
    assert cascade.develop_publish_objections( copy ) == []


def _develop_nodes( path, objections_from ):
    key = ( "capy", "capy", "develop" )
    nodes = {
            key: {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": str( path ),
                    "_develop_dir": str( path ),
                    "_from_develop": True,
            },
    }
    return nodes, [ key ], objections_from


def _stub_inspect( monkeypatch, **copy_fields ):
    from cuppa.develop import Copy

    def _inspect( name, path ):
        return Copy(
                name=name, path=path, exists=True, is_working_copy=True, scm="git",
                **copy_fields
        )

    monkeypatch.setattr( "cuppa.develop.inspect", _inspect )


def test_publishing_from_a_modified_develop_tree_is_refused( tmp_path, monkeypatch ):
    """The registry version could not be rebuilt from history, so stop before any upload."""
    _stub_inspect( monkeypatch, modified=True, branch="develop", upstream="origin/develop" )
    nodes, order, _ = _develop_nodes( tmp_path, None )
    env = _PlanEnv( { "develop": True } )

    with pytest.raises( SCons.Errors.StopError ) as failure:
        cascade.judge_publisher_trees( env, nodes, order )
    message = str( failure.value )

    assert "uncommitted changes" in message
    assert "--publish-modified-develop" in message
    assert "Commit and push" in message


def test_the_override_allows_the_publish_and_says_so( tmp_path, monkeypatch, caplog ):
    _stub_inspect( monkeypatch, modified=True, branch="develop", upstream="origin/develop" )
    nodes, order, _ = _develop_nodes( tmp_path, None )
    env = _PlanEnv( { "develop": True, "publish-modified-develop": True } )

    with caplog.at_level( logging.WARNING ):
        cascade.judge_publisher_trees( env, nodes, order )

    assert "allowed by --publish-modified-develop" in caplog.text


def test_a_clean_develop_tree_publishes_without_comment( tmp_path, monkeypatch ):
    _stub_inspect(
            monkeypatch, branch="develop", upstream="origin/develop", ahead=0, behind=0
    )
    nodes, order, _ = _develop_nodes( tmp_path, None )
    cascade.judge_publisher_trees( _PlanEnv( { "develop": True } ), nodes, order )


def test_the_plan_reports_what_a_real_run_would_refuse( tmp_path, monkeypatch ):
    _stub_inspect( monkeypatch, modified=True, branch="develop", upstream="origin/develop" )
    nodes, order, _ = _develop_nodes( tmp_path, None )
    env = _PlanEnv( { "develop": True } )

    cascade._record_publisher_objections( env, nodes, order )
    body = "\n".join( cascade.cascade_plan_lines( nodes, order, "corosio", "0.2.0" ) )

    assert "(develop)" in body
    assert "[1 error]" in body
    assert "error: publishing from this tree has uncommitted changes" in body
    assert "refused; commit and push" in body


def test_the_plan_reports_an_allowed_modified_tree_as_a_note( tmp_path, monkeypatch ):
    _stub_inspect( monkeypatch, modified=True, branch="develop", upstream="origin/develop" )
    nodes, order, _ = _develop_nodes( tmp_path, None )
    env = _PlanEnv( { "develop": True, "publish-modified-develop": True } )

    cascade._record_publisher_objections( env, nodes, order )
    body = "\n".join( cascade.cascade_plan_lines( nodes, order, "corosio", "0.2.0" ) )

    assert "[0 errors][0 warnings][1 note]" in body
    assert "(allowed by" in body
    assert "--publish-modified-develop" in body


def test_the_plan_says_when_a_develop_tree_was_configured_but_not_used():
    key = ( "capy", "capy", "develop" )
    nodes = {
            key: {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": "/authored/capy",
                    "_develop_dir": "/home/user/coding/capy",
                    "_develop_unused": True,
            },
    }
    body = "\n".join( cascade.cascade_plan_lines( nodes, [ key ], "corosio", "0.2.0" ) )

    assert "[0 errors][1 warning][0 notes]" in body
    assert "warning: a develop tree is configured" in body
    assert "was that intentional" in body
    assert "publisher [/home/user/coding/capy]" not in body or "publisher [/authored/capy]" in body


def test_unused_develop_with_no_other_tree_is_a_warning_and_note_not_a_false_error():
    """Soak: develop path exists; forgetting --develop is not 'no local working tree'."""
    key = ( "capy", "capy", "develop" )
    nodes = {
            key: {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": None,
                    "_develop_dir": "/home/user/coding/capy",
                    "_develop_unused": True,
                    "_would_happen": (
                            "without --develop, cascade would look under "
                            "[~/.cuppa/publishers] (nothing found) and then need "
                            "--clone-publishers; pass --develop to publish from "
                            "[~/coding/capy]"
                    ),
            },
    }
    body = "\n".join( cascade.cascade_plan_lines( nodes, [ key ], "corosio", "0.2.0" ) )

    assert "[0 errors][1 warning][1 note]" in body
    assert "warning: a develop tree is configured" in body
    assert "note: without --develop" in body
    assert "error:" not in body
    assert "no local working tree" not in body


def test_a_usable_unused_develop_tree_is_not_a_plan_resolve_error( tmp_path ):
    ( tmp_path / "project" ).mkdir()
    _publisher_tree( tmp_path / "capy" )
    env = _develop_env( tmp_path, "capy", "../capy" )
    env["storage_root"] = str( tmp_path / "store" )
    entry = {
            "name": "capy",
            "package": "capy",
            "version": "develop",
            "package_source": "git@git.example:packages/capy",
    }

    nodes, _ = cascade.build_cascade_graph(
            env,
            type( "P", (), {
                    "_dependencies": [ entry ],
                    "_package": "corosio",
                    "_version": "0.2.0",
            } )(),
            tolerant=True,
            allow_clone=False,
    )
    node = nodes[ ( "capy", "capy", "develop" ) ]

    assert node.get( "_develop_unused" ) is True
    assert node.get( "_would_happen" )
    assert "_resolve_error" not in node
    assert node.get( "_publisher_dir" ) is None


def test_tip_forward_args_drops_tip_dependency_options():
    """Nested publishers never registered the tip's --<dep>-… flags."""
    class _Capy:
        _name = "capy"
        _package_manager = "gitlab"

    env = _PlanEnv( data={
            "dependencies": { "capy": type( "F", (), { "__self__": _Capy } )() },
    } )
    argv = cascade.tip_forward_args( [
            "scons", "-D", "--rel", "--develop",
            "--capy-gitlab-develop=../capy",
            "--capy-gitlab-package-source=git@gitlab.example:packages/capy@develop",
            "--publish-package",
            "--build-and-publish-dependencies",
    ], env=env )

    assert "--develop" in argv
    assert "--rel" in argv
    assert "--capy-gitlab-develop=../capy" not in argv
    assert "--capy-gitlab-package-source=git@gitlab.example:packages/capy@develop" not in argv
    assert all( not a.startswith( "--capy-gitlab-" ) for a in argv )


def test_tip_forward_args_drops_publish_modified_develop():
    argv = cascade.tip_forward_args( [
            "scons", "--dbg", "--publish-modified-develop", "--publish-package",
    ] )
    assert "--publish-modified-develop" not in argv
    assert "--dbg" in argv


def test_a_staged_publish_manifest_does_not_make_a_prefix_a_publisher_tree( tmp_path ):
    """A publisher build stages cuppa-publish.json beside include/ and lib/."""
    prefix = tmp_path / "capy"
    ( prefix / "include" ).mkdir( parents=True )
    ( prefix / "cuppa-publish.json" ).write_text( "{}", encoding="utf-8" )

    assert not cascade.develop_names_a_publisher_tree( str( prefix ) )
    assert "holds a built package" in cascade.develop_tree_refusal( str( prefix ) )


def test_a_develop_path_is_only_a_publisher_source_under_cascade( tmp_path ):
    tree = _publisher_tree( tmp_path / "capy" )

    assert not cascade.develop_is_publisher_source( _PlanEnv( {} ), str( tree ) )
    assert cascade.develop_is_publisher_source(
            _PlanEnv( { "build-and-publish-dependencies": True } ), str( tree )
    )
    assert cascade.develop_is_publisher_source(
            _PlanEnv( { "cascade-plan": True } ), str( tree )
    )


def _rooted_nodes( path ):
    """A publisher tree cascade found by root lookup rather than a develop path."""
    key = ( "capy", "capy", "develop" )
    nodes = {
            key: {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": str( path ),
            },
    }
    return nodes, [ key ]


def test_local_work_in_a_rooted_tree_warns_rather_than_stopping(
        tmp_path, monkeypatch, caplog
):
    """Refusing here would stop the workflow cascade shipped with; the hazard still shows."""
    _stub_inspect( monkeypatch, modified=True, branch="develop", upstream="origin/develop" )
    nodes, order = _rooted_nodes( tmp_path )

    with caplog.at_level( logging.WARNING ):
        cascade.judge_publisher_trees( _PlanEnv( {} ), nodes, order )

    assert "uncommitted changes" in caplog.text
    assert "--publish-modified-develop" not in caplog.text


def test_the_plan_grades_a_rooted_tree_as_a_warning( tmp_path, monkeypatch ):
    _stub_inspect( monkeypatch, ahead=2, branch="develop", upstream="origin/develop" )
    nodes, order = _rooted_nodes( tmp_path )

    cascade._record_publisher_objections( _PlanEnv( {} ), nodes, order )
    body = "\n".join( cascade.cascade_plan_lines( nodes, order, "corosio", "0.2.0" ) )

    assert "[0 errors][1 warning][0 notes]" in body
    assert "warning: publishing from this tree has 2 commits not pushed" in body
    assert "published anyway; cascade only" in body


def test_an_unreadable_rooted_tree_says_nothing( tmp_path, monkeypatch, caplog ):
    """A rooted tree that is not a working copy is ordinary, not worth a line."""
    from cuppa.develop import Copy

    monkeypatch.setattr(
            "cuppa.develop.inspect",
            lambda name, path: Copy( name=name, path=path, exists=True ),
    )
    nodes, order = _rooted_nodes( tmp_path )

    with caplog.at_level( logging.WARNING ):
        cascade.judge_publisher_trees( _PlanEnv( {} ), nodes, order )

    assert caplog.text == ""


def test_a_package_source_declared_on_the_dependency_resolves_a_publisher_tree( tmp_path ):
    """Declared for --clone-develop; cascade should not need it said twice."""
    ( tmp_path / "project" ).mkdir()
    tree = _publisher_tree( tmp_path / "packages" / "capy" )
    dependency = _package_dependency( "capy", None )
    dependency._package_source = "git@gitlab.example:packages/capy"

    env = _PlanEnv(
            { "publisher-root": str( tmp_path / "packages" ) },
            {
                    "sconstruct_dir": str( tmp_path / "project" ),
                    "dependencies": { "capy": dependency },
            },
    )
    entry = { "name": "capy", "package": "capy", "version": "develop" }

    assert cascade.declared_package_source( env, entry ) == (
            "git@gitlab.example:packages/capy"
    )
    assert cascade.resolve_publisher_dir( env, entry ) == str( tree )
