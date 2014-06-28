
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Linux Platform
#-------------------------------------------------------------------------------

from subprocess import Popen, PIPE
from re import sub, match, search, MULTILINE
from string import strip, replace
from os import path

import platform


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
        self.values = {}


    def default_toolchain( self ):
        return self.__default_toolchain


    def system_include_paths( self ):
        return self.values['system_include_paths']


    def system_lib_paths( self ):
        return self.values['system_lib_paths']


    def jar_home( self ):
        return self.values['jar_home']


    def __getitem__( self, key ):
        return self.values.get( key )


    def initialise( self, toolchains ):

        ( system, node, release, version, machine, processor ) = platform.uname()

        self.values['os'] = system

        gcc_version  = Popen(["gcc", "--version"], stdout=PIPE).communicate()[0]

        multiarch_lib_path = '-'.join( [ machine, system.lower(), 'gnu' ] )

        libc_file = "libc.so.6"
        libc_path = "/lib/" + libc_file

        if not path.exists( libc_path ):
            libc_path = "/lib/" + multiarch_lib_path + "/" + libc_file

        libc_version = Popen([libc_path], stdout=PIPE).communicate()[0]

        self.values['architecture']    = machine

        if machine == "i386":
            self.values['bit_width']   = '32'
        elif machine == "i686":
            self.values['bit_width']   = '32'
        elif machine == "x86_64":
            self.values['bit_width']   = '64'
        else:
            self.values['bit_width']   = 'unknown'

        self.values['os_version']           = match( r'(\d+\.\d+)', release ).group(0)
        self.values['toolchain_name']       = 'gcc' + search( r'(\d)\.(\d)\.(\d)', gcc_version ).expand(r'\1\2\3')
        self.values['libc_version']         = 'libc' + search( r'^GNU C Library [()a-zA-Z ]*([0-9][.0-9]+)', libc_version, MULTILINE ).expand(r'\1').replace('.','')
        self.values['toolchain_tag']        = 'gcc' + search( r'(\d)\.(\d)\.(\d)', gcc_version ).expand(r'\1\2')
        self.values['platform_path']        = self.values['architecture'] \
                                                + '_' + self.values['os'] \
                                                + '_' + self.values['os_version'] \
                                                + '_' + self.values['toolchain_tag']
        self.values['long_platform_path']   = self.values['os'] \
                                                + '/' + self.values['architecture'] \
                                                + '/' + self.values['os_version'] \
                                                + '/' + self.values['toolchain_name'] \
                                                + '_' + self.values['libc_version']

        self.values['system_include_paths'] = [ '/usr/include' ]
        self.values['system_lib_paths']     = [ '/usr/lib' ]
        self.values['jar_home']             = '/usr/share/java'

        toolchain_name = self.values['toolchain_tag']

        if toolchain_name not in toolchains:
            raise LinuxException( 'Toolchain [' + toolchain_name + '] not supported. Supported toolchains are ' + str(toolchains.keys()) )

        self.__default_toolchain = toolchains[ toolchain_name ]



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


    def print_values( self ):

        print 'os             = ' + self.values['os']
        print 'architecture   = ' + self.values['architecture']
        print 'bit_width      = ' + self.values['bit_width']
        print 'os_version     = ' + self.values['os_version']
        print 'toolchain_name = ' + self.values['toolchain_name']
        print 'toolchain_tag  = ' + self.values['toolchain_tag']
        print 'libc_version   = ' + self.values['libc_version']
        print 'platform_path  = ' + self.values['platform_path']

