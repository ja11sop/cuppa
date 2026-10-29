#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for named GitLab package library groups."""

from pathlib import Path

import pytest
import SCons.Errors

from cuppa.package_managers.cuppa_publish_manifest import (
        build_publish_document,
        package_lib_groups,
        read_publish_manifest,
        write_publish_manifest,
)
from cuppa.package_managers.package_lib_groups import (
        catalogue_lib_groups,
        expand_use_lib_tokens,
        normalise_lib_groups,
        show_libs_for_token,
)


pytestmark = pytest.mark.unit


def test_normalise_lib_groups_accepts_mapping_and_string_member():
    assert normalise_lib_groups( None ) is None
    assert normalise_lib_groups( {
            "kms": [ "kms_client", "kms_protos" ],
            "storage": "storage_client",
    } ) == {
            "kms": [ "kms_client", "kms_protos" ],
            "storage": [ "storage_client" ],
    }


def test_normalise_lib_groups_rejects_non_mapping():
    with pytest.raises( SCons.Errors.StopError, match="mapping" ):
        normalise_lib_groups( [ "kms" ] )


def test_expand_use_lib_tokens_mixes_groups_and_leaves():
    groups = {
            "kms": [ "kms_client", "kms_protos" ],
            "storage": [ "storage_client" ],
    }
    assert expand_use_lib_tokens(
            [ "kms", "extra", "storage", "kms_client" ],
            groups,
    ) == [ "kms_client", "kms_protos", "extra", "storage_client" ]


def test_expand_nested_groups_and_detects_cycles():
    groups = {
            "cloud": [ "storage", "kms_client" ],
            "storage": [ "storage_client" ],
    }
    assert expand_use_lib_tokens( [ "cloud" ], groups ) == [
            "storage_client",
            "kms_client",
    ]
    cyclic = { "a": [ "b" ], "b": [ "a" ] }
    with pytest.raises( SCons.Errors.StopError, match="cycle" ):
        expand_use_lib_tokens( [ "a" ], cyclic )


def test_expand_group_may_include_same_named_leaf():
    """Group token shadows the leaf, but the group body may list that leaf."""
    groups = {
            "kms": [ "kms", "kms_protos", "grpc utils" ],
            "grpc utils": [ "grpc_utils", "common" ],
    }
    assert expand_use_lib_tokens( [ "kms" ], groups ) == [
            "kms",
            "kms_protos",
            "grpc_utils",
            "common",
    ]


def test_show_libs_for_token_leaf_or_group():
    groups = { "kms": [ "kms_client", "kms_protos" ] }
    assert show_libs_for_token( "kms", groups ) == [ "kms_client", "kms_protos" ]
    assert show_libs_for_token( "standalone", groups ) == [ "standalone" ]


def test_catalogue_lib_groups_reports_ungrouped_stems():
    groups = { "kms": [ "kms_client" ] }
    catalogue = catalogue_lib_groups(
            groups,
            linkable_stems=[ "kms_client", "orphan", "extra" ],
    )
    assert catalogue["groups"]["kms"] == [ "kms_client" ]
    assert catalogue["ungrouped"] == [ "orphan", "extra" ]


def test_publish_manifest_round_trips_lib_groups( tmp_path: Path ):
    groups = {
            "kms": [ "kms_client", "kms_protos" ],
            "cloud storage": [ "storage_client" ],
    }
    document = build_publish_document(
            "mega",
            "1.0.0",
            dependencies=[],
            lib_groups=groups,
    )
    assert document["lib_groups"] == groups

    write_publish_manifest(
            str( tmp_path ),
            "mega",
            "1.0.0",
            dependencies=[],
            lib_groups=groups,
            payload_sha256=None,
    )
    loaded = read_publish_manifest( str( tmp_path ) )
    assert loaded["lib_groups"] == groups
    assert package_lib_groups( str( tmp_path ) ) == groups


