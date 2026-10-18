#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Tip-local ``cuppa.add_option`` bookkeeping (no live SCons AddOption)."""

import pytest

from cuppa.core import options as cuppa_options


pytestmark = pytest.mark.unit


def test_tip_local_option_flags_track_takes_value( monkeypatch ):
    cuppa_options.reset_tip_local_options()
    recorded = []

    def _fake_add_option( *args, **kwargs ):
        recorded.append( ( args, kwargs ) )

    monkeypatch.setattr( cuppa_options.SCons.Script, "AddOption", _fake_add_option )

    cuppa_options.add_tip_option(
            "--test-postgres-container",
            dest="test_postgres_container",
            action="store_true",
            help="tip helper",
    )
    cuppa_options.add_tip_option(
            "--pipeline-slot",
            dest="pipeline_slot",
            type="string",
            nargs=1,
            action="store",
            help="tip value",
    )
    # Cuppa-owned path must not pollute tip-local set.
    cuppa_options.add_option(
            "--offline",
            dest="offline",
            action="store_true",
            help="cuppa owned",
    )

    assert "--test-postgres-container" in cuppa_options.tip_local_option_flags()
    assert "--pipeline-slot" in cuppa_options.tip_local_option_flags()
    assert "--offline" not in cuppa_options.tip_local_option_flags()
    assert "--pipeline-slot" in cuppa_options.tip_local_option_takes_value()
    assert "--test-postgres-container" not in cuppa_options.tip_local_option_takes_value()
    assert len( recorded ) == 3
    cuppa_options.reset_tip_local_options()
