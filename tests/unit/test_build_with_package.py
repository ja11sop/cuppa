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
    assert info["package"]["args"]["variant"] == "rel"


def test_package_id_default_variant_via_gitlab_helper():
    pkg = type("Pkg", (), {"_registry": "r", "_package": "p", "_version": "1", "_variant": None})()
    pkg.default_version = lambda version, env: None
    env = FakeEnv(develop=True)
    result = GitlabPackageDependency.package_id(pkg, env)
    assert result["id"][3] == "rel"
    assert result["id"][4] is True
