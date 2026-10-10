#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for GitLab package version bounds."""

from pathlib import Path

import pytest
import SCons.Errors

from cuppa.package_managers.package_version_bound import (
        VersionBoundConflict,
        VersionBoundError,
        cached_package_versions,
        format_bound_with_resolved,
        intersect_version_bounds,
        parse_version_bound,
        resolve_bound_to_concrete,
        select_highest_satisfying,
        version_satisfies,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
        "token, kind, version, display",
        [
                ( "1.28.0", "exact", "1.28.0", "1.28.0" ),
                ( "==1.28.0", "exact", "1.28.0", "1.28.0" ),
                ( "== 1.28.0", "exact", "1.28.0", "1.28.0" ),
                ( ">=1.28.0", "minimum", "1.28.0", ">=1.28.0" ),
                ( ">= 1.28.0", "minimum", "1.28.0", ">=1.28.0" ),
                ( "latest", "latest", None, "latest" ),
                ( "Latest", "latest", None, "latest" ),
        ],
)
def test_parse_supported( token, kind, version, display ):
    bound = parse_version_bound( token )
    assert bound.kind == kind
    assert bound.version == version
    assert bound.display() == display


@pytest.mark.parametrize(
        "token",
        [
                ">=1.28.0,<2.0.0",
                "~=1.28.0",
                "^1.28.0",
                ">=1.28.0,!=1.29.0",
                "1.28.*",
                ">=1.28.0, <2",
                "",
                None,
        ],
)
def test_parse_unsupported( token ):
    with pytest.raises( VersionBoundError ):
        parse_version_bound( token )


def test_version_satisfies_minimum_and_exact():
    minimum = parse_version_bound( ">=1.28.0" )
    exact = parse_version_bound( "1.30.0" )
    assert version_satisfies( minimum, "1.28.0" )
    assert version_satisfies( minimum, "1.29.1" )
    assert not version_satisfies( minimum, "1.27.0" )
    assert version_satisfies( exact, "1.30.0" )
    assert not version_satisfies( exact, "1.30.1" )


def test_intersect_compatible_minima():
    left = parse_version_bound( ">=1.28.0" )
    right = parse_version_bound( ">=1.30.0" )
    assert intersect_version_bounds( left, right ).display() == ">=1.30.0"
    assert intersect_version_bounds( right, left ).display() == ">=1.30.0"


def test_intersect_exact_and_minimum():
    exact = parse_version_bound( "1.30.0" )
    minimum = parse_version_bound( ">=1.28.0" )
    assert intersect_version_bounds( exact, minimum ) == exact
    assert intersect_version_bounds( minimum, exact ) == exact


def test_intersect_exact_conflict():
    with pytest.raises( VersionBoundConflict, match="disagree" ):
        intersect_version_bounds(
                parse_version_bound( "1.28.0" ),
                parse_version_bound( "1.30.0" ),
        )


def test_intersect_exact_outside_minimum():
    with pytest.raises( VersionBoundConflict, match="does not satisfy" ):
        intersect_version_bounds(
                parse_version_bound( ">=1.30.0" ),
                parse_version_bound( "==1.28.0" ),
        )


def test_intersect_latest_yields_other():
    latest = parse_version_bound( "latest" )
    minimum = parse_version_bound( ">=1.28.0" )
    assert intersect_version_bounds( latest, minimum ) == minimum
    assert intersect_version_bounds( minimum, latest ) == minimum


def test_select_highest_satisfying():
    bound = parse_version_bound( ">=1.28.0" )
    assert select_highest_satisfying(
            bound, [ "1.27.0", "1.28.0", "1.29.1" ]
    ) == "1.29.1"
    assert select_highest_satisfying( bound, [ "1.27.0" ] ) is None


def test_format_bound_with_resolved():
    assert format_bound_with_resolved(
            parse_version_bound( ">=1.28.0" ), "1.29.1"
    ) == ">=1.28.0 → 1.29.1"
    assert format_bound_with_resolved(
            parse_version_bound( "1.28.0" ), "1.28.0"
    ) == "1.28.0"


