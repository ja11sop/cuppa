#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for PublishPackage source wiring."""

from types import SimpleNamespace

import pytest

from cuppa.methods.manage_packages import PublishPackageMethod, publish_package_sources


pytestmark = pytest.mark.unit


def test_publish_package_sources_includes_archive():
    publisher = SimpleNamespace( package_archive=lambda: "final/widget.tar.gz" )
    sources = publish_package_sources( publisher, ["working/widget.packaged"] )
    assert sources == ["working/widget.packaged", "final/widget.tar.gz"]


def test_publish_package_sources_without_archive_attr():
    publisher = SimpleNamespace()
    sources = publish_package_sources( publisher, ["working/widget.packaged"] )
    assert sources == ["working/widget.packaged"]


def test_publish_package_sources_uses_env_file():
    class _Env:
        def File( self, path ):
            return "FILE:{}".format( path )

    publisher = SimpleNamespace( package_archive=lambda: "final/widget.tar.gz" )
    sources = publish_package_sources(
            publisher, ["working/widget.packaged"], env=_Env()
    )
    assert sources == ["working/widget.packaged", "FILE:final/widget.tar.gz"]


def test_publish_package_method_passes_archive_to_publish_command( monkeypatch ):
    recorded = []

    class _Env( dict ):
        def File( self, path ):
            return path

        def Command( self, target, source, action ):
            recorded.append( ( target, list( source ), action ) )
            return target

        def get_option( self, name ):
            return name == "publish-package"

        def Clean( self, *_args, **_kwargs ):
            return None

    monkeypatch.setattr(
            "cuppa.progress.NotifyProgress.add",
            staticmethod( lambda env, target: None ),
    )

    publisher = SimpleNamespace(
            package=lambda: "working/widget.packaged",
            package_published=lambda: "working/widget.published",
            package_archive=lambda: "final/widget.tar.gz",
            sources=lambda: [],
            build_package="build",
            publish_package="publish",
            clean_targets=lambda: [],
    )
    env = _Env()
    env["clean"] = False
    PublishPackageMethod()( env, "libwidget.a", publisher=publisher )

    assert len( recorded ) == 2
    _target, publish_sources, action = recorded[1]
    assert action == "publish"
    assert "working/widget.packaged" in publish_sources
    assert "final/widget.tar.gz" in publish_sources


def test_publish_package_method_amend_uses_amend_package( monkeypatch ):
    recorded = []

    class _Env( dict ):
        def File( self, path ):
            return path

        def Command( self, target, source, action ):
            recorded.append( ( target, list( source ) if source else [], action ) )
            return target

        def get_option( self, name ):
            return name in ( "publish-package", "amend-package-manifest" )

        def Clean( self, *_args, **_kwargs ):
            return None

    monkeypatch.setattr(
            "cuppa.progress.NotifyProgress.add",
            staticmethod( lambda env, target: None ),
    )

    publisher = SimpleNamespace(
            package=lambda: "working/widget.packaged",
            package_published=lambda: "working/widget.published",
            package_archive=lambda: "final/widget.tar.gz",
            sources=lambda: [ "libwidget.a" ],
            build_package="build",
            amend_package=lambda *a, **k: "amend",
            publish_package="publish",
            clean_targets=lambda: [],
    )
    env = _Env()
    env["clean"] = False
    PublishPackageMethod()( env, "libwidget.a", publisher=publisher )

    assert callable( recorded[0][2] )
    assert recorded[0][1] == []
    assert recorded[1][2] == "publish"


def test_publish_package_method_amend_rejects_conan_style( monkeypatch ):
    import SCons.Errors

    class _Env( dict ):
        def File( self, path ):
            return path

        def Command( self, target, source, action ):
            return target

        def get_option( self, name ):
            return name == "amend-package-manifest"

        def Clean( self, *_args, **_kwargs ):
            return None

    monkeypatch.setattr(
            "cuppa.progress.NotifyProgress.add",
            staticmethod( lambda env, target: None ),
    )

    publisher = SimpleNamespace(
            package=lambda: "working/widget.packaged",
            sources=lambda: [],
            build_package="build",
            clean_targets=lambda: [],
    )
    env = _Env()
    env["clean"] = False
    with pytest.raises( SCons.Errors.StopError ):
        PublishPackageMethod()( env, "libwidget.a", publisher=publisher )
