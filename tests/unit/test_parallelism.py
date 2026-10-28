#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.utility.parallelism import (
        argv_requests_parallel,
        effective_cpu_count,
        parse_parallel_option,
        resolve_parallel_job_count,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
        "args, expected",
        [
            ( [], False ),
            ( [ '--dbg' ], False ),
            ( [ '--parallel' ], True ),
            ( [ '--parallel=12' ], True ),
            ( [ '--toolchains=gcc', '--parallel=4', '-D' ], True ),
            ( [ '--parallelism' ], False ),
        ],
)
def test_argv_requests_parallel( args, expected ):
    assert argv_requests_parallel( args ) is expected


@pytest.mark.parametrize(
        "value, enabled, jobs",
        [
            ( None, False, None ),
            ( False, False, None ),
            ( True, True, None ),
            ( 'auto', True, None ),
            ( '12', True, 12 ),
            ( 8, True, 8 ),
        ],
)
def test_parse_parallel_option_ok( value, enabled, jobs ):
    request = parse_parallel_option( value )
    assert request.enabled is enabled
    assert request.jobs == jobs


@pytest.mark.parametrize( "value", [ '', '0', '-1', 'x', '1.5' ] )
def test_parse_parallel_option_rejects( value ):
    with pytest.raises( ValueError ):
        parse_parallel_option( value )


def test_resolve_parallel_auto_and_combo():
    auto = parse_parallel_option( 'auto' )
    count, mode = resolve_parallel_job_count( auto, 1, effective_cpus=14 )
    assert ( count, mode ) == ( 14, 'automatically' )

    count, mode = resolve_parallel_job_count( auto, 8, effective_cpus=14 )
    assert ( count, mode ) == ( 8, 'manually' )


def test_resolve_parallel_explicit_and_conflict():
    explicit = parse_parallel_option( '12' )
    count, mode = resolve_parallel_job_count( explicit, 1, effective_cpus=14 )
    assert ( count, mode ) == ( 12, 'explicit' )

    with pytest.raises( ValueError, match='do not combine' ):
        resolve_parallel_job_count( explicit, 8, effective_cpus=14 )


def test_resolve_parallel_disabled_keeps_jobs():
    off = parse_parallel_option( None )
    assert resolve_parallel_job_count( off, 1 ) == ( 1, 'manually' )
    assert resolve_parallel_job_count( off, 4 ) == ( 4, 'manually' )


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
