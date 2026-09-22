#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.packages import boost_package


pytestmark = pytest.mark.unit


def test_boost_package_define_forwards_package_source():
    cls = boost_package.define(
            registry="https://gitlab.example/api/v4/projects/1",
            version="1.92",
            package_source="git@gitlab.example:packages/boost@develop",
    )
    assert cls._package_source == "git@gitlab.example:packages/boost@develop"
    assert cls._package == "boost"
    assert cls._name == "boost_package"


def test_boost_package_define_omits_package_source_by_default():
    cls = boost_package.define(
            registry="https://gitlab.example/api/v4/projects/1",
            version="1.92",
    )
    assert getattr( cls, "_package_source", None ) is None
