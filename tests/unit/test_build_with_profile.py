#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.build_with_profile import profile


pytestmark = pytest.mark.unit


def test_profile_factory_shape_and_add_to_env():
    Prof = profile("asan")
    assert Prof._name == "asan"
    assert Prof.name() == "asan"
    assert Prof.__name__ == "BuildProfileAsan"

    instance = Prof.create(None)
    assert isinstance(instance, Prof)

    recorded = {}

    def add_profile(name, factory):
        recorded[name] = factory

    Prof.add_to_env(None, add_profile)
    assert recorded["asan"].__func__ is Prof.create.__func__
