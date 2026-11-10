#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import re

import pytest
import SCons.Errors

from cuppa.colourise import as_emphasised, as_error, as_info, colouriser
from cuppa.utility.console_errors import raise_options_error, remedy_colour


pytestmark = pytest.mark.unit


def _plain( text ):
    return re.sub( r"\x1b\[[0-9;]*m", "", text )


def test_raise_options_error_prints_tree_then_short_stop( capsys ):
    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--stage-package and --publish-package\)",
        ):
            raise_options_error(
                    "--stage-package and --publish-package cannot be combined",
                    [
                            (
                                    "--stage-package builds without uploading; "
                                    "--publish-package uploads",
                                    as_error,
                            ),
                            (
                                    "Choose one: --stage-package or --publish-package",
                                    remedy_colour,
                            ),
                    ],
                    "Invalid option combination "
                    "(--stage-package and --publish-package)",
            )
    finally:
        colouriser.use_colour = was

    out = capsys.readouterr().out
    visible = _plain( out )
    assert "Options Error" in visible
    assert "--stage-package and --publish-package cannot be combined" in visible
    assert "Choose one" in visible
    assert as_emphasised( as_info( "--stage-package" ) ) in out
    assert out.endswith( "\n\n" ) or "\n\n" in out


def test_publish_package_check_options_refuses_stage_and_publish( capsys ):
    from cuppa.methods.manage_packages import PublishPackageMethod

    class _Env:
        def get_option( self, name, default=None ):
            return name in ( "publish-package", "stage-package" )

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--stage-package and --publish-package\)",
        ):
            PublishPackageMethod.check_options( _Env() )
    finally:
        colouriser.use_colour = was

    visible = _plain( capsys.readouterr().out )
    assert "Options Error" in visible
    assert "--stage-package and --publish-package cannot be combined" in visible


def test_publish_package_check_options_allows_stage_alone():
    from cuppa.methods.manage_packages import PublishPackageMethod

    class _Env:
        def get_option( self, name, default=None ):
            return name == "stage-package"

        def get( self, name, default=None ):
            return default

    PublishPackageMethod.check_options( _Env() )


def test_publish_package_check_options_refuses_cascade_without_companion( capsys ):
    from cuppa.methods.manage_packages import PublishPackageMethod

    class _Env:
        def get_option( self, name, default=None ):
            return name == "cascade"

        def get( self, name, default=None ):
            return default

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--cascade without a companion\)",
        ):
            PublishPackageMethod.check_options( _Env() )
    finally:
        colouriser.use_colour = was

    visible = _plain( capsys.readouterr().out )
    assert "Options Error" in visible
    assert "--cascade requires a companion flag" in visible
    assert "--publish-package" in visible


def test_publish_package_check_options_refuses_publish_cascade_deps_with_publish(
        capsys,
):
    from cuppa.methods.manage_packages import PublishPackageMethod

    class _Env:
        def get_option( self, name, default=None ):
            return name in (
                    "cascade",
                    "publish-cascade-dependencies",
                    "publish-package",
            )

        def get( self, name, default=None ):
            return default

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--publish-cascade-dependencies and --publish-package\)",
        ):
            PublishPackageMethod.check_options( _Env() )
    finally:
        colouriser.use_colour = was

    visible = _plain( capsys.readouterr().out )
    assert "Options Error" in visible
    assert "cannot be combined" in visible


def test_check_cascade_options_refuses_plan_without_cascade( capsys ):
    from cuppa.package_managers import package_cascade

    class _Env:
        def get_option( self, name, default=None ):
            return name == "cascade-plan"

        def get( self, name, default=None ):
            return default

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--cascade-plan without --cascade\)",
        ):
            package_cascade.check_cascade_options( _Env() )
    finally:
        colouriser.use_colour = was

    visible = _plain( capsys.readouterr().out )
    assert "Options Error" in visible
    assert "--cascade-plan requires --cascade" in visible
    assert "Pass --cascade --cascade-plan" in visible


def test_base_options_check_options_refuses_parallel_n_with_jobs( capsys ):
    from cuppa.core import base_options

    class _Env:
        def get_option( self, name, default=None ):
            if name == "parallel":
                return "4"
            if name == "num_jobs":
                return 8
            return default

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--parallel=4 and --jobs=8 / -j\)",
        ):
            base_options.check_options( _Env() )
    finally:
        colouriser.use_colour = was

    visible = _plain( capsys.readouterr().out )
    assert "Options Error" in visible
    assert "--parallel=4 cannot be combined with --jobs / -j" in visible


def test_base_options_check_options_allows_parallel_alone():
    from cuppa.core import base_options

    class _Env:
        def get_option( self, name, default=None ):
            if name == "parallel":
                return "4"
            if name == "num_jobs":
                return 1
            return default

    base_options.check_options( _Env() )


def test_registration_check_options_discovers_publish_package( capsys ):
    from cuppa.modules import registration

    class _Env:
        def get_option( self, name, default=None ):
            return name in ( "publish-package", "stage-package" )

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--stage-package and --publish-package\)",
        ):
            registration.check_options( "methods", _Env() )
    finally:
        colouriser.use_colour = was

    visible = _plain( capsys.readouterr().out )
    assert "Options Error" in visible


def test_publish_package_method_stage_and_publish_is_options_error(
        monkeypatch, capsys,
):
    from types import SimpleNamespace
    from cuppa.methods.manage_packages import PublishPackageMethod

    class _Env( dict ):
        def File( self, path ):
            return path

        def Command( self, target, source, action ):
            return target

        def SideEffect( self, *_args, **_kwargs ):
            return None

        def get_option( self, name ):
            return name in ( "publish-package", "stage-package" )

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

    was = colouriser.use_colour
    colouriser.enable()
    try:
        with pytest.raises(
                SCons.Errors.StopError,
                match=r"Invalid option combination \(--stage-package and --publish-package\)",
        ):
            PublishPackageMethod()( env, "libwidget.a", publisher=publisher )
    finally:
        colouriser.use_colour = was

    visible = _plain( capsys.readouterr().out )
    assert "Options Error" in visible
    assert "--stage-package and --publish-package cannot be combined" in visible
