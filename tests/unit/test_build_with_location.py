#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.build_with_location import location_dependency
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_location_dependency_factory_defaults():
    Dep = location_dependency(
        "headers",
        location="include",
        develop="../headers",
        include=".",
        sys_include="sys",
        extra_sub_path="src",
        source_path="lib",
        linktype="static",
    )
    assert Dep._name == "headers"
    assert Dep._default_location == "include"
    assert Dep._default_develop == "../headers"
    assert Dep._default_include == ["."]
    assert Dep._default_sys_include == ["sys"]
    assert Dep._extra_sub_path == "src"
    assert Dep._source_path == "lib"
    assert Dep._linktype == "static"
    assert Dep.location_option() == "headers-location"
    assert Dep.include_option() == "headers-include"
    assert Dep.develop_option() == "headers-develop"


def test_location_id_precedence_default_location():
    Dep = location_dependency("liba", location="/opt/liba")
    env = FakeEnv(thirdparty=None, branch_root=None)
    assert Dep.location_id(env) == ("/opt/liba", None, None, None)


def test_location_id_explicit_option_overrides_default():
    Dep = location_dependency("liba", location="/opt/liba", develop="/dev/liba")
    env = FakeEnv(
        {
            "liba-location": "/custom/liba",
            "liba-develop": "/custom/dev",
            "liba-branch-path": "branches/x",
            "develop": True,
            "thirdparty": None,
            "branch_root": None,
        }
    )
    assert Dep.location_id(env) == (
        "/custom/liba",
        "/custom/dev",
        "branches/x",
        True,
    )


def test_location_id_falls_back_to_branch_root_then_thirdparty():
    Dep = location_dependency("liba")
    env = FakeEnv(
        {
            "liba-branch-path": "branches/x",
            "branch_root": "/branch",
            "thirdparty": None,
        }
    )
    assert Dep.location_id(env)[0] == "/branch"

    env2 = FakeEnv(branch_root=None, thirdparty="/third")
    assert Dep.location_id(env2)[0] == "/third"

    env3 = FakeEnv(branch_root=None, thirdparty=None)
    assert Dep.location_id(env3) is None


def test_location_id_expands_user(monkeypatch):
    Dep = location_dependency("liba")
    env = FakeEnv({"liba-location": "~/deps/liba", "thirdparty": None, "branch_root": None})
    monkeypatch.setenv("HOME", "/home/tester")
    location_id = Dep.location_id(env)
    assert location_id[0] == os.path.expanduser("~/deps/liba")


def test_abs_path_from(tmp_path):
    Dep = location_dependency("liba")
    local = str(tmp_path / "local")
    base = str(tmp_path)
    assert Dep.abs_path_from("inc", local, base) == os.path.join(local, "inc")
    assert Dep.abs_path_from("/abs/inc", local, base) == "/abs/inc"


def test_cached_locations_reused(reset_location_caches, monkeypatch):
    Dep = location_dependency("cached", location="/opt/cached")
    env = FakeEnv(thirdparty=None, branch_root=None, sconstruct_dir="/proj")

    sentinel = object()
    calls = []

    def fake_location(*args, **kwargs):
        calls.append((args, kwargs))
        return sentinel

    monkeypatch.setattr("cuppa.location.Location", fake_location)

    first = Dep._get_location(env)
    second = Dep._get_location(env)
    assert first is sentinel
    assert second is sentinel
    assert len(calls) == 1
