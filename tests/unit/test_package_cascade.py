#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import io
import logging
import os
import re
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


def test_resolve_url_without_publisher_root_mentions_flag( tmp_path ):
    """Empty storage forest + URL source: stop and name the clone / root flags.

    Pin ``storage_root`` so a real ``~/.cuppa/publishers`` tree from soak does
    not satisfy the lookup and hide the refusal.
    """
    class _Env:
        def get_option( self, name, default=None ):
            return default

        def get( self, name, default=None ):
            if name == "storage_root":
                return str( tmp_path / "store" )
            return default

    with pytest.raises(
            SCons.Errors.StopError,
            match=r"Pass --clone-publishers to clone it, or set --publisher-root",
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


def test_maybe_run_cascade_refuses_scons_dry_run( capsys ):
    """Soak: -n forwards into nested configure, which cannot create .sconf_temp."""
    import re

    from cuppa.colourise import as_emphasised, as_info, colouriser

    class _Env:
        def get_option( self, name, default=None ):
            return name in (
                    "build-and-publish-dependencies",
                    "publish-package",
                    "no_exec",
            )

    class _Publisher:
        _dependencies = []
        _package = "widget"
        _version = "1"

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--build-and-publish-dependencies and -n/--no-exec\)",
        ):
            cascade.maybe_run_cascade( _Env(), _Publisher() )
    finally:
        colouriser.use_colour = was

    out = capsys.readouterr().out
    visible = re.sub( r"\x1b\[[0-9;]*m", "", out )
    assert "Options Error" in visible
    assert "--build-and-publish-dependencies cannot run under -n/--no-exec" in visible
    assert ".sconf_temp" in visible
    assert "--cascade-plan" in visible
    assert "--collect-cascade" in visible
    # Prose may wrap between "without" and "-n".
    assert "re-run without" in visible and "-n to publish" in visible
    # Trailing blank line before the critical StopError log.
    assert visible.rstrip( "\n" ).endswith( "to publish" ) or visible.endswith( "\n\n" )
    assert out.endswith( "\n\n" ) or "\n\n" in out[ out.rfind( "publish" ) : ]
    # Remedy flags are emphasised info, not error.
    assert as_emphasised( as_info( "--cascade-plan" ) ) in out
    assert as_emphasised( as_info( "--collect-cascade" ) ) in out


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
            {
                    "package": "corosio",
                    "version": "0.2.0",
                    "errors": 0,
                    "clones": 0,
                    "needs_clone_opt_in": 0,
                    "unused_develop": 0,
                    "mode": "cascade-plan",
                    "trees_collected": 0,
                    "trees_updated": 0,
            }
    ]


def test_collect_cascade_requires_the_cascade_flag():
    env = _PlanEnv( { "collect-cascade": True } )
    with pytest.raises(
            SCons.Errors.StopError,
            match="--collect-cascade requires --build-and-publish-dependencies",
    ):
        cascade.maybe_run_cascade( env, type( "P", (), {
                "_dependencies": [], "_package": "w", "_version": "1",
        } )() )


def test_collect_cascade_and_cascade_plan_cannot_combine():
    env = _PlanEnv( {
            "collect-cascade": True,
            "cascade-plan": True,
            "build-and-publish-dependencies": True,
    } )
    with pytest.raises( SCons.Errors.StopError, match="cannot be combined" ):
        cascade.maybe_run_cascade( env, type( "P", (), {
                "_dependencies": [], "_package": "w", "_version": "1",
        } )() )


def test_collect_cascade_clones_then_stops_without_nested_publish(
        tmp_path, monkeypatch
):
    """Collect materialises trees; it must not start nested cuppa sessions."""
    origin = tmp_path / "origin"
    origin.mkdir()
    ( origin / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )

    cloned = []

    def _fake_clone( url, destination, recurse_submodules=True ):
        cloned.append( ( url, destination ) )
        os.makedirs( destination )
        with open( os.path.join( destination, "sconstruct" ), "w", encoding="utf-8" ) as handle:
            handle.write( "import cuppa\n" )

    monkeypatch.setattr( cascade.Git, "clone", _fake_clone )
    monkeypatch.setattr(
            cascade, "run_nested_publish",
            lambda *a, **k: (_ for _ in ()).throw(
                    AssertionError( "collect must not nested-publish" )
            ),
    )
    cascade.reset_plan_reports()

    class _Publisher:
        _dependencies = [
                {
                        "name": "capy",
                        "package": "capy",
                        "version": "develop",
                        "package_source": "git@git.example:packages/capy",
                }
        ]
        _package = "corosio"
        _version = "0.2.0"

    env = _PlanEnv(
            {
                    "collect-cascade": True,
                    "build-and-publish-dependencies": True,
                    "clone-publishers": True,
            },
            { "storage_root": str( tmp_path / "store" ) },
    )
    cascade.maybe_run_cascade( env, _Publisher() )

    assert len( cloned ) == 1
    assert cloned[0][1] == str( tmp_path / "store" / "publishers" / "capy" )
    reports = cascade.plan_reports()
    assert len( reports ) == 1
    assert reports[0]["mode"] == "collect-cascade"
    assert reports[0]["clones"] == 1
    assert reports[0]["trees_collected"] == 1
    assert reports[0]["errors"] == 0

    out = io.StringIO()
    status = cascade.finish_cascade_stop( env, out=out )
    assert status == 0
    text = out.getvalue()
    assert "--collect-cascade:" in text
    assert "1 publisher tree collected" in text
    assert "newly cloned" in text
    assert "nothing was built, published, or uploaded" in text
    assert "nothing was collected" not in text


def test_collect_cascade_footer_counts_zero_trees_when_clone_opt_in_is_missing(
        tmp_path, monkeypatch
):
    monkeypatch.setattr(
            cascade, "run_nested_publish",
            lambda *a, **k: (_ for _ in ()).throw( AssertionError( "no nested" ) ),
    )
    cascade.reset_plan_reports()
    env = _PlanEnv(
            {
                    "collect-cascade": True,
                    "build-and-publish-dependencies": True,
            },
            { "storage_root": str( tmp_path / "store" ) },
    )
    publisher = type( "P", (), {
            "_dependencies": [ {
                    "name": "capy", "package": "capy", "version": "develop",
                    "package_source": "git@git.example:packages/capy",
            } ],
            "_package": "corosio",
            "_version": "0.2.0",
    } )()
    cascade.maybe_run_cascade( env, publisher )

    assert cascade.plan_reports()[0]["trees_collected"] == 0
    nodes, _ = cascade.build_cascade_graph(
            env, publisher, tolerant=True, allow_clone=False
    )
    body = "\n".join( cascade.cascade_plan_lines(
            nodes, [ ( "capy", "capy", "develop" ) ], "corosio", "0.2.0",
            mode="collect-cascade",
            argv=[ "cuppa", "-D", "--collect-cascade", "--cuppa-mode" ],
    ) )
    assert "collecting packages for" in body
    assert "make this collect executable" in body
    assert "--cuppa-mode" not in body
    assert "and pass --clone-publishers" in body
    # Wrap may split the sentence across lines.
    assert "uses that tree instead of cloning" in re.sub( r"\s+", " ", body )

    out = io.StringIO()
    assert cascade.finish_cascade_stop( env, out=out ) == 0
    text = out.getvalue()
    assert "0 publisher trees collected" in text
    assert "nothing was collected, built, published, or uploaded" in text


