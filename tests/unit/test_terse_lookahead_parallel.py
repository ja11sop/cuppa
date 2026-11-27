#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Terse up-to-date lookahead skips ``is_up_to_date`` under ``num_jobs > 1``."""

import pytest

from cuppa import progress


pytestmark = pytest.mark.unit


def test_terse_lookahead_skipped_when_num_jobs_gt_1( monkeypatch ):
    called = []

    class _Ledger:
        def credit_currently_up_to_date( self ):
            called.append( True )

    monkeypatch.setattr( progress, "_progress_ledger", _Ledger() )
    monkeypatch.delenv( "CUPPA_TERSE_BISECT", raising=False )

    import SCons.Script
    monkeypatch.setattr( SCons.Script, "GetOption", lambda name: 2 if name == "num_jobs" else None )

    progress.credit_terse_up_to_date_lookahead()
    assert called == []


def test_terse_lookahead_runs_when_num_jobs_is_1( monkeypatch ):
    called = []

    class _Ledger:
        def credit_currently_up_to_date( self ):
            called.append( True )

    monkeypatch.setattr( progress, "_progress_ledger", _Ledger() )
    monkeypatch.delenv( "CUPPA_TERSE_BISECT", raising=False )

    import SCons.Script
    monkeypatch.setattr( SCons.Script, "GetOption", lambda name: 1 if name == "num_jobs" else None )

    progress.credit_terse_up_to_date_lookahead()
    assert called == [ True ]
