#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Mode banners stay visible when quiet suppresses info logs."""

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project


pytestmark = pytest.mark.integration


def _assert_banners_without_info_prefix( result ):
    assert_success( result )
    text = result.stdout
    assert "Running in OFFLINE mode" in text
    assert "Running in LIST BUILDS mode, no building will be attempted" in text
    assert "cuppa: construct: [info]" not in text
    assert "cuppa: storage_actions: [info]" not in text


def test_mode_banners_survive_no_progress( tmp_path ):
    project = copy_dummy_project( tmp_path )
    _assert_banners_without_info_prefix( run_cuppa( project, "-Q", "--list-builds" ) )


def test_mode_banners_survive_silent( tmp_path ):
    project = copy_dummy_project( tmp_path )
    _assert_banners_without_info_prefix( run_cuppa( project, "-s", "--list-builds" ) )