def test_collect_cascade_reuses_an_existing_publisher_tree( tmp_path, monkeypatch ):
    forest = tmp_path / "store" / "publishers" / "capy"
    forest.mkdir( parents=True )
    ( forest / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    write_publish_manifest( str( forest ), "capy", "develop", dependencies=[] )

    def _must_not_clone( *args, **kwargs ):
        raise AssertionError( "existing forest tree must not be re-cloned" )

    monkeypatch.setattr( cascade.Git, "clone", _must_not_clone )
    monkeypatch.setattr(
            cascade, "run_nested_publish",
            lambda *a, **k: (_ for _ in ()).throw(
                    AssertionError( "collect must not nested-publish" )
            ),
    )
    cascade.reset_plan_reports()

    env = _PlanEnv(
            {
                    "collect-cascade": True,
                    "build-and-publish-dependencies": True,
                    "clone-publishers": True,
            },
            { "storage_root": str( tmp_path / "store" ) },
    )
    cascade.maybe_run_cascade( env, type( "P", (), {
            "_dependencies": [ {
                    "name": "capy", "package": "capy", "version": "develop",
                    "package_source": "git@git.example:packages/capy",
            } ],
            "_package": "corosio",
            "_version": "0.2.0",
    } )() )

    assert cascade.plan_reports()[0]["clones"] == 0
    assert cascade.plan_reports()[0]["trees_collected"] == 1
    out = io.StringIO()
    assert cascade.finish_cascade_stop( env, out=out ) == 0
    text = out.getvalue()
    assert "1 publisher tree collected" in text
    assert "newly cloned" not in text
    assert "nothing was built, published, or uploaded" in text
    assert "nothing was collected" not in text


def test_tip_forward_args_drops_collect_cascade():
    argv = cascade.tip_forward_args( [
            "scons", "--dbg", "--collect-cascade", "--publish-package",
    ] )
    assert "--collect-cascade" not in argv
    assert "--dbg" in argv


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
    import re

    from cuppa.colourise import as_subdued, colouriser
    from cuppa.utility import storage as storage_util

    def plain( text ):
        return re.sub( r"\x1b\[[0-9;]*m", "", text )

    was = colouriser.use_colour
    colouriser.enable()
    try:
        nodes = {
                ( "capy", "capy", "develop" ): {
                        "name": "capy", "package": "capy", "version": "develop",
                        "package_source": "git@git.example:packages/capy",
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
        visible = plain( body )

        assert "Printing Cascade plan for building and publishing package corosio [==0.2.0] given the command:" in visible
        assert "Cascade plan: corosio [==0.2.0] (this package) with" in visible
        assert "2 package dependencies" in visible
        assert "[0 errors][0 warnings][0 notes]" in visible
        assert "1 of 2  capy [==develop]" in visible
        assert as_subdued( "git@git.example:packages/capy" ) in body
        assert "using publisher at [/home/user/coding/packages/capy]" in visible
        tee, elbow, pipe, _gap = storage_util.glyphs()
        # Nested elbow hangs under the package label pad (under = pipe + spaces).
        under = pipe + " " * ( len( "2 of 2" ) + 2 )
        stub = pipe.rstrip()
        assert any(
                line.startswith( as_subdued( under + elbow ) )
                and "using publisher at" in plain( line )
                for line in lines
        )
        # Breathing stub under each package node before nested leaves.
        assert as_subdued( under + stub ) in lines
        # Breathing stub between package siblings.
        assert lines.count( as_subdued( stub ) ) >= 2
        assert "2 of 2  widget [==1.2]" in visible
        assert visible.rstrip().endswith( "then corosio [==0.2.0] from this tree" )
        # Outer tree glyphs match judgement trees (subdued stems).
        assert as_subdued( stub ) in lines
        assert any( line.startswith( as_subdued( tee ) ) for line in lines )
        assert any( line.startswith( as_subdued( elbow ) ) for line in lines )
    finally:
        colouriser.use_colour = was


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
    assert "1 error" in body
    assert "no package_source and --publisher-root is not set" in body
    assert "error:" not in body or "1 error" in body


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
    import re

    from cuppa.colourise import as_info_label, colouriser

    def plain( text ):
        return re.sub( r"\x1b\[[0-9;]*m", "", text )

    was = colouriser.use_colour
    colouriser.enable()
    try:
        cascade.reset_plan_reports()
        cascade.record_plan_report( "corosio", "0.2.0", 0 )
        out = io.StringIO()
        assert cascade.finish_plan_only( out=out ) == 0
        text = out.getvalue()
        visible = plain( text )
        assert visible.strip().startswith( "--cascade-plan:" )
        assert "nothing was built, published, uploaded, or cloned" in visible
        # Summary through the semicolon is the info-label chip; detail stays plain.
        assert as_info_label( "--cascade-plan: 1 package planned" ) in text
        assert "; nothing was built" in visible

        cascade.record_plan_report( "widget", "1.2", 2 )
        out = io.StringIO()
        assert cascade.finish_plan_only( out=out ) == 1
        assert "2 dependencies without a publisher tree" in plain( out.getvalue() )
    finally:
        colouriser.use_colour = was


def test_session_banners_carry_ordinal_and_total():
    from cuppa.colourise import as_info_label, colouriser

    def plain( text ):
        return re.sub( r"\x1b\[[0-9;]*m", "", text )

    was = colouriser.use_colour
    colouriser.use_colour = True
    try:
        begin = "\n".join( cascade.session_begin_lines(
                1, 2, "capy develop (capy)", "/home/user/coding/packages/capy",
                "python -m cuppa -D --rel --publish-package",
        ) )
        assert as_info_label( "cascade session 1 of 2" ) in begin
        assert "capy develop (capy)" in plain( begin )
        assert "publisher [/home/user/coding/packages/capy]" in plain( begin )
        assert "command [python -m cuppa -D --rel --publish-package]" in plain( begin )

        end_lines = cascade.session_end_lines(
                1, 2, "capy develop (capy)", 1500000000
        )
        assert as_info_label( "cascade session 1 of 2 finished" ) in end_lines[0]
        assert "capy develop (capy) in 00:00:01" in plain( end_lines[0] )
        assert set( plain( end_lines[1] ) ) == { "-" }
        assert end_lines[2] == ""

        stage_begin = "\n".join( cascade.session_begin_lines(
                1, 1, "capy/develop/rel", "/home/user/coding/packages/capy",
                "python -m cuppa -D --rel --stage-package",
                kind="develop stage",
        ) )
        assert as_info_label( "develop stage 1 of 1" ) in stage_begin

        stage_end_lines = cascade.session_end_lines(
                1, 1, "capy/develop/rel", 1500000000, kind="develop stage"
        )
        assert as_info_label( "develop stage 1 of 1 finished" ) in stage_end_lines[0]
        assert set( plain( stage_end_lines[1] ) ) == { "-" }
        assert stage_end_lines[2] == ""

        complete = "\n".join( cascade.sessions_complete_lines( 2, "corosio", "0.2.0" ) )
        assert as_info_label( "cascade sessions complete" ) in complete
        assert "2 nested publishes; resuming this package corosio [==0.2.0]" in plain( complete )

        clean_complete = "\n".join( cascade.sessions_complete_lines(
                1, "corosio", "0.2.0", clean=True
        ) )
        assert "1 nested clean; resuming clean of this package corosio [==0.2.0]" in plain(
                clean_complete
        )
    finally:
        colouriser.use_colour = was


def test_cascade_plan_lines_clean_mode_retargets_intro_and_notes_cmake():
    def plain( text ):
        return re.sub( r"\x1b\[[0-9;]*m", "", text )

    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy",
                    "package": "capy",
                    "version": "develop",
                    "_publisher_dir": "/home/user/.cuppa/publishers/capy",
            },
    }
    order = [ ( "capy", "capy", "develop" ) ]
    visible = plain( "\n".join( cascade.cascade_plan_lines(
            nodes, order, "corosio", "develop", clean=True,
            argv=[ "cuppa", "-D", "--rel", "-c", "--publish-package",
                   "--build-and-publish-dependencies" ],
    ) ) )
    assert "Printing Cascade plan for cleaning package corosio [==develop]" in visible
    assert "then clean corosio [==develop] from this tree" in visible
    assert "CMakeConfigure/CMakeBuild" in visible
    assert "incremental Ninja" in visible
    assert "building and publishing" not in visible


def test_maybe_run_cascade_clean_skips_consume_refresh( monkeypatch ):
    """Soak: -c must not invalidate+re-fetch after nested cleans."""
    refreshed = []

    class _Env( dict ):
        def get_option( self, name, default=None ):
            return name in (
                    "build-and-publish-dependencies",
                    "publish-package",
                    "clean",
            ) or default

    class _Publisher:
        _dependencies = [
                { "name": "capy", "package": "capy", "version": "develop" },
        ]
        _package = "corosio"
        _version = "develop"

    monkeypatch.setattr( cascade, "build_cascade_graph", lambda *a, **k: (
            {
                    ( "capy", "capy", "develop" ): {
                            "name": "capy",
                            "package": "capy",
                            "version": "develop",
                            "_publisher_dir": "/pubs/capy",
                    },
            },
            {},
    ) )
    monkeypatch.setattr(
            cascade, "topological_publish_order",
            lambda nodes, edges: list( nodes.keys() ),
    )
    monkeypatch.setattr( cascade, "judge_publisher_trees", lambda *a, **k: None )
    monkeypatch.setattr( cascade, "write_lines", lambda *a, **k: None )
    monkeypatch.setattr( cascade, "run_nested_publish", lambda *a, **k: None )
    monkeypatch.setattr(
            cascade,
            "refresh_package_consume_cache",
            lambda *a, **k: refreshed.append( True ),
    )
    monkeypatch.setattr( cascade, "_clean_enabled", lambda env: True )

    cascade.maybe_run_cascade( _Env(), _Publisher() )
    assert refreshed == []


def test_cascade_stop_before_build_update_without_publish():
    class _Env:
        def __init__( self, flags ):
            self._flags = flags

        def get_option( self, name, default=None ):
            return name in self._flags or default

    assert cascade.cascade_stop_before_build( _Env( {
            "build-and-publish-dependencies", "update-publishers",
    } ) )
    assert not cascade.cascade_stop_before_build( _Env( {
            "build-and-publish-dependencies", "update-publishers", "publish-package",
    } ) )


def test_maybe_run_cascade_refuses_plan_with_update():
    class _Env:
        def get_option( self, name, default=None ):
            return name in (
                    "build-and-publish-dependencies",
                    "cascade-plan",
                    "update-publishers",
            ) or default

    class _Publisher:
        _dependencies = []
        _package = "widget"
        _version = "1"

    with pytest.raises( SCons.Errors.StopError, match="cannot be combined" ):
        cascade.maybe_run_cascade( _Env(), _Publisher() )


def test_update_publisher_trees_skips_develop_and_ffs_behind( monkeypatch ):
    from cuppa.develop import Action, Copy
    import cuppa.develop as develop_mod

    lines = []

    def _emit( text="" ):
        lines.append( text )

    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": "/pubs/capy",
            },
            ( "leaf", "leaf", "1" ): {
                    "name": "leaf", "package": "leaf", "version": "1",
                    "_publisher_dir": "/dev/leaf",
                    "_from_develop": True,
            },
    }
    order = list( nodes.keys() )

    monkeypatch.setattr(
            develop_mod, "inspect",
            lambda name, path: Copy(
                    name=name, path=path, exists=True, is_working_copy=True,
                    scm="git", branch="master", upstream="origin/master",
                    behind=2 if name == "capy" else 0, ahead=0,
                    modified=False, detached=False,
            ),
    )
    monkeypatch.setattr(
            develop_mod, "update_action",
            lambda copy: (
                    Action( True, "2 commits behind [origin/master]" )
                    if copy.behind else
                    Action( False, "already up to date" )
            ),
    )
    fetches = []
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fetch",
            lambda path, progress=None, **kwargs: fetches.append( ( path, progress ) ),
    )
    ff = []
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fast_forward",
            lambda path: ff.append( path ),
    )

    class _Env( dict ):
        def get_option( self, name, default=None ):
            return default

    updated = cascade.update_publisher_trees( _Env(), nodes, order, out=_emit )
    assert updated == 1
    assert fetches == [ ( "/pubs/capy", False ) ]
    assert ff == [ "/pubs/capy" ]
    joined = "\n".join( lines )
    assert "ACTION" in joined
    assert "updated" in joined
    assert "capy" in joined
    assert "left alone" in joined
    assert "develop tree (use --update-develop)" in joined
    assert "Updated [capy]" not in joined


