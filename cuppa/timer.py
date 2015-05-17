
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
import sys


nanosecs_multiple = 1000000000


def wall_time_nanosecs():
    return int( timeit.default_timer()*nanosecs_multiple )


def process_times_nanosecs():
    process = time.clock()
    user, system, children_user, children_system, real = os.times()
    return int( process*nanosecs_multiple), int( user*nanosecs_multiple ), int( system*nanosecs_multiple )


class CpuTimes(object):

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


class Timer(object):

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


class no_colourising(object):

    def emphasise( self, text ):
        return text

    def emphasise_time_by_digit( self, text ):
        return text

    def colour( self, text ):
        return text


def as_duration_string( total_nanosecs ):
    secs, remainder      = divmod( total_nanosecs, 1000000000 )
    millisecs, remainder = divmod( remainder, 1000000 )
    microsecs, nanosecs  = divmod( remainder, 1000 )
    hours, remainder     = divmod( secs, 3600 )
    minutes, secs        = divmod( remainder, 60 )

    duration = "%02d:%02d:%02d.%03d,%03d,%03d" % ( hours, minutes, secs, millisecs, microsecs, nanosecs )
    return duration


def as_wall_cpu_percent_string( cpu_times ):
    wall_cpu_percent = "n/a"

    if cpu_times.wall:
        percent = "{:.2f}".format( float(cpu_times.process) * 100 / cpu_times.wall )
        wall_cpu_percent = "%6s%%" % percent.upper()

    return wall_cpu_percent


def write_time( cpu_times, colouriser=no_colourising(), emphasise=False ):

    def write( text ):
        if not emphasise:
            sys.stdout.write( text )
        else:
            sys.stdout.write( colouriser.emphasise( text ) )

    write( " Time:" )
    write( " Wall [ {}".format( colouriser.emphasise_time_by_digit( as_duration_string( cpu_times.wall ) ) ) )
    write( " ] CPU [ {}".format( colouriser.emphasise_time_by_digit( as_duration_string( cpu_times.process ) ) ) )
    write( " ] CPU/Wall [ {}".format( colouriser.colour( 'time', as_wall_cpu_percent_string( cpu_times ) ) ) )
    write( " ]" )
