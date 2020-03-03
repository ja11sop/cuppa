
#          Copyright Jamie Allsop 2011-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Linux Platform
#-------------------------------------------------------------------------------

from subprocess import Popen, PIPE
from re import match, search, MULTILINE
from os import path

import platform
import SCons.Script

from cuppa.log import logger
from cuppa.utility.python2to3 import as_str


class LinuxException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Linux:

    @classmethod
    def add_to_env( cls, args ):
        args['env']['platforms']['Linux'] = cls()


    def __init__( self ):
        self._toolchain = None
        self.values = {}


    def default_toolchain( self ):
        if not self._toolchain:
            env = SCons.Script.Environment()
            self._toolchain = env['CC']
            return self._toolchain
        return self._toolchain


    def __getitem__( self, key ):
        return self.values.get( key )


    def _bit_depth( self, machine ):
        if machine == "i386":
            return '32'
        elif machine == "i686":
            return '32'
        elif machine == "x86_64":
            return '64'
        else:
            return 'unknown'


    def _libc_version( self, machine, system ):

        libc_file = "libc.so.6"
        libc_path = "/lib/" + libc_file

        if not path.exists( libc_path ):
            multiarch_lib_path = '-'.join( [ machine, system.lower(), 'gnu' ] )
            libc_path = "/lib/" + multiarch_lib_path + "/" + libc_file

        try:
            libc_version = Popen([libc_path], stdout=PIPE).communicate()[0]
            return 'libc' + search( r'^GNU C Library [()a-zA-Z ]*([0-9][.0-9]+)', as_str( libc_version ), MULTILINE ).expand(r'\1').replace('.','')
        except:
            logger.warn( "Could not detect the version of libc installed. You might be missing some development libraries!" )
            return None


    def initialise( self ):

        ( system, node, release, version, machine, processor ) = platform.uname()

        self.values['system']        = system
        self.values['node']          = node
        self.values['release']       = release
        self.values['version']       = version
        self.values['machine']       = machine
        self.values['processor']     = processor
        self.values['os']            = system
        self.values['architecture']  = machine
        self.values['os_version']    = match( r'(\d+\.\d+)', release ).group(0)
        self.values['bit_width']     = self._bit_depth( machine )
        self.values['libc_version']  = self._libc_version( machine, system )
        self.values['platform_path'] = self.values['architecture'] + '_' + self.values['os'] + '_' + self.values['os_version']



    class Constants(object):

        CLOCK_REALTIME              = 0 # System-wide realtime clock.
        CLOCK_MONOTONIC	            = 1 # Monotonic system-wide clock.
        CLOCK_PROCESS_CPUTIME_ID    = 2 # High-resolution timer from the CPU.
        CLOCK_THREAD_CPUTIME_ID     = 3 # Thread-specific CPU-time clock.
        CLOCK_MONOTONIC_RAW	        = 4 # Monotonic system-wide clock, not adjusted for frequency scaling.
        CLOCK_REALTIME_COARSE       = 5 # System-wide realtime clock, updated only on ticks.
        CLOCK_MONOTONIC_COARSE      = 6 # Monotonic system-wide clock, updated only on ticks.
        CLOCK_BOOTTIME              = 7 # Monotonic system-wide clock that includes time spent in suspension.


    @classmethod
    def constants( cls ):
        return cls.Constants


    @classmethod
    def name( cls ):
        return cls.__name__



