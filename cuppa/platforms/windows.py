
#          Copyright Jamie Allsop 2014-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Windows Platform
#-------------------------------------------------------------------------------

import platform


class WindowsException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Windows:

    @classmethod
    def add_to_env( cls, args ):
        args['env']['platforms']['Windows'] = cls()


    def __init__( self ):
        self._toolchain = None
        self.values = {}


    def default_toolchain( self ):
        if not self._toolchain:
            self._toolchain = 'vc'
        return self._toolchain


    def __getitem__( self, key ):
        return self.values.get( key )


    def _bit_depth( self, machine ):
        machine = machine.lower()
        if machine == "x86":
            return '32'
        elif machine == "amd64":
            return '64'
        else:
            return 'unknown'


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
        self.values['os_version']    = release
        self.values['bit_width']     = self._bit_depth( machine )
        self.values['platform_path'] = self.values['architecture'] + '_' + self.values['os'] + '_' + self.values['os_version']


    class Constants(object):
        pass


    @classmethod
    def constants( cls ):
        return cls.Constants


    @classmethod
    def name( cls ):
        return cls.__name__