def test_update_publisher_trees_dry_run_fetches_then_would_update( monkeypatch ):
    from cuppa.develop import Action, Copy
    import cuppa.develop as develop_mod

    lines = []
    monkeypatch.setattr(
            develop_mod, "inspect",
            lambda name, path: Copy(
                    name=name, path=path, exists=True, is_working_copy=True,
                    scm="git", branch="master", upstream="origin/master",
                    behind=3, ahead=0, modified=False, detached=False,
            ),
    )
    monkeypatch.setattr(
            develop_mod, "update_action",
            lambda copy: Action( True, "3 commits behind [origin/master]" ),
    )
    fetches = []
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fetch",
            lambda path, progress=None, **kwargs: fetches.append( ( path, progress ) ),
    )
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fast_forward",
            lambda path: (_ for _ in ()).throw( AssertionError( "no FF on dry-run" ) ),
    )

    class _Env( dict ):
        def get_option( self, name, default=None ):
            return True if name == "no_exec" else default

    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": "/home/user/.cuppa/publishers/capy",
            },
    }
    updated = cascade.update_publisher_trees(
            _Env(), nodes, list( nodes.keys() ), out=lines.append,
    )
    assert updated == 0
    assert fetches == [ ( "/home/user/.cuppa/publishers/capy", False ) ]
    joined = "\n".join( lines )
    assert "checking remotes" in joined
    assert "judged as of your last fetch" not in joined
    assert "would update" in joined
    assert "3 behind" in joined
    assert "publishers/capy" in joined
    assert "Would fetch" not in joined
    assert "Would update [capy]" not in joined


def test_update_publisher_trees_dry_run_already_current( monkeypatch ):
    from cuppa.develop import Action, Copy
    import cuppa.develop as develop_mod

    lines = []
    monkeypatch.setattr(
            develop_mod, "inspect",
            lambda name, path: Copy(
                    name=name, path=path, exists=True, is_working_copy=True,
                    scm="git", branch="master", upstream="origin/master",
                    behind=0, ahead=0, modified=False, detached=False,
            ),
    )
    monkeypatch.setattr(
            develop_mod, "update_action",
            lambda copy: Action( False, "already up to date" ),
    )
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fetch",
            lambda path, progress=None, **kwargs: None,
    )

    class _Env( dict ):
        def get_option( self, name, default=None ):
            return True if name == "no_exec" else default

    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": "/pubs/capy",
            },
    }
    cascade.update_publisher_trees( _Env(), nodes, list( nodes.keys() ), out=lines.append )
    joined = "\n".join( lines )
    assert "no change" in joined
    assert "current" in joined
    assert "Nothing to be done for [capy]" not in joined
    assert "Leaving [capy] alone" not in joined


