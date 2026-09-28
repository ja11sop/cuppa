#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration fixtures: isolate every case from the developer's real home."""

from __future__ import annotations

import pytest

from tests.helpers.home import apply_isolated_home


@pytest.fixture( autouse=True )
def isolate_cuppa_home( tmp_path, monkeypatch ):
    """Point HOME / USERPROFILE at a per-test directory under tmp_path.

    Cuppa defaults storage under ``~/.cuppa``. Without isolation, concurrent
    pytest-xdist workers (and even serial inventory tests) would race or
    observe the developer machine's real trees. Cases that already pass
    ``extra_env=own_home(tmp_path)`` keep working — they use the same path.
    """
    return apply_isolated_home( tmp_path, monkeypatch )
