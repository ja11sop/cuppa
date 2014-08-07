
#          Copyright Jamie Allsop 2014-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Darwin Platform
#-------------------------------------------------------------------------------

from subprocess import Popen, PIPE
import re
import platform


class DarwinException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Darwin:

    @classmethod
    def add_to_env( cls, args ):
        args['env']['platforms']['Darwin'] = cls()


    def __init__( self ):
        self.values = {}


    def default_toolchain( self ):
        return self.__default_toolchain


    def __getitem__( self, key ):
        return self.values.get( key )


    def initialise( self, toolchains ):

        ( system, node, release, version, machine, processor ) = platform.uname()

        self.values['os']              = system
        self.values['architecture']    = machine

        if machine == "i386":
            self.values['bit_width']   = '32'
        elif machine == "i686":
            self.values['bit_width']   = '32'
        elif machine == "x86_64":
            self.values['bit_width']   = '64'
        else:
            self.values['bit_width']   = 'unknown'

        self.values['os_version']      = release

        self.values['platform_path']   = self.values['architecture'] + '_' + self.values['os'] + '_' + self.values['os_version']

        toolchain_version = Popen(["clang", "--version"], stdout=PIPE).communicate()[0]

        self.values['toolchain_name'] = 'clang' + re.search( r'(\d)\.(\d)\.(\d)', toolchain_version ).expand(r'\1\2\3')
        self.values['toolchain_tag']  = 'clang' + re.search( r'(\d)\.(\d)\.(\d)', toolchain_version ).expand(r'\1\2')

        default_toolchain = self.values['toolchain_tag']

        if default_toolchain not in toolchains:
            raise DarwinException( 'Toolchain [' + default_toolchain + '] not supported. Supported toolchains are ' + str(toolchains.keys()) )

        self.__default_toolchain = toolchains[ default_toolchain ]



    class Constants(object):

        CLOCK_REALTIME              = 0 # System-wide realtime clock.
        CLOCK_MONOTONIC             = 1 # Monotonic system-wide clock.
        CLOCK_PROCESS_CPUTIME_ID    = 2 # High-resolution timer from the CPU.
        CLOCK_THREAD_CPUTIME_ID     = 3 # Thread-specific CPU-time clock.
        CLOCK_MONOTONIC_RAW         = 4 # Monotonic system-wide clock, not adjusted for frequency scaling.
        CLOCK_REALTIME_COARSE       = 5 # System-wide realtime clock, updated only on ticks.
        CLOCK_MONOTONIC_COARSE      = 6 # Monotonic system-wide clock, updated only on ticks.
        CLOCK_BOOTTIME              = 7 # Monotonic system-wide clock that includes time spent in suspension.


    @classmethod
    def constants( cls ):
        return cls.Constants

    @classmethod
    def name( cls ):
        return cls.__name__

    def print_values( self ):

        print 'os             = ' + self.values['os']
        print 'architecture   = ' + self.values['architecture']
        print 'bit_width      = ' + self.values['bit_width']
        print 'os_version     = ' + self.values['os_version']
        print 'platform_path  = ' + self.values['platform_path']
        print 'toolchain_name = ' + self.values['toolchain_name']
        print 'toolchain_tag  = ' + self.values['toolchain_tag']