def test_update_publisher_trees_offline_dry_run_skips_network( monkeypatch ):
    from cuppa.develop import Action, Copy
    import cuppa.develop as develop_mod

    lines = []
    monkeypatch.setattr(
            develop_mod, "inspect",
            lambda name, path: Copy(
                    name=name, path=path, exists=True, is_working_copy=True,
                    scm="git", branch="master", upstream="origin/master",
                    behind=1, ahead=0, modified=False, detached=False,
            ),
    )
    monkeypatch.setattr(
            develop_mod, "update_action",
            lambda copy: Action( True, "1 commit behind [origin/master]" ),
    )
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fetch",
            lambda path, progress=None, **kwargs: (_ for _ in ()).throw(
                    AssertionError( "no fetch offline" )
            ),
    )

    class _Env( dict ):
        def get_option( self, name, default=None ):
            return True if name == "no_exec" else default

    env = _Env()
    env["offline"] = True
    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": "/pubs/capy",
            },
    }
    cascade.update_publisher_trees( env, nodes, list( nodes.keys() ), out=lines.append )
    joined = "\n".join( lines )
    assert "judged from your last update" in joined
    assert "would update" in joined
    assert "1 behind" in joined


def test_update_publisher_trees_leaves_alone_when_untracked_would_overwrite( monkeypatch ):
    from cuppa.develop import Action, Copy
    import cuppa.develop as develop_mod

    lines = []
    monkeypatch.setattr(
            develop_mod, "inspect",
            lambda name, path: Copy(
                    name=name, path=path, exists=True, is_working_copy=True,
                    scm="git", branch="master", upstream="origin/master",
                    behind=2, ahead=0, modified=False, detached=False,
            ),
    )
    monkeypatch.setattr(
            develop_mod, "update_action",
            lambda copy: Action(
                    False, "untracked [cuppa-publish.json] would be overwritten"
            ),
    )
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fetch",
            lambda path, progress=None, **kwargs: None,
    )
    monkeypatch.setattr(
            "cuppa.scms.git.Git.fast_forward",
            lambda path: (_ for _ in ()).throw( AssertionError( "no FF" ) ),
    )

    class _Env( dict ):
        def get_option( self, name, default=None ):
            return default

    nodes = {
            ( "capy", "capy", "develop" ): {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": "/pubs/capy",
            },
    }
    updated = cascade.update_publisher_trees(
            _Env(), nodes, list( nodes.keys() ), out=lines.append,
    )
    assert updated == 0
    joined = "\n".join( lines )
    assert "left alone" in joined
    assert "untracked [cuppa-publish.json] would be overwritten" in joined
    assert "failed" not in joined


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
    # Two note lines hang under one "2 notes" group (clone + "not known until").
    assert "[0 errors][0 warnings][2 notes]" in body
    assert "2 notes" in body
    assert "would clone [git@host:capy] at [develop] into" in body
    assert "/store/publishers/capy" in body
    assert "not known until that tree exists" in body


def test_finish_plan_only_counts_the_trees_it_would_clone():
    cascade.reset_plan_reports()
    cascade.record_plan_report( "corosio", "0.2.0", 0, clone_count=2 )
    out = io.StringIO()
    status = cascade.finish_plan_only( out=out )
    report = re.sub( r"\x1b\[[0-9;]*m", "", out.getvalue() )

    assert status == 0
    assert "2 publisher trees to clone first" in report
    assert "pass --clone-publishers along with --publish-package to execute" in report
    assert "nothing was built, published, uploaded, or cloned" in report


def test_finish_plan_only_names_the_clone_flag_when_a_tree_is_missing():
    cascade.reset_plan_reports()
    cascade.record_plan_report( "corosio", "0.2.0", 1 )
    out = io.StringIO()
    status = cascade.finish_plan_only( out=out )
    report = re.sub( r"\x1b\[[0-9;]*m", "", out.getvalue() )

    assert status == 1
    assert "--clone-publishers" in report
    assert "Then re-run with --publish-package to execute" in report

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
    assert "1 error" in body
    assert "publishing from this tree has uncommitted changes" in body
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
                    "_lookup_root": "/home/user/.cuppa/publishers",
            },
    }
    body = "\n".join( cascade.cascade_plan_lines(
            nodes, [ key ], "corosio", "0.2.0",
            argv=[ "cuppa", "-D", "--cascade-plan", "--build-and-publish-dependencies" ],
    ) )

    assert "given the command:" in body
    assert "--cascade-plan" in body
    assert "[0 errors][1 warning][0 notes]" in body
    assert "1 warning" in body
    assert "a develop tree is configured" in body
    assert "pass --develop to make this plan executable" in body
    assert "using publisher at [/authored/capy]" in body


def test_unused_develop_with_no_other_tree_is_a_warning_and_notes_not_a_false_error():
    """Soak: develop path exists; forgetting --develop is not 'no local working tree'."""
    key = ( "capy", "capy", "develop" )
    nodes = {
            key: {
                    "name": "capy", "package": "capy", "version": "develop",
                    "_publisher_dir": None,
                    "_develop_dir": "/home/user/coding/capy",
                    "_develop_unused": True,
                    "_lookup_root": "/home/user/.cuppa/publishers",
                    "_clone_url": "git@git.example:packages/capy",
                    "_clone_dir": "/home/user/.cuppa/publishers/capy",
            },
    }
    body = "\n".join( cascade.cascade_plan_lines(
            nodes, [ key ], "corosio", "0.2.0",
            argv=[ "cuppa", "-D", "--cascade-plan", "--build-and-publish-dependencies" ],
    ) )
    # highlight_values wraps --flags in ANSI, so assert tokens rather than a contiguous phrase.
    visible = re.sub( r"\x1b\[[0-9;]*m", "", body )

    assert "[0 errors][1 warning][2 notes]" in visible
    assert "1 warning" in visible
    assert "2 notes" in visible
    lines = visible.splitlines()

    def _index( needle ):
        return next( i for i, line in enumerate( lines ) if needle in line )

    for heading, message in (
            ( "├── 1 warning", "develop tree is configured" ),
            ( "└── 2 notes", "alternatively, cascade will look under" ),
    ):
        heading_i = _index( heading )
        message_i = _index( message )
        assert "│" in lines[heading_i - 1] or "|" in lines[heading_i - 1]
        assert "│" in lines[message_i - 1] or "|" in lines[message_i - 1]

    assert "pass --develop to make this plan executable" in visible
    assert "--clone-publishers" in visible
    assert "to clone into" in visible
    assert "publishers/capy" in visible
    assert "use --publisher-root" in visible
    assert "filesystem package_source" not in visible
    assert "error:" not in visible
    assert "no local working tree" not in visible


