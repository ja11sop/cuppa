#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest
import SCons.Errors

from cuppa.package_managers import publish_version as pv


pytestmark = pytest.mark.unit


def test_is_floating_publish_version():
    assert pv.is_floating_publish_version( None )
    assert pv.is_floating_publish_version( "latest" )
    assert pv.is_floating_publish_version( "LATEST" )
    assert pv.is_floating_publish_version( "current" )
    assert not pv.is_floating_publish_version( "1.92" )
    assert not pv.is_floating_publish_version( "1.92.0" )


def test_boost_style_dot_version():
    assert pv._boost_style_dot_version( "1_92" ) == "1.92"
    assert pv._boost_style_dot_version( "1.92.0" ) == "1.92"
    assert pv._boost_style_dot_version( "1.91" ) == "1.91"


def test_resolve_publisher_version_concrete_passthrough():
    seed, concrete = pv.resolve_publisher_version(
            env=None, package="widget", version="1.0.0"
    )
    assert seed == "1.0.0"
    assert concrete == "1.0.0"


def test_resolve_publisher_version_from_build_with_boost( monkeypatch ):
    class Env:
        pass

    monkeypatch.setattr(
            pv,
            "_concrete_from_build_with",
            lambda env, package: "1.92" if package == "boost" else None,
    )
    monkeypatch.setattr( pv, "_concrete_from_boost_latest", lambda env: None )
    monkeypatch.setattr( pv, "_concrete_from_registry", lambda *a, **k: None )

    seed, concrete = pv.resolve_publisher_version(
            Env(), package="boost", version="latest"
    )
    assert seed == "latest"
    assert concrete == "1.92"


def test_resolve_publisher_version_boost_latest_fallback( monkeypatch ):
    class Env:
        pass

    monkeypatch.setattr( pv, "_concrete_from_build_with", lambda env, package: None )
    monkeypatch.setattr( pv, "_concrete_from_boost_latest", lambda env: "1.91" )
    monkeypatch.setattr( pv, "_concrete_from_registry", lambda *a, **k: None )

    seed, concrete = pv.resolve_publisher_version(
            Env(), package="boost", version="latest"
    )
    assert seed == "latest"
    assert concrete == "1.91"


def test_resolve_publisher_version_registry_fallback( monkeypatch ):
    class Env:
        pass

    monkeypatch.setattr( pv, "_concrete_from_build_with", lambda env, package: None )
    monkeypatch.setattr( pv, "_concrete_from_boost_latest", lambda env: None )
    monkeypatch.setattr(
            pv,
            "_concrete_from_registry",
            lambda env, registry, package, custom_token=None: "3.1.0",
    )

    seed, concrete = pv.resolve_publisher_version(
            Env(),
            package="widget",
            version="latest",
            registry="https://gitlab.example/api/v4/projects/1",
    )
    assert seed == "latest"
    assert concrete == "3.1.0"


def test_resolve_publisher_version_unresolved_raises( monkeypatch ):
    class Env:
        pass

    monkeypatch.setattr( pv, "_concrete_from_build_with", lambda env, package: None )
    monkeypatch.setattr( pv, "_concrete_from_boost_latest", lambda env: None )
    monkeypatch.setattr( pv, "_concrete_from_registry", lambda *a, **k: None )

    with pytest.raises( SCons.Errors.StopError ):
        pv.resolve_publisher_version( Env(), package="widget", version="latest" )
