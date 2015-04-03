
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Timer
#-------------------------------------------------------------------------------

# Python Standard Library Imports
import os
import timeit
import time


nanosecs_multiple = 1000000000


def wall_time_nanosecs():
    return int( timeit.default_timer()*nanosecs_multiple )


def process_times_nanosecs():
    process = time.clock()
    user, system, children_user, children_system, real = os.times()
    return int( process*nanosecs_multiple), int( user*nanosecs_multiple ), int( system*nanosecs_multiple )


class CpuTimes:

    def __init__( self, wall, process, system, user ):
        self.wall    = wall
        self.process = process
        self.system  = system
        self.user    = user


    def __add__( self, other ):
        if isinstance( other, self.__class__ ):
            return CpuTimes(
                self.wall    + other.wall,
                self.process + other.process,
                self.system  + other.system,
                self.user    + other.user
            )
        else:
            raise TypeError("Unsupported operand type(s) for +: '{}' and '{}'").format(self.__class__, type(other))


    def __sub__( self, other ):
        if isinstance( other, self.__class__ ):
            return CpuTimes(
                self.wall    - other.wall,
                self.process - other.process,
                self.system  - other.system,
                self.user    - other.user
            )
        else:
            raise TypeError("Unsupported operand type(s) for -: '{}' and '{}'").format(self.__class__, type(other))


class Timer:

    @classmethod
    def _current_time( cls ):
        wall = wall_time_nanosecs()
        process, user, system = process_times_nanosecs()
        return CpuTimes( wall, process, system, user )


    @classmethod
    def _elapsed_time( cls, current, start ):
        return current - start


    def __init__( self ):
        self.start()


    def elapsed( self ):
        if not self._stopped:
            self._current = self._current_time()
        return self._elapsed_time( self._current, self._start )


    def start( self ):
        self._stopped = False
        self._start = self._current_time()


    def stop( self ):
        self._stopped = True
        self._current = self._current_time()


    def resume( self ):
        self.start()
