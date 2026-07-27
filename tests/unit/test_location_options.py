#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.core import location_options
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_process_location_options_copies_flags():
    env = FakeEnv(
        {
            "develop": True,
            "location_default_branch": "main",
            "location_match_current_branch": True,
            "location_explicit_default_branch": False,
            "location_match_branch": "feature",
            "location_match_tag": "v1.0",
        }
    )
    location_options.process_location_options(env)
    assert env["develop"] is True
    assert env["location_default_branch"] == "main"
    assert env["location_match_current_branch"] is True
    assert env["location_explicit_default_branch"] is False
    assert env["location_match_branch"] == "feature"
    assert env["location_match_tag"] == "v1.0"