def test_unused_develop_with_a_publisher_forest_hit_warns_twice( tmp_path ):
    """Plan executes from the forest copy — warn that this is probably not intended."""
    ( tmp_path / "project" ).mkdir()
    forest = _publisher_tree( tmp_path / "store" / "publishers" / "capy" )
    _publisher_tree( tmp_path / "capy" )

    env = _develop_env( tmp_path, "capy", "../capy" )
    env["storage_root"] = str( tmp_path / "store" )
    entry = {
            "name": "capy",
            "package": "capy",
            "version": "develop",
            "package_source": "git@git.example:packages/capy",
    }
    path = cascade.resolve_publisher_dir( env, entry )

    assert os.path.samefile( path, forest )
    assert entry["_develop_unused"] is True
    assert entry.get( "_publisher_forest_hit" )

    body = "\n".join( cascade.cascade_plan_lines(
            { ( "capy", "capy", "develop" ): dict( entry, _publisher_dir=path ) },
            [ ( "capy", "capy", "develop" ) ],
            "corosio", "0.2.0",
    ) )
    import re

    from cuppa.colourise import as_warning, colouriser

    visible = re.sub( r"\x1b\[[0-9;]*m", "", body )
    assert "[0 errors][2 warnings][1 note]" in visible
    assert "pass --develop to make this plan executable" in visible
    assert "probably not what you intended" in visible
    assert "use --publisher-root" in visible
    # Path alone — no redundant "under [forest-root]" after the publisher path
    # (prose may wrap between "at" and the bracketed path).
    assert "existing publisher tree at" in visible
    assert "under [" not in visible.split( "existing publisher tree at", 1 )[1].split(
            "probably not what you intended", 1
    )[0]
    was = colouriser.use_colour
    colouriser.enable()
    try:
        coloured = "\n".join( cascade.cascade_plan_lines(
                { ( "capy", "capy", "develop" ): dict( entry, _publisher_dir=path ) },
                [ ( "capy", "capy", "develop" ) ],
                "corosio", "0.2.0",
        ) )
        # Plain "/" between severity-coloured root and severity-coloured leaf.
        assert "/" + as_warning( "capy" ) in coloured
        assert "{capy}" not in re.sub( r"\x1b\[[0-9;]*m", "", coloured )
    finally:
        colouriser.use_colour = was


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
    assert node.get( "_clone_dir" )
    assert "_resolve_error" not in node
    assert node.get( "_publisher_dir" ) is None


def test_a_cloneable_url_without_clone_flag_is_a_plan_warning_not_an_error( tmp_path ):
    """Plan mode: opt-in missing is a warning; a real run still StopErrors."""
    env = _PlanEnv( {}, { "storage_root": str( tmp_path / "store" ) } )
    entry = {
            "name": "capy",
            "package": "capy",
            "version": "develop",
            "package_source": "git@git.example:packages/capy",
    }
    publisher = type( "P", (), {
            "_dependencies": [ entry ],
            "_package": "corosio",
            "_version": "0.2.0",
    } )()

    with pytest.raises( SCons.Errors.StopError, match="Pass --clone-publishers" ):
        cascade.build_cascade_graph( env, publisher, tolerant=False )

    nodes, _ = cascade.build_cascade_graph(
            env, publisher, tolerant=True, allow_clone=False
    )
    node = nodes[ ( "capy", "capy", "develop" ) ]
    assert node.get( "_needs_clone_opt_in" ) is True
    assert node.get( "_clone_dir" )
    assert "_resolve_error" not in node

    body = "\n".join( cascade.cascade_plan_lines(
            nodes, [ ( "capy", "capy", "develop" ) ], "corosio", "0.2.0",
            argv=[
                    "cuppa", "-D", "--rel", "--toolchains=gcc15",
                    "--build-and-publish-dependencies", "--cascade-plan",
            ],
    ) )
    assert "given the command:" in body
    assert "[0 errors][1 warning][2 notes]" in body
    assert "1 warning" in body
    assert "pass --clone-publishers to clone into" in body
    assert "make this plan executable" in body
    assert "use --publisher-root" in body
    assert "pass --develop" in body
    assert "filesystem package_source" not in body


def test_colour_plan_command_line_drops_cuppa_mode():
    coloured = cascade.colour_plan_command_line( [
            "cuppa", "-D", "--collect-cascade", "--cuppa-mode",
    ] )
    assert "--cuppa-mode" not in coloured
    assert "--collect-cascade" in coloured


def test_colour_plan_command_line_emphasises_cascade_flags():
    coloured = cascade.colour_plan_command_line( [
            "cuppa", "-D", "--rel", "--toolchains=gcc15",
            "--build-and-publish-dependencies", "--cascade-plan",
            "--capy-gitlab-develop=../capy",
    ] )
    assert coloured.startswith( "cuppa " )
    # Emphasised tokens wrap the flag; values after '=' stay info-coloured.
    assert "--build-and-publish-dependencies" in coloured
    assert "--cascade-plan" in coloured
    assert "--capy-gitlab-develop" in coloured
    assert "../capy" in coloured


def test_finish_plan_only_names_opt_in_flags_when_the_plan_is_only_blocked_by_warnings():
    cascade.reset_plan_reports()
    cascade.record_plan_report(
            "corosio", "0.2.0", 0, needs_clone_opt_in=1, unused_develop=1
    )
    out = io.StringIO()
    status = cascade.finish_plan_only( out=out )
    report = out.getvalue()
    visible = re.sub( r"\x1b\[[0-9;]*m", "", report )

    assert status == 0
    assert "1 package planned" in visible
    assert "pass --clone-publishers along with --publish-package" in visible
    assert "pass --develop along with --publish-package" in visible
    assert "nothing was built, published, uploaded, or cloned" in visible
    assert "without a publisher tree" not in visible
    assert "filesystem package_source" not in visible


def test_finish_plan_only_names_publish_package_when_trees_would_clone_first():
    cascade.reset_plan_reports()
    cascade.record_plan_report( "corosio", "0.2.0", 0, clone_count=1 )
    out = io.StringIO()
    status = cascade.finish_plan_only( out=out )
    visible = re.sub( r"\x1b\[[0-9;]*m", "", out.getvalue() )

    assert status == 0
    assert "1 publisher tree to clone first" in visible
    assert "pass --clone-publishers along with --publish-package to execute" in visible


def test_finish_collect_opt_in_advice_does_not_require_publish_package():
    cascade.reset_plan_reports()
    cascade.record_plan_report(
            "corosio", "0.2.0", 0,
            needs_clone_opt_in=1, mode="collect-cascade", trees_collected=0,
    )
    out = io.StringIO()
    status = cascade.finish_cascade_stop( out=out )
    visible = re.sub( r"\x1b\[[0-9;]*m", "", out.getvalue() )

    assert status == 0
    assert "pass --clone-publishers to clone missing" in visible
    assert "along with --publish-package" not in visible
    assert "nothing was collected" in visible


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


def test_a_develop_path_with_sconstruct_is_a_publisher_source( tmp_path ):
    tree = _publisher_tree( tmp_path / "capy" )

    assert cascade.develop_is_publisher_source( _PlanEnv( {} ), str( tree ) )
    assert cascade.develop_is_publisher_source(
            _PlanEnv( { "build-and-publish-dependencies": True } ), str( tree )
    )


def test_resolve_develop_package_stage_prefers_tool_variant_then_scan( tmp_path ):
    root = tmp_path / "widget"
    stage = (
            root / "_build" / "gcc15" / "rel" / "x86_64" / "cxx2c"
            / "final" / "widget" / "1.0.0"
    )
    ( stage / "include" ).mkdir( parents=True )
    ( stage / "lib" ).mkdir()
    ( stage / "include" / "widget.hpp" ).write_text( "//\n", encoding="utf-8" )

    found = cascade.resolve_develop_package_stage(
            str( root ), "widget", "1.0.0", env=None
    )
    assert found == str( stage )


