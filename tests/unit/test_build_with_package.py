#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest
import SCons.Errors

from cuppa.build_with_package import package_dependency
from cuppa.package_managers.gitlab import GitlabPackageDependency
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_package_dependency_requires_registry():
    with pytest.raises(SCons.Errors.StopError):
        package_dependency("widget", package_manager="gitlab")


def test_package_info_none_without_manager():
    Dep = package_dependency(
        "widget", package_manager="gitlab", registry="https://gitlab.example/api/v4"
    )
    Dep._package_manager = None
    env = FakeEnv()
    assert Dep.package_info(env) is None


def test_package_info_identity_and_default_variant(reset_location_caches):
    Dep = package_dependency(
        "widget",
        package_manager="gitlab",
        registry="https://gitlab.example/api/v4",
        package="widget",
        version="1.2.3",
    )
    env = FakeEnv(develop=False)
    info = Dep.package_info(env)
    assert info["manager"] == "gitlab"
    assert info["package"]["id"][0] == "https://gitlab.example/api/v4"
    assert info["package"]["id"][1] == "widget"
    assert info["package"]["id"][2] == "1.2.3"
    assert info["package"]["id"][3] == "rel"
    assert info["package"]["id"][4] is False
    # No toolchain on FakeEnv → tool_variant segment is None.
    assert info["package"]["id"][5] is None
    assert info["package"]["args"]["variant"] == "rel"


def test_package_id_default_variant_via_gitlab_helper():
    pkg = type("Pkg", (), {"_registry": "r", "_package": "p", "_version": "1", "_variant": None})()
    pkg.default_version = lambda version, env: None
    env = FakeEnv(develop=True)
    result = GitlabPackageDependency.package_id(pkg, env)
    assert result["id"][3] == "rel"
    assert result["id"][4] is True
    assert result["id"][5] is None


class _FakeToolchain:
    def __init__(self, name):
        self._name = name

    def package_name(self):
        return self._name


class _FakeVariant:
    def name(self):
        return "dbg"


def test_package_id_includes_tool_variant_per_toolchain():
    pkg = type("Pkg", (), {
        "_registry": "r",
        "_package": "boost",
        "_version": "1.91",
        "_variant": "rel",
    })()
    pkg.default_version = lambda version, env: None

    def make_env(toolchain_name):
        return FakeEnv(
            develop=False,
            toolchain=_FakeToolchain(toolchain_name),
            variant=_FakeVariant(),
            target_arch="x86_64",
            abi="cxx2c",
        )

    gcc_id = GitlabPackageDependency.package_id(pkg, make_env("gcc153"))["id"]
    clang_id = GitlabPackageDependency.package_id(pkg, make_env("clang211"))["id"]
    assert gcc_id[5] == "gcc153_rel_x86_64_cxx2c"
    assert clang_id[5] == "clang211_rel_x86_64_cxx2c"
    assert gcc_id != clang_id
