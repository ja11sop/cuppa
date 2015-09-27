
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Build Platform
#-------------------------------------------------------------------------------

import platform
import subprocess
import shlex
import os.path

# Custom
import cuppa.modules.registration

from cuppa.platforms import *


class PlatformException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Platform(object):

    @classmethod
    def _get_supported_platforms( cls, supported ):
        cuppa.modules.registration.add_to_env( 'platforms', { 'env': supported } )


    @classmethod
    def _create( cls ):
        cls._supported = { 'platforms': {} }
        cls._get_supported_platforms( cls._supported )

        system = platform.system()
        if system not in cls._supported['platforms']:
            raise PlatformException( 'Platform [' + system + '] not supported. Supported platforms are ' + str(cls._supported['platforms']) )
        cls._platform = cls._supported['platforms'][ system ]
        cls._platform.initialise()


    @classmethod
    def supported( cls ):
        if not hasattr(cls, '_supported'):
            cls._create()
        return cls._supported['platforms']


    @classmethod
    def current( cls ):
        if not hasattr(cls, '_platform'):
            cls._create()
        return cls._platform


def which( program ):
    exe = 'which'
    if platform.system() == "Windows":
        exe = 'where.exe'
    command = "{} {}".format( exe, program )
    try:
        path = subprocess.check_output( shlex.split( command ) )
        return os.path.dirname( path )
    except subprocess.CalledProcessError as error:
        print "ERROR calling command \"{}\"; Failed with error: {}".format( command, str(error) )
    return None


def name():
    return Platform.current().name()


def constants():
    return Platform.current().constants()