def test_resolve_develop_package_stage_accepts_version_mismatch_fallback( tmp_path ):
    root = tmp_path / "widget"
    stage = (
            root / "_build" / "gcc" / "dbg" / "x86_64" / "cxx2c"
            / "final" / "widget" / "master"
    )
    ( stage / "include" ).mkdir( parents=True )
    ( stage / "lib" ).mkdir()

    found = cascade.resolve_develop_package_stage(
            str( root ), "widget", "develop", env=None
    )
    assert found == str( stage )


def test_tip_forward_args_stage_only_adds_stage_package_not_publish():
    tip = [ "cuppa", "-D", "--rel", "--publish-package", "--develop" ]
    forwarded = cascade.tip_forward_args( tip, stage_only=True )
    assert "--stage-package" in forwarded
    assert "--publish-package" not in forwarded
    assert "--develop" in forwarded
    assert "-D" in forwarded


def test_tip_forward_args_publish_strips_stage_package():
    tip = [ "cuppa", "-D", "--rel", "--stage-package" ]
    forwarded = cascade.tip_forward_args( tip, stage_only=False )
    assert "--publish-package" in forwarded
    assert "--stage-package" not in forwarded


def test_tip_forward_args_project_only_drops_publish_and_stage_package():
    tip = [
            "cuppa", "-D", "--dbg", "--develop", "--stage-develop",
            "--publish-package", "--stage-package",
    ]
    forwarded = cascade.tip_forward_args( tip, project_only=True )
    assert "--publish-package" not in forwarded
    assert "--stage-package" not in forwarded
    assert "--stage-develop" not in forwarded
    assert "--develop" in forwarded
    assert "--dbg" in forwarded
    assert "-D" in forwarded


def test_tip_forward_args_rejects_stage_only_with_project_only():
    with pytest.raises( ValueError, match="project_only" ):
        cascade.tip_forward_args(
                [ "cuppa", "-D" ], stage_only=True, project_only=True
        )


