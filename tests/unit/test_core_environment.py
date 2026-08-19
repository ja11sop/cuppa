#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from types import SimpleNamespace

import pytest

import SCons.Script

from cuppa.core.environment import CuppaEnvironment


pytestmark = pytest.mark.unit


def test_get_option_cli_overrides_defaults(reset_cuppa_environment, monkeypatch):
    CuppaEnvironment = reset_cuppa_environment
    CuppaEnvironment._options["default_options"] = {"jobs": 2}
    CuppaEnvironment._options["configured_options"] = {"jobs": 8}

    monkeypatch.setattr(SCons.Script, "GetOption", lambda option: 4 if option == "jobs" else None)
    assert CuppaEnvironment.get_option("jobs") == 4


def test_get_option_default_options_before_default_arg(reset_cuppa_environment, monkeypatch):
    CuppaEnvironment = reset_cuppa_environment
    CuppaEnvironment._options["default_options"] = {"verbosity": "info"}
    CuppaEnvironment._options["configured_options"] = {}

    monkeypatch.setattr(SCons.Script, "GetOption", lambda option: None)
    assert CuppaEnvironment.get_option("verbosity", default="quiet") == "info"


def test_get_option_falls_back_to_default_arg(reset_cuppa_environment, monkeypatch):
    CuppaEnvironment = reset_cuppa_environment
    CuppaEnvironment._options["default_options"] = {}
    CuppaEnvironment._options["configured_options"] = {}

    monkeypatch.setattr(SCons.Script, "GetOption", lambda option: None)
    assert CuppaEnvironment.get_option("missing", default="fallback") == "fallback"


def test_get_option_without_configured_options_key(reset_cuppa_environment, monkeypatch):
    """Early construct bootstrap may call get_option before configured_options exists."""
    CuppaEnvironment = reset_cuppa_environment
    CuppaEnvironment._options["default_options"] = {}

    monkeypatch.setattr(
        SCons.Script,
        "GetOption",
        lambda option: "exception" if option == "verbosity" else None,
    )
    assert CuppaEnvironment.get_option("verbosity") == "exception"


def test_get_option_configured_source_still_returns_cli_value(reset_cuppa_environment, monkeypatch):
    """configured_options only annotates source; CLI / defaults still supply the value."""
    CuppaEnvironment = reset_cuppa_environment
    CuppaEnvironment._options["default_options"] = {"dbg": True}
    CuppaEnvironment._options["configured_options"] = {"dbg": True}

    monkeypatch.setattr(SCons.Script, "GetOption", lambda option: None)
    assert CuppaEnvironment.get_option("dbg") is True


def test_registry_helpers_populate_options(reset_cuppa_environment):
    CuppaEnvironment = reset_cuppa_environment
    dep = SimpleNamespace(name="boost")
    profile = SimpleNamespace(name="asan")
    toolchain = SimpleNamespace(name="gcc")

    CuppaEnvironment.add_dependency("boost", dep)
    CuppaEnvironment.add_profile("asan", profile)
    CuppaEnvironment.add_available_toolchain("gcc", toolchain)

    assert CuppaEnvironment._options["dependencies"]["boost"] is dep
    assert CuppaEnvironment._options["profiles"]["asan"] is profile
    assert CuppaEnvironment._options["toolchains"]["gcc"] is toolchain
