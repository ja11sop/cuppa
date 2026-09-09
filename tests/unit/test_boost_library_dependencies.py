#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for boost library dependency expansion order."""

import os
import subprocess
import sys

import pytest

from cuppa.dependencies.boost.library_dependencies import (
    add_dependent_libraries,
    boost_dependency_order,
)


pytestmark = pytest.mark.unit


_CONSUMER_STYLE_LIBS = [
    'log',
    'log_setup',
    'program_options',
    'system',
    'unit_test_framework',
]


def _assert_master_subset( result ):
    master = boost_dependency_order()
    positions = [ master.index( name ) for name in result if name in master ]
    assert positions == sorted( positions ), result


def _append_staticlibs( existing, names ):
    """Model boost use_libs: Append the expansion, allowing intentional repeats."""
    existing.extend( names )
    return existing


def _append_unique_staticlibs( existing, names ):
    """Former mistaken use_libs behaviour that dropped needed repeats."""
    for name in names:
        if name not in existing:
            existing.append( name )
    return existing


def test_add_dependent_libraries_emits_master_order_subset():
    """Required libs keep relative order from boost_dependency_order()."""
    result = add_dependent_libraries( 1.92, 'static', list( _CONSUMER_STYLE_LIBS ) )

    assert result == [
        'log_setup',
        'log',
        'date_time',
        'filesystem',
        'unit_test_framework',
        'system',
        'thread',
        'program_options',
    ]
    _assert_master_subset( result )


def test_add_dependent_libraries_test_alias_uses_unit_test_slot():
    """Requesting 'test' remaps to unit_test_framework at the master slot."""
    result = add_dependent_libraries( 1.86, 'static', [ 'filesystem', 'test' ] )

    assert 'test' not in result
    assert 'unit_test_framework' in result
    assert result.index( 'filesystem' ) < result.index( 'unit_test_framework' )
    assert result.index( 'unit_test_framework' ) < result.index( 'system' )
    _assert_master_subset( result )


def test_add_dependent_libraries_patched_test_keeps_timer_after_framework():
    result = add_dependent_libraries(
        1.86, 'static', [ 'unit_test_framework' ], patched_test=True
    )

    assert result.index( 'unit_test_framework' ) < result.index( 'timer' )
    assert result.index( 'timer' ) < result.index( 'chrono' )
    assert result.index( 'chrono' ) < result.index( 'system' )


def test_add_dependent_libraries_unknown_names_sorted_after_master():
    result = add_dependent_libraries(
        1.92, 'static', [ 'system', 'zz_unknown', 'aa_unknown' ]
    )

    assert result[-2:] == [ 'aa_unknown', 'zz_unknown' ]
    assert result.index( 'system' ) < result.index( 'aa_unknown' )


def test_add_dependent_libraries_order_stable_across_hash_seeds():
    """Same required set must yield the same link order under any PYTHONHASHSEED."""
    code = (
        'from cuppa.dependencies.boost.library_dependencies import '
        'add_dependent_libraries; '
        'print(add_dependent_libraries(1.92, "static", '
        + repr( _CONSUMER_STYLE_LIBS )
        + '))'
    )
    orders = set()
    env_base = dict( os.environ )
    env_base['PYTHONPATH'] = os.pathsep.join(
        [ os.getcwd() ] + env_base.get( 'PYTHONPATH', '' ).split( os.pathsep )
    )
    for seed in ( '0', '1', '2', '42', '99', '12345', 'random' ):
        env = dict( env_base )
        env['PYTHONHASHSEED'] = seed
        out = subprocess.check_output(
            [ sys.executable, '-c', code ],
            env=env,
            text=True,
        ).strip()
        orders.add( out )

    assert len( orders ) == 1, orders


def test_log_dependents_reappear_after_earlier_filesystem_thread_use_libs():
    """Quince-style early use_libs then consumer log must repeat thread after log.

    GNU ld needs filesystem/thread after libboost_log.a even when those archives
    already appear earlier on the line. use_libs must Append expansions; Unique
    would drop the repeats and leave undefined TSS symbols from Boost.Log.
    """
    quince_libs = add_dependent_libraries(
        1.92, 'static', [ 'filesystem', 'thread', 'system' ]
    )
    postgresql_libs = add_dependent_libraries( 1.92, 'static', [ 'date_time' ] )
    consumer_libs = add_dependent_libraries( 1.92, 'static', list( _CONSUMER_STYLE_LIBS ) )

    with_append = []
    _append_staticlibs( with_append, quince_libs )
    _append_staticlibs( with_append, postgresql_libs )
    _append_staticlibs( with_append, consumer_libs )

    assert with_append.count( 'filesystem' ) >= 2
    assert with_append.count( 'thread' ) >= 2
    assert with_append.count( 'date_time' ) >= 2
    log_index = with_append.index( 'log' )
    assert 'filesystem' in with_append[ log_index + 1 : ]
    assert 'thread' in with_append[ log_index + 1 : ]
    assert 'date_time' in with_append[ log_index + 1 : ]

    with_unique = []
    _append_unique_staticlibs( with_unique, quince_libs )
    _append_unique_staticlibs( with_unique, postgresql_libs )
    _append_unique_staticlibs( with_unique, consumer_libs )
    unique_log_index = with_unique.index( 'log' )
    assert 'thread' not in with_unique[ unique_log_index + 1 : ]
