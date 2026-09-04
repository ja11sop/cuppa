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