def test_cached_package_versions( tmp_path: Path ):
    pkg = tmp_path / "packages" / "widget-core"
    ( pkg / "1.28.0" ).mkdir( parents=True )
    ( pkg / "1.29.1" ).mkdir()
    ( pkg / "notes.txt" ).write_text( "x" )
    assert sorted( cached_package_versions( tmp_path, "widget-core" ) ) == [
            "1.28.0",
            "1.29.1",
    ]


def test_resolve_minimum_offline_uses_cache( tmp_path: Path, monkeypatch ):
    pkg = tmp_path / "packages" / "widget-core"
    ( pkg / "1.28.0" ).mkdir( parents=True )
    ( pkg / "1.29.1" ).mkdir()

    env = { "offline": True, "downloads_root": str( tmp_path ) }
    bound = parse_version_bound( ">=1.28.0" )

    def boom( *args, **kwargs ):
        raise AssertionError( "registry list should not run offline" )

    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.list_generic_package_versions",
            boom,
    )
    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.stored_registry_latest",
            lambda *a, **k: None,
    )

    assert resolve_bound_to_concrete(
            env,
            bound,
            registry="https://gitlab.example/api/v4/projects/1",
            package="widget-core",
    ) == "1.29.1"


def test_resolve_minimum_offline_fails_when_cache_too_old( tmp_path: Path, monkeypatch ):
    pkg = tmp_path / "packages" / "widget-core"
    ( pkg / "1.27.0" ).mkdir( parents=True )
    env = { "offline": True, "downloads_root": str( tmp_path ) }
    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.stored_registry_latest",
            lambda *a, **k: None,
    )
    with pytest.raises( SCons.Errors.StopError, match="Offline" ):
        resolve_bound_to_concrete(
                env,
                parse_version_bound( ">=1.28.0" ),
                registry="https://gitlab.example/api/v4/projects/1",
                package="widget-core",
        )


def test_resolve_minimum_keeps_cache_without_refresh( tmp_path: Path, monkeypatch ):
    pkg = tmp_path / "packages" / "widget-core"
    ( pkg / "1.28.0" ).mkdir( parents=True )
    env = { "offline": False, "downloads_root": str( tmp_path ) }
    listed = []

    def opener_list( *args, **kwargs ):
        listed.append( True )
        return [ "1.28.0", "1.29.1" ]

    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.list_generic_package_versions",
            opener_list,
    )
    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.stored_registry_latest",
            lambda *a, **k: None,
    )

    assert resolve_bound_to_concrete(
            env,
            parse_version_bound( ">=1.28.0" ),
            registry="https://gitlab.example/api/v4/projects/1",
            package="widget-core",
            force_refresh=False,
    ) == "1.28.0"
    assert listed == []


def test_resolve_minimum_refresh_picks_registry_highest( tmp_path: Path, monkeypatch ):
    pkg = tmp_path / "packages" / "widget-core"
    ( pkg / "1.28.0" ).mkdir( parents=True )
    env = { "offline": False, "downloads_root": str( tmp_path ) }
    remembered = {}

    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.list_generic_package_versions",
            lambda *a, **k: [ "1.28.0", "1.29.1" ],
    )
    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.stored_registry_latest",
            lambda *a, **k: None,
    )
    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.remember_registry_latest",
            lambda env, registry, package, version: remembered.setdefault(
                    package, version
            ),
    )

    assert resolve_bound_to_concrete(
            env,
            parse_version_bound( ">=1.28.0" ),
            registry="https://gitlab.example/api/v4/projects/1",
            package="widget-core",
            force_refresh=True,
    ) == "1.29.1"
    assert remembered["widget-core"] == "1.29.1"


def test_resolve_exact_returns_pin_without_list( monkeypatch ):
    env = { "offline": False }

    def boom( *args, **kwargs ):
        raise AssertionError( "exact should not list registry" )

    monkeypatch.setattr(
            "cuppa.package_managers.gitlab_latest.list_generic_package_versions",
            boom,
    )
    assert resolve_bound_to_concrete(
            env,
            parse_version_bound( "==1.28.0" ),
            registry="https://gitlab.example/api/v4/projects/1",
            package="widget-core",
    ) == "1.28.0"
