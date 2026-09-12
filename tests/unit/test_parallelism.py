#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.utility.parallelism import effective_cpu_count


pytestmark = pytest.mark.unit


def test_effective_cpu_count_prefers_sched_getaffinity( monkeypatch ):
    monkeypatch.setattr(
            'cuppa.utility.parallelism.os.sched_getaffinity',
            lambda pid: set( range( 14 ) ),
            raising=False,
    )
    assert effective_cpu_count() == 14


def test_effective_cpu_count_falls_back_to_multiprocessing( monkeypatch ):
    def _raise( pid ):
        raise AttributeError( 'no affinity' )

    monkeypatch.setattr(
            'cuppa.utility.parallelism.os.sched_getaffinity',
            _raise,
            raising=False,
    )
    monkeypatch.setattr(
            'cuppa.utility.parallelism.multiprocessing.cpu_count',
            lambda: 8,
    )
    # Force psutil path to fail so we hit multiprocessing.
    import sys
    monkeypatch.setitem( sys.modules, 'psutil', None )
    assert effective_cpu_count() == 8