def test_order_location_stage_candidates_is_leaf_first( tmp_path ):
    leaf = tmp_path / "leaf"
    mid = tmp_path / "mid"
    tip = tmp_path / "tip"
    for path in ( leaf, mid, tip ):
        path.mkdir()
        ( path / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    ( mid / "sconstruct" ).write_text(
            "import cuppa\nWidget = cuppa.location_dependency('leaf', develop={!r})\n"
            .format( str( leaf ) ),
            encoding="utf-8",
    )
    ( tip / "sconstruct" ).write_text(
            "import cuppa\nMid = cuppa.location_dependency('mid', develop={!r})\n"
            .format( str( mid ) ),
            encoding="utf-8",
    )
    candidates = [
            ( "tip", str( tip.resolve() ) ),
            ( "mid", str( mid.resolve() ) ),
            ( "leaf", str( leaf.resolve() ) ),
    ]
    ordered = cascade.order_location_stage_candidates( candidates )
    assert [ name for name, _ in ordered ] == [ "leaf", "mid", "tip" ]


def test_order_location_stage_candidates_refuses_a_cycle( tmp_path ):
    a = tmp_path / "a"
    b = tmp_path / "b"
    for path, other in ( ( a, b ), ( b, a ) ):
        path.mkdir()
        ( path / "sconstruct" ).write_text(
                "develop={!r}\n".format( str( other ) ),
                encoding="utf-8",
        )
    candidates = [
            ( "a", str( a.resolve() ) ),
            ( "b", str( b.resolve() ) ),
    ]
    with pytest.raises( SCons.Errors.StopError, match="cycle" ):
        cascade.order_location_stage_candidates( candidates )


def test_stage_develop_plan_lines_number_leaf_first_order( tmp_path ):
    leaf = tmp_path / "leaf"
    mid = tmp_path / "mid"
    leaf.mkdir()
    mid.mkdir()
    ( leaf / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    ( mid / "sconstruct" ).write_text(
            "Widget = cuppa.location_dependency('leaf', develop={!r})\n"
            .format( str( leaf ) ),
            encoding="utf-8",
    )

    class _Loc:
        _package_manager = None

        def __init__( self, name, develop, location ):
            self._name = name
            self._develop = develop
            self._location = location

        def location_id( self, env ):
            return (
                    self._location,
                    self._develop,
                    None,
                    True,
            )

    leaf_dep = _Loc(
            "leaf", str( leaf ), "git@git.example:org/leaf.git"
    )
    mid_dep = _Loc(
            "mid", str( mid ), "git@git.example:org/mid.git"
    )
    env = _PlanEnv(
            { "develop": True, "stage-develop-plan": True },
            {
                    "dependencies": {
                            "mid": mid_dep.location_id,
                            "leaf": leaf_dep.location_id,
                    },
                    "default_dependencies": [ "mid", "leaf" ],
                    "sconstruct_dir": str( tmp_path ),
            },
    )
    from cuppa.colourise import as_info, as_subdued, colouriser
    from cuppa.utility import storage as storage_util
    import re

    was = colouriser.use_colour
    colouriser.enable()
    try:
        lines = cascade.stage_develop_plan_lines(
                env, argv=[ "cuppa", "-D", "--develop", "--stage-develop-plan" ]
        )
        body = "\n".join( lines )
        visible = re.sub( r"\x1b\[[0-9;]*m", "", body )
        numbered = [ line for line in visible.splitlines() if " of 2" in line ]
        assert len( numbered ) == 2
        assert any( "1 of 2" in line and "leaf" in line for line in numbered )
        assert any( "2 of 2" in line and "mid" in line for line in numbered )
        # Execute (leaf-first) order: leaf before mid visually and by ordinal.
        mid_i = next( i for i, line in enumerate( visible.splitlines() ) if "mid" in line and " of 2" in line )
        leaf_i = next( i for i, line in enumerate( visible.splitlines() ) if "leaf" in line and " of 2" in line )
        assert leaf_i < mid_i
        assert "git.example/org/leaf" in visible
        assert "not a working copy" in visible
        assert "Stage plan summary" in visible
        assert "will stage" in visible
        assert "2 projects will stage" in visible or "2 project will stage" in visible
        assert "nested project build" in visible
        assert "nothing was built or cleaned" in visible
        assert "--stage-develop-plan" in visible
        from cuppa.colourise import as_emphasised
        assert as_emphasised( as_info( "--stage-develop-plan" ) ) in body

        tee, elbow, pipe, gap = storage_util.glyphs()
        stub = pipe.rstrip()
        marker_width = max( len( "unstaged" ), len( "2 of 2" ) )
        under = pipe + " " * ( marker_width + 2 )
        assert as_subdued( under + stub ) in lines
        assert as_subdued( stub ) in lines
        assert any( line.startswith( as_subdued( elbow ) ) and "Stage plan summary" in re.sub(
                r"\x1b\[[0-9;]*m", "", line
        ) for line in lines )
        assert any(
                "no edges to other stage candidates" in line
                and as_info( "no edges to other stage candidates" ) not in line
                for line in lines
        )
        assert any(
                "depends on [" in line and as_info( "leaf" ) in line
                and as_info( "depends on [" ) not in line
                for line in lines
        )
        assert any(
                "project [" in line
                and as_info( storage_util.display_path( str( leaf ) ) ) in line
                for line in lines
        )
    finally:
        colouriser.use_colour = was


def test_stage_depends_lines_colour_each_name_and_wrap():
    from cuppa.colourise import as_info, colouriser

    names = [
            "application", "baa", "common_types", "moo",
            "protocols", "session_protocol", "system",
    ]
    was = colouriser.use_colour
    colouriser.enable()
    try:
        short = cascade._stage_depends_lines( [ "leaf" ], 80 )
        assert short == [ "depends on [" + as_info( "leaf" ) + "]" ]

        wrapped = cascade._stage_depends_lines( names, 55 )
        assert len( wrapped ) >= 2
        assert wrapped[0].startswith( "depends on [" )
        assert wrapped[0].endswith( "," )
        assert wrapped[-1].endswith( "]" )
        assert "depends on [" not in wrapped[1]
        body = "".join( wrapped )
        for name in names:
            assert as_info( name ) in body
        assert as_info( ", " ) not in body
        assert as_info( "depends on [" ) not in body
    finally:
        colouriser.use_colour = was


def test_wrapped_keeps_bracketed_values_whole_for_colouring():
    from cuppa.colourise import as_info, colouriser
    from cuppa.utility import storage as storage_util

    long_deps = (
            "depends on [application, baa, common_types, moo, protocols, "
            "session_protocol, system, transport_layer]"
    )
    pieces = storage_util.wrapped( long_deps, 60 )
    assert len( pieces ) == 1
    assert pieces[0] == long_deps

    was = colouriser.use_colour
    colouriser.enable()
    try:
        highlighted = storage_util.highlight_values( pieces[0], as_info )
        assert as_info(
                "application, baa, common_types, moo, protocols, "
                "session_protocol, system, transport_layer"
        ) in highlighted
    finally:
        colouriser.use_colour = was


def test_stage_repo_hint_reads_location_id_from_dependency_class():
    class _Loc:
        _package_manager = None

        @classmethod
        def create( cls, env ):
            return cls

        @classmethod
        def location_id( cls, env ):
            return (
                    "git@git.example:org/widget.git",
                    "/tmp/widget",
                    None,
                    True,
            )

    env = _PlanEnv( {}, { "dependencies": { "widget": _Loc.create } } )
    assert cascade._location_configured_url( env, "widget" ) == (
            "git@git.example:org/widget.git"
    )
    assert cascade._display_stage_repo_url(
            "git@git.example:org/widget.git"
    ) == "git.example/org/widget"


def test_stage_repo_hint_shows_checkout_branch_and_warns_when_off_branch():
    from cuppa.colourise import as_emphasised, as_info, as_subdued, as_warning, colouriser

    env = _PlanEnv( {}, {} )
    was = colouriser.use_colour
    colouriser.enable()
    try:
        assert cascade._stage_branch_unexpected( "master", "feature_1", env ) is False
        assert cascade._stage_branch_unexpected( "main", "feature_1", env ) is False
        assert cascade._stage_branch_unexpected( "feature_1", "feature_1", env ) is False
        assert cascade._stage_branch_unexpected( "feature_22", "feature_1", env ) is True

        expected = cascade._format_stage_repo_hint(
                "git.example/org/storage", "feature_1", "clean", False
        )
        assert re.sub( r"\x1b\[[0-9;]*m", "", expected ) == (
                " (git.example/org/storage@feature_1 clean)"
        )
        assert as_subdued( "feature_1" ) in expected
        assert as_warning( "feature_1" ) not in expected

        tip = cascade._format_stage_repo_hint(
                "git.example/org/matching_facility",
                "feature_1",
                "clean, no upstream",
                False,
                emphasise_ref=True,
        )
        assert as_emphasised( as_info( "feature_1" ) ) in tip
        assert as_subdued( "feature_1" ) not in tip

        unexpected = cascade._format_stage_repo_hint(
                "git.example/org/storage", "feature_22", "clean", True
        )
        assert re.sub( r"\x1b\[[0-9;]*m", "", unexpected ) == (
                " (git.example/org/storage@feature_22 clean)"
        )
        assert as_warning( "feature_22" ) in unexpected
        assert as_subdued( "feature_22" ) not in unexpected
    finally:
        colouriser.use_colour = was


def test_stage_expected_branches_prefer_detected_default_and_emphasise():
    from cuppa.colourise import as_emphasised, as_info, colouriser
    from cuppa.utility.preprocess import AnsiEscape
    from cuppa.utility import storage as storage_util

    was = colouriser.use_colour
    colouriser.enable()
    try:
        assert cascade._stage_expected_branches( "feature_1", "master" ) == [
                "feature_1",
                "master",
                "main",
        ]
        assert cascade._stage_expected_branches( "feature_1", "main" ) == [
                "feature_1",
                "main",
                "master",
        ]
        assert cascade._stage_expected_branches( None, "master" ) == [
                "master",
                "main",
        ]

        phrase = cascade._format_stage_expected_branches_phrase(
                "feature_1", "master"
        )
        assert AnsiEscape.strip( phrase ).replace( "\u00a0", " " ) == (
                "feature_1 or master or main"
        )
        assert as_emphasised( as_info( "feature_1" ) ) in phrase
        assert as_emphasised( as_info( "master" ) ) in phrase
        assert as_info( "main" ) in phrase
        assert as_emphasised( as_info( "main" ) ) not in phrase

        env = _PlanEnv( {}, { "location_default_branch": "main" } )
        assert cascade._stage_preferred_default_branch( env ) == "main"
        assert cascade._stage_preferred_default_branch( _PlanEnv( {}, {} ) ) == (
                "master"
        )

        # Keep ``expected branches (…)`` together when the line wraps.
        warning = (
                "transport_layer branch is [feature_22] which deviates from "
                "the expected\u00a0branches\u00a0({})".format( phrase )
        )
        pieces = storage_util.wrapped( warning, 70 )
        assert not any(
                AnsiEscape.strip( piece ).lstrip().startswith( "(" )
                for piece in pieces
        )
        joined = " ".join(
                AnsiEscape.strip( piece ).replace( "\u00a0", " " )
                for piece in pieces
        )
        assert "expected branches (feature_1 or master or main)" in joined
    finally:
        colouriser.use_colour = was


def test_working_copy_default_branch_reads_origin_head( tmp_path, monkeypatch ):
    from cuppa.scms.git import Git

    repo = tmp_path / "repo"
    ( repo / ".git" ).mkdir( parents=True )

    monkeypatch.setattr(
            Git,
            "execute_command",
            lambda command, path=None: "origin/master",
    )
    assert Git.working_copy_default_branch( str( repo ) ) == "master"

    monkeypatch.setattr(
            Git,
            "execute_command",
            lambda command, path=None: "origin/main",
    )
    assert Git.working_copy_default_branch( str( repo ) ) == "main"

    def raise_error( command, path=None ):
        raise Git.Error( "missing" )

    monkeypatch.setattr( Git, "execute_command", raise_error )
    assert Git.working_copy_default_branch( str( repo ) ) is None
    assert Git.working_copy_default_branch( str( tmp_path / "absent" ) ) is None


def test_stage_develop_plan_lists_unstaged_after_leaf_first_stage_order( tmp_path ):
    import re

    from cuppa.colourise import as_error, colouriser

    present = tmp_path / "present"
    present.mkdir()
    ( present / "sconstruct" ).write_text(
            "Missing = cuppa.location_dependency('ghost', develop={!r})\n"
            .format( str( tmp_path / "ghost" ) ),
            encoding="utf-8",
    )
    missing = tmp_path / "ghost"

    class _Loc:
        _package_manager = None

        def __init__( self, name, develop, location ):
            self._name = name
            self._develop = develop
            self._location = location

        def location_id( self, env ):
            return ( self._location, self._develop, None, True )

    ghost = _Loc( "ghost", str( missing ), "git@git.example:org/ghost.git" )
    present_dep = _Loc(
            "present", str( present ), "git@git.example:org/present.git"
    )
    env = _PlanEnv(
            { "develop": True, "stage-develop-plan": True },
            {
                    "dependencies": {
                            "ghost": ghost.location_id,
                            "present": present_dep.location_id,
                    },
                    "default_dependencies": [ "ghost", "present" ],
                    "sconstruct_dir": str( tmp_path ),
            },
    )
    was = colouriser.use_colour
    colouriser.enable()
    try:
        body = "\n".join( cascade.stage_develop_plan_lines( env ) )
    finally:
        colouriser.use_colour = was
    visible = re.sub( r"\x1b\[[0-9;]*m", "", body )
    assert "unstaged" in visible
    assert "1 of 1" in visible
    assert "project [" in visible and "is missing" in visible
    assert "1 error" in visible
    assert "[1 error]" in visible
    assert "Use " in visible and "clone-develop" in visible
    assert "wants git.example/org/ghost" in visible
    # Execute order: nestable first, then unstaged marker row.
    present_i = next(
            i for i, line in enumerate( visible.splitlines() )
            if "1 of 1" in line and "present" in line
    )
    ghost_i = next(
            i for i, line in enumerate( visible.splitlines() )
            if "unstaged" in line and "ghost" in line
    )
    assert present_i < ghost_i
    from cuppa.colourise import as_emphasised, as_info
    assert as_emphasised( as_info( "--clone-develop" ) ) in body
    assert as_error( "ghost" ) in body


def test_finish_stage_develop_plan_errors_on_missing_path( tmp_path ):
    class _Loc:
        _package_manager = None
        _name = "ghost"
        _develop = str( tmp_path / "missing" )

        def location_id( self, env ):
            return (
                    "https://example.com/ghost.git",
                    self._develop,
                    None,
                    True,
            )

    loc = _Loc()
    env = _PlanEnv(
            { "develop": True, "stage-develop-plan": True },
            {
                    "dependencies": { "ghost": loc.location_id },
                    "default_dependencies": [ "ghost" ],
                    "sconstruct_dir": str( tmp_path ),
            },
    )
    out = io.StringIO()
    status = cascade.finish_stage_develop_plan( env, out=out )
    assert status == 1
    assert "is missing" in out.getvalue()
    assert "unstaged" in out.getvalue()


def test_tip_forward_args_drops_stage_develop_plan():
    tip = [ "cuppa", "-D", "--dbg", "--develop", "--stage-develop-plan" ]
    forwarded = cascade.tip_forward_args( tip, project_only=True )
    assert "--stage-develop-plan" not in forwarded
    assert "--develop" in forwarded


def test_run_location_stage_develop_nests_with_ordinals( tmp_path, monkeypatch ):
    project = tmp_path / "widget"
    project.mkdir()
    ( project / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )
    calls = []

    def _nest( env, project_dir, label, ordinal=1, total=1 ):
        calls.append( ( project_dir, label, ordinal, total ) )

    monkeypatch.setattr(
            "cuppa.package_managers.package_cascade.run_nested_location_project",
            _nest,
    )

    class _Dep:
        _name = "widget"
        _package_manager = None
        _develop = str( project )

        def location_id( self, env ):
            return (
                    "https://example.com/widget.git",
                    str( project ),
                    None,
                    True,
            )

    dep = _Dep()
    env = _PlanEnv(
            { "develop": True, "stage-develop": True },
            {
                    "dependencies": { "widget": dep.location_id },
                    "default_dependencies": [ "widget" ],
                    "sconstruct_dir": str( tmp_path ),
            },
    )
    cascade.run_location_stage_develop( env )
    assert calls == [ ( str( project.resolve() ), "widget", 1, 1 ) ]

    # Same tip process: second call is a no-op.
    cascade.run_location_stage_develop( env )
    assert len( calls ) == 1


def test_location_stage_candidates_skips_packages_and_counts_many( tmp_path ):
    loc_a = tmp_path / "a"
    loc_b = tmp_path / "b"
    for path in ( loc_a, loc_b ):
        path.mkdir()
        ( path / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )

    class _Loc:
        _package_manager = None

        def __init__( self, name, develop ):
            self._name = name
            self._develop = develop

        def location_id( self, env ):
            return (
                    "https://example.com/{}.git".format( self._name ),
                    self._develop,
                    None,
                    True,
            )

    class _Pkg:
        _package_manager = "gitlab"
        _name = "boost"
        _develop = str( loc_a )

    a = _Loc( "alpha", str( loc_a ) )
    b = _Loc( "beta", str( loc_b ) )
    pkg = _Pkg()
    env = _PlanEnv(
            {},
            {
                    "dependencies": {
                            "alpha": a.location_id,
                            "beta": b.location_id,
                            "boost": pkg,
                    },
                    "default_dependencies": [ "beta", "alpha" ],
                    "sconstruct_dir": str( tmp_path ),
            },
    )

    found = cascade.location_stage_candidates( env )
    assert [ name for name, _ in found ] == [ "beta", "alpha" ]
    assert found[0][1] == str( loc_b.resolve() )
    assert found[1][1] == str( loc_a.resolve() )


def test_run_location_stage_develop_skips_without_flag( tmp_path, monkeypatch ):
    project = tmp_path / "widget"
    project.mkdir()
    ( project / "sconstruct" ).write_text( "import cuppa\n", encoding="utf-8" )

    class _Dep:
        _package_manager = None
        _name = "widget"
        _develop = str( project )

        def location_id( self, env ):
            return (
                    "https://example.com/widget.git",
                    str( project ),
                    None,
                    True,
            )

    dep = _Dep()
    monkeypatch.setattr(
            "cuppa.package_managers.package_cascade.run_nested_location_project",
            lambda *a, **k: (_ for _ in ()).throw( AssertionError( "nest" ) ),
    )
    env = _PlanEnv(
            { "develop": True, "stage-develop": False },
            {
                    "dependencies": { "widget": dep.location_id },
                    "default_dependencies": [ "widget" ],
                    "sconstruct_dir": str( tmp_path ),
            },
    )
    cascade.run_location_stage_develop( env )


def test_run_location_stage_develop_skips_prefix_shaped_tree(
        tmp_path, monkeypatch
):
    prefix = tmp_path / "widget"
    ( prefix / "include" ).mkdir( parents=True )
    ( prefix / "lib" ).mkdir()

    class _Loc:
        _package_manager = None
        _name = "widget"
        _develop = str( prefix )

        def location_id( self, env ):
            return ( "https://example.com/w.git", str( prefix ), None, True )

    loc = _Loc()
    monkeypatch.setattr(
            "cuppa.package_managers.package_cascade.run_nested_location_project",
            lambda *a, **k: (_ for _ in ()).throw( AssertionError( "nest" ) ),
    )
    env = _PlanEnv(
            { "develop": True, "stage-develop": True },
            {
                    "dependencies": { "widget": loc.location_id },
                    "default_dependencies": [ "widget" ],
                    "sconstruct_dir": str( tmp_path ),
            },
    )
    cascade.run_location_stage_develop( env )


def test_looks_like_package_stage_requires_include_and_lib( tmp_path ):
    path = tmp_path / "stage"
    ( path / "include" ).mkdir( parents=True )
    assert not cascade.looks_like_package_stage( str( path ) )
    ( path / "lib" ).mkdir()
    assert cascade.looks_like_package_stage( str( path ) )


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
    assert "1 warning" in body
    assert "publishing from this tree has 2 commits not pushed" in body
    assert "published anyway" in body
    assert "only refuses a develop tree" in body


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
