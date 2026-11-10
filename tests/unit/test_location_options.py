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
            "list_develop": True,
            "update_develop": False,
            "skip-location-update": True,
            "location_default_branch": "main",
            "location_base_branch": "integration",
            "location_match_current_branch": True,
            "location_explicit_default_branch": False,
            "location_match_branch": "feature",
            "location_match_tag": "v1.0",
        }
    )
    location_options.process_location_options(env)
    assert env["develop"] is True
    assert env["list_develop"] is True
    assert env["update_develop"] is False
    assert env["skip_location_update"] is True
    assert env["location_default_branch"] == "main"
    assert env["location_base_branch"] == "integration"
    assert env["location_match_current_branch"] is True
    assert env["location_explicit_default_branch"] is False
    assert env["location_match_branch"] == "feature"
    assert env["location_match_tag"] == "v1.0"


def test_process_location_options_refuses_skip_with_update_develop( capsys ):
    import re
    import SCons.Errors

    env = FakeEnv(
        {
            "skip-location-update": True,
            "update_develop": True,
            "clone_develop": False,
            "checkout_develop_branch": None,
            "reset_develop_branch": None,
        }
    )
    with pytest.raises(
            SCons.Errors.StopError,
            match=r"Invalid option combination \(--skip-location-update and --update-develop\)",
    ):
        location_options.process_location_options( env )
    visible = re.sub( r"\x1b\[[0-9;]*m", "", capsys.readouterr().out )
    assert "Options Error" in visible
    assert "--skip-location-update cannot be combined with --update-develop" in visible


def test_process_location_options_refuses_stage_develop_without_develop( capsys ):
    import re
    import SCons.Errors

    env = FakeEnv(
        {
            "develop": False,
            "stage-develop": True,
            "stage-develop-plan": False,
        }
    )
    with pytest.raises(
            SCons.Errors.StopError,
            match=r"Invalid option combination \(--stage-develop without --develop\)",
    ):
        location_options.process_location_options( env )
    visible = re.sub( r"\x1b\[[0-9;]*m", "", capsys.readouterr().out )
    assert "Options Error" in visible
    assert "Pass --develop --stage-develop" in visible
