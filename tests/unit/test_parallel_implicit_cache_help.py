#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""``--parallel`` help mentions the terse ``-j`` lookahead fix."""

import pytest

from cuppa.core import options as cuppa_options


pytestmark = pytest.mark.unit


def test_parallel_help_mentions_terse_lookahead_skip( monkeypatch ):
    recorded = {}

    def _fake_add_option( *args, **kwargs ):
        if args and args[0] == "--parallel":
            recorded["help"] = kwargs.get( "help" ) or ""

    monkeypatch.setattr( cuppa_options.SCons.Script, "AddOption", _fake_add_option )

    from cuppa.core import base_options
    base_options.add_base_options()

    help_text = recorded.get( "help", "" )
    assert "is_up_to_date" in help_text
    assert "num_jobs" in help_text
