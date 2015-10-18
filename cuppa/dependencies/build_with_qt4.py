
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Qt4
#-------------------------------------------------------------------------------

import subprocess
import shlex
import glob

# Cuppa Imports
import cuppa.location
import cuppa.output_processor
import cuppa.build_platform
from cuppa.colourise import as_info
from cuppa.log import logger

import SCons.Script


class Qt4Exception(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class build_with_qt4(object):

    _name = "qt4"
    _qt4_tool = None

    @classmethod
    def add_options( cls, add_option ):
        pass

    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        add_dependency( cls._name, cls.create )


    @classmethod
    def create( cls, env ):
        try:
            if not cls._qt4_tool:
                cls._qt4_tool = cls.retrieve_tool( env )
            return build_with_qt4( env )
        except Qt4Exception:
            logger.error( "Could not create dependency [{}]. Dependency not available.".format( cls._name ) )
        return None


    @classmethod
    def retrieve_tool( cls, env ):
        url = "hg+https://bitbucket.org/dirkbaechle/scons_qt4"
        try:
            return cuppa.location.Location( env, url, extra_sub_path = "qt4" )
        except cuppa.location.LocationException:
            logger.warn( "Could not retrieve scons_qt4 from [{}]".format( url ) )
        return None


    def __init__( self, env ):

        self._version = "4"

        if cuppa.build_platform.name() in ["Darwin", "Linux"]:
            if cuppa.output_processor.command_available( "pkg-config" ):
                if 'QT4DIR' not in env:
                    self._set_qt4_dir( env )
                self._version = self._get_qt4_version()

        elif cuppa.build_platform.name() == "Windows":
            if 'QT4DIR' not in env:
                paths = glob.glob( 'C:\\Qt\\4.*\\*' )
                if len(paths):
                    paths.sort()
                    env['QT4DIR'] = paths[-1]

        if 'QT4DIR' not in env:
            logger.error( "could not detect QT4 installation" )
            raise Qt4Exception( "could not detect QT4 installation." )

        logger.debug( "Q4DIR detected as [{}]".format( as_info( env['QT4DIR'] ) ) )



    def _set_qt4_dir( self, env ):
        command = "pkg-config --cflags QtCore"
        try:
            cflags = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip()
            if cflags:
                flags = env.ParseFlags( cflags )
                if 'CPPPATH' in flags:
                    shortest_path = flags['CPPPATH'][0]
                    for include in flags['CPPPATH']:
                        if len(include) < len(shortest_path):
                            shortest_path = include
                    env['QT4DIR'] = shortest_path
                logger.debug( "Q4DIR detected as [{}]".format( as_info( env['QT4DIR'] ) ) )
        except:
            logger.debug( "In _set_qt4_dir() failed to execute [{}]".format( command ) )



    def _get_qt4_version( self ):
        command = "pkg-config --modversion QtCore"
        try:
            return subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip()
        except:
            logger.debug( "In _get_qt4_version() failed to execute [{}]".format( command ) )
        return None


    def __call__( self, env, toolchain, variant ):

        SCons.Script.Tool( 'qt4', toolpath=[ self._qt4_tool.base_local() ] )( env )

        if cuppa.build_platform.name() in ["Darwin", "Linux"]:
            env.MergeFlags("-fPIC")


    def name( self ):
        return self._name

    def version( self ):
        return self._version

    def repository( self ):
        return "N/A"

    def branch( self ):
        return "N/A"

    def revisions( self ):
        return []


