
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Library Dependencies
#-------------------------------------------------------------------------------

from cuppa.colourise import colour_items
from cuppa.log       import logger



def boost_dependency_order():
    return [
        'graph',
        'regex',
        'coroutine',
        'context',
        'log_setup',
        'log',
        'date_time',
        'locale',
        'filesystem',
        'test',
        'timer',
        'chrono',
        'system',
        'thread'
    ]


def boost_dependency_set():
    return set( boost_dependency_order() )


def boost_libraries_with_no_dependencies():
    return set( [
        'context',
        'date_time',
        'exception',
        'graph_parallel',
        'iostreams',
        'math',
        'mpi',
        'program_options',
        'python',
        'random',
        'regex',
        'serialization',
        'signals',
        'system',
        'thread',
        'wave'
    ] )


def add_dependent_libraries( version, linktype, libraries, patched_test=False ):
    required_libraries = set( libraries )

    logger.trace( "Required Library Set = [{}]".format( colour_items( [l for l in required_libraries] ) ) )

    for library in libraries:
        if library in boost_libraries_with_no_dependencies():
            continue
        elif library == 'chrono':
            required_libraries.update( ['system'] )
        elif library == 'coroutine':
            required_libraries.update( ['context', 'system'] )
            if version > 1.55:
                required_libraries.update( ['thread'] )
            if linktype == 'shared':
                required_libraries.update( ['chrono'] )
        elif library == 'filesystem':
            required_libraries.update( ['system'] )
        elif library == 'graph':
            required_libraries.update( ['regex'] )
        elif library == 'locale':
            required_libraries.update( ['filesystem', 'system', 'thread'] )
        elif library == 'log':
            required_libraries.update( ['date_time', 'filesystem', 'system', 'thread'] )
        elif library == 'log_setup':
            required_libraries.update( ['log', 'date_time', 'filesystem', 'system', 'thread'] )
        elif library in { 'test', 'prg_exec_monitor', 'test_exec_monitor', 'unit_test_framework' }:
            if library == 'test' and 'test' in required_libraries:
                required_libraries.remove( 'test' )
                required_libraries.update( ['unit_test_framework'] )
            if patched_test:
                required_libraries.update( ['timer', 'chrono', 'system'] )
        elif library == 'timer':
            required_libraries.update( ['chrono', 'system'] )

    libraries = []

    for library in boost_dependency_order():
        if library in required_libraries:
            libraries.append( library )

    for library in required_libraries:
        if library not in boost_dependency_set():
            libraries.append( library )

    return libraries
