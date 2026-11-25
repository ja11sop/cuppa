#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json
import os
from pathlib import Path

import pytest

from cuppa.package_managers.pkgconfig_paths import (
        dependency_pkg_config_dirs,
        discover_pkg_config_dir,
        merge_pkg_config_search_dirs,
        pkg_config_with_path_args,
        traveling_dependency_names,
)

pytestmark = pytest.mark.unit


def _write_publish( package_dir: Path, **fields ):
    document = { "cuppa_publish_format": 1, "package": "widget", "version": "1.0.0" }
    document.update( fields )
    package_dir.mkdir( parents=True, exist_ok=True )
    ( package_dir / "cuppa-publish.json" ).write_text(
            json.dumps( document ), encoding="utf-8"
    )


def _write_pc( directory: Path, name: str, requires: str = "" ):
    directory.mkdir( parents=True, exist_ok=True )
    body = [
            "prefix=/usr",
            "Name: {}".format( name ),
            "Description: {}".format( name ),
            "Version: 1.0.0",
            "Libs: -l{}".format( name ),
    ]
    if requires:
        body.insert( -1, "Requires: {}".format( requires ) )
    ( directory / "{}.pc".format( name ) ).write_text(
            "\n".join( body ) + "\n", encoding="utf-8"
    )


def test_discover_uses_traveling_pkg_config_dir( tmp_path: Path ):
    root = tmp_path / "widget" / "1.0.0"
    pc = root / "share" / "pkgconfig"
    _write_pc( pc, "widget" )
    _write_publish( root, pkg_config_dir="share/pkgconfig" )
    assert discover_pkg_config_dir( str( root ) ) == str( pc.resolve() )


def test_discover_falls_back_to_lib_pkgconfig_when_key_omitted( tmp_path: Path ):
    root = tmp_path / "grpc_like" / "1.0.0"
    pc = root / "lib" / "pkgconfig"
    _write_pc( pc, "widget_core" )
    _write_publish( root )
    assert discover_pkg_config_dir( str( root ) ) == str( pc.resolve() )


def test_discover_falls_back_to_share_pkgconfig( tmp_path: Path ):
    root = tmp_path / "json_like" / "1.0.0"
    pc = root / "share" / "pkgconfig"
    _write_pc( pc, "widget_json" )
    _write_publish( root )
    assert discover_pkg_config_dir( str( root ) ) == str( pc.resolve() )


def test_discover_skips_empty_lib_pkgconfig_without_manifest_key( tmp_path: Path ):
    root = tmp_path / "empty" / "1.0.0"
    ( root / "lib" / "pkgconfig" ).mkdir( parents=True )
    _write_publish( root )
    assert discover_pkg_config_dir( str( root ) ) is None


def test_with_path_args_are_repeated_not_colon_joined():
    assert pkg_config_with_path_args( [ "/a", "/b" ] ) == (
            "--with-path=/a --with-path=/b"
    )


def test_merge_keeps_primary_first_and_dedupes( tmp_path: Path ):
    primary = str( ( tmp_path / "primary" ).resolve() )
    other = str( ( tmp_path / "other" ).resolve() )
    assert merge_pkg_config_search_dirs( primary, [ other, primary, other ] ) == [
            primary,
            other,
    ]


def test_dependency_closure_composes_child_and_grandchild( tmp_path: Path ):
    parent = tmp_path / "parent" / "1.0.0"
    child = tmp_path / "child" / "1.0.0"
    grand = tmp_path / "grand" / "1.0.0"
    _write_pc( parent / "lib" / "pkgconfig", "widget_parent", requires="widget_child" )
    _write_pc( child / "lib" / "pkgconfig", "widget_child", requires="widget_grand" )
    _write_pc( grand / "lib" / "pkgconfig", "widget_grand" )
    _write_publish(
            parent,
            pkg_config_dir="lib/pkgconfig",
            dependencies=[ { "name": "child", "package": "child", "version": "1.0.0" } ],
    )
    _write_publish(
            child,
            dependencies=[ { "name": "grand", "package": "grand", "version": "1.0.0" } ],
    )
    _write_publish( grand )

    roots = {
            "child": str( child ),
            "grand": str( grand ),
    }

    dirs = dependency_pkg_config_dirs( str( parent ), roots.get )
    assert dirs == [
            str( ( child / "lib" / "pkgconfig" ).resolve() ),
            str( ( grand / "lib" / "pkgconfig" ).resolve() ),
    ]
    assert traveling_dependency_names( str( parent ) ) == [ "child" ]


def test_parse_pkg_config_includes_dependency_with_path( tmp_path: Path ):
    from types import SimpleNamespace

    from cuppa.package_managers.gitlab import GitlabPackageDependency

    parent = tmp_path / "parent" / "1.0.0"
    child = tmp_path / "child" / "1.0.0"
    parent_pc = parent / "lib" / "pkgconfig"
    child_pc = child / "lib" / "pkgconfig"
    _write_pc( parent_pc, "widget_kms", requires="widget_core" )
    _write_pc( child_pc, "widget_core" )
    _write_publish(
            parent,
            pkg_config_dir="lib/pkgconfig",
            library_prefix="widget_",
            dependencies=[ { "name": "child", "package": "child", "version": "1.0.0" } ],
    )
    _write_publish( child )

    dependency = GitlabPackageDependency.__new__( GitlabPackageDependency )
    dependency._clean = False
    dependency._library_prefix = "widget_"
    dependency._package_id = "widget/1.0.0/rel"
    dependency._package_dir = str( parent )
    dependency._pkg_config_dir_argument = None
    dependency._pkg_config_dir = None
    dependency._env = SimpleNamespace(
            parsed=[],
            ParseConfig=lambda command: dependency._env.parsed.append( command ),
    )
    dependency._resolve_dependency_package_dir = (
            lambda name: str( child ) if name == "child" else None
    )

    dependency.parse_pkg_config( [ "kms" ] )
    assert len( dependency._env.parsed ) == 1
    command = dependency._env.parsed[0]
    assert "--with-path={}".format( parent_pc.resolve() ) in command
    assert "--with-path={}".format( child_pc.resolve() ) in command
    assert command.index( str( parent_pc.resolve() ) ) < command.index(
            str( child_pc.resolve() )
    )
    assert "widget_kms" in command
