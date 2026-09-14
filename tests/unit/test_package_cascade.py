#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

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

    path = cascade.resolve_publisher_dir(
            _Env(),
            { "name": "protobuf", "package": "protobuf", "version": "1" },
    )
    assert path == str( nested )


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
