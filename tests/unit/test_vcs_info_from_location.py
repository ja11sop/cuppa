#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.test_report import html_report


pytestmark = pytest.mark.unit


def test_vcs_info_from_location_without_vcs(tmp_path, monkeypatch):
    html_report.cached_vcs_info.clear()
    monkeypatch.setattr(
        "cuppa.location.Location.detect_vcs_info",
        classmethod(lambda cls, location, expected_vc_type=None: None),
    )
    url, repository, branch, remote, revision = html_report.vcs_info_from_location(
        str(tmp_path), "main", "abc123"
    )
    assert url is None
    assert repository is None
    assert branch == "main"
    assert remote is None
    assert revision == "abc123"
