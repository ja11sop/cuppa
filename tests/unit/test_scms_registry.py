#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.scms import git, subversion
from cuppa.scms.scms import get_scms


pytestmark = pytest.mark.unit


def test_get_scms_known_and_unknown():
    assert get_scms("git") is git.Git
    assert get_scms("svn") is subversion.Subversion
    assert get_scms("unknown") is None