def test_gitlab_use_libs_expands_groups( tmp_path: Path, monkeypatch ):
    from cuppa.package_managers import gitlab as gitlab_module

    package_dir = tmp_path / "pkg"
    lib_dir = package_dir / "lib"
    lib_dir.mkdir( parents=True )
    for stem in ( "kms_client", "kms_protos", "extra" ):
        ( lib_dir / "lib{}.a".format( stem ) ).write_bytes( b"a" )

    write_publish_manifest(
            str( package_dir ),
            "mega",
            "1.0.0",
            dependencies=[],
            lib_groups={ "kms": [ "kms_client", "kms_protos" ] },
            payload_sha256=None,
    )

    applied = []

    def fake_apply( env, lib_path, libs, **kwargs ):
        applied.append( list( libs ) )
        return { "static": list( libs ), "shared": [], "libpath": [ lib_path ] }

    import cuppa.package_managers.package_link_libs as link_libs
    import cuppa.package_managers.cuppa_dependency_apply as apply_mod

    monkeypatch.setattr( link_libs, "apply_resolved_libs", fake_apply )
    monkeypatch.setattr( apply_mod, "apply_transitive_use_libs", lambda *a, **k: None )

    class _Env( dict ):
        def AppendUnique( self, **kwargs ):
            return None

        def Depends( self, *args ):
            return None

        def subst( self, text ):
            return text.replace( "$LIBPREFIX", "lib" ).replace( "$LIBSUFFIX", ".a" ).replace(
                    "$SHLIBPREFIX", "lib"
            ).replace( "$SHLIBSUFFIX", ".so" )

    # Build a minimal GitlabPackageDependency-like object
    dep = object.__new__( gitlab_module.GitlabPackageDependency )
    dep._env = _Env( LIBPREFIX="lib", LIBSUFFIX=".a", SHLIBPREFIX="lib", SHLIBSUFFIX=".so" )
    dep._package_dir = str( package_dir )
    dep._lib_dir = str( lib_dir )
    dep._library_prefix = ""
    dep._pkg_config_dir = None
    dep._package_id = "mega/1.0.0"
    dep._package = "mega"
    dep._registry = object()

    # Bind methods from the class
    dep._resolve_lib_groups = gitlab_module.GitlabPackageDependency._resolve_lib_groups.__get__(
            dep
    )
    dep._link_contrib_key = gitlab_module.GitlabPackageDependency._link_contrib_key.__get__(
            dep
    )
    dep._package_link_mode = lambda: "prefer_static"
    dep.include_dir = lambda: str( package_dir / "include" )
    dep.use_libs = gitlab_module.GitlabPackageDependency.use_libs.__get__( dep )
    dep.show_libs_for = gitlab_module.GitlabPackageDependency.show_libs_for.__get__( dep )
    dep.show_all_libs = gitlab_module.GitlabPackageDependency.show_all_libs.__get__( dep )

    dep.use_libs( [ "kms", "extra" ] )
    assert applied == [ [ "kms_client", "kms_protos", "extra" ] ]

    assert dep.show_libs_for( "kms" ) == [ "kms_client", "kms_protos" ]
    catalogue = dep.show_all_libs()
    assert catalogue["groups"]["kms"] == [ "kms_client", "kms_protos" ]
    assert "extra" in catalogue["ungrouped"]


def test_gitlab_use_libs_pkg_config_missing_pc_hints_lib_groups( tmp_path: Path ):
    import SCons.Errors
    from cuppa.package_managers import gitlab as gitlab_module

    package_dir = tmp_path / "pkg"
    lib_dir = package_dir / "lib"
    pc_dir = lib_dir / "pkgconfig"
    pc_dir.mkdir( parents=True )
    # No lib_groups in traveling JSON; no .pc for the group-shaped token.
    write_publish_manifest(
            str( package_dir ),
            "mega",
            "1.0.0",
            dependencies=[],
            payload_sha256=None,
    )

    class _Env( dict ):
        def AppendUnique( self, **kwargs ):
            return None

        def Depends( self, *args ):
            return None

        def ParseConfig( self, command ):
            raise AssertionError( "ParseConfig should not run: " + command )

    dep = object.__new__( gitlab_module.GitlabPackageDependency )
    dep._env = _Env()
    dep._package_dir = str( package_dir )
    dep._lib_dir = str( lib_dir )
    dep._library_prefix = "mega_"
    dep._pkg_config_dir = str( pc_dir )
    dep._package_id = "mega/1.0.0"
    dep._package = "mega"
    dep._registry = object()
    dep._resolve_lib_groups = gitlab_module.GitlabPackageDependency._resolve_lib_groups.__get__(
            dep
    )
    dep._link_contrib_key = gitlab_module.GitlabPackageDependency._link_contrib_key.__get__(
            dep
    )
    dep.include_dir = lambda: str( package_dir / "include" )
    dep.use_libs = gitlab_module.GitlabPackageDependency.use_libs.__get__( dep )

    with pytest.raises( SCons.Errors.StopError, match="lib_groups" ) as raised:
        dep.use_libs( [ "widget_libs" ] )
    message = str( raised.value )
    assert "\x1b" not in message
    assert "0m" not in message
    assert "widget_libs.pc" in message
