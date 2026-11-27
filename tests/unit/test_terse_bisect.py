#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""``CUPPA_TERSE_BISECT`` disables named terse subsystems for soak probes."""

import pytest

from cuppa import progress


pytestmark = pytest.mark.unit


def test_terse_bisect_disabled_tokens( monkeypatch ):
    monkeypatch.delenv( "CUPPA_TERSE_BISECT", raising=False )
    assert progress._terse_bisect_disabled( "hooks" ) is False

    monkeypatch.setenv( "CUPPA_TERSE_BISECT", "hooks, lookahead" )
    assert progress._terse_bisect_disabled( "hooks" ) is True
    assert progress._terse_bisect_disabled( "lookahead" ) is True
    assert progress._terse_bisect_disabled( "outstanding" ) is False
