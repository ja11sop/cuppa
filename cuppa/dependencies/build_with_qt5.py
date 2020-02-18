
#          Copyright Jamie Allsop 2015-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Qt5
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
from cuppa.utility.python2to3 import as_str

import SCons.Script


class Qt5Exception(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class build_with_qt5(object):

    _name = "qt5"
    _qt5_tool = None

    @classmethod
    def add_options( cls, add_option ):
        pass

    @classmethod
    def add_to_env( cls, cuppa_env, add_dependency  ):
        add_dependency( cls._name, cls.create )


    @classmethod
    def create( cls, env ):
        try:
            if not cls._qt5_tool:
                cls._qt5_tool = cls.retrieve_tool( env )
            return build_with_qt5( env )
        except Qt5Exception:
            logger.error( "Could not create dependency [{}]. Dependency not available.".format( cls._name ) )
        return None


    @classmethod
    def retrieve_tool( cls, env ):
        url = "hg+https://bitbucket.org/dirkbaechle/scons_qt5"
        try:
            return cuppa.location.Location( env, url, extra_sub_path = "qt5" )
        except cuppa.location.LocationException:
            logger.warn( "Could not retrieve scons_qt5 from [{}]".format( url ) )
        return None


    def __init__( self, env ):

        self._version = "5"

        if cuppa.build_platform.name() in ["Darwin", "Linux"]:
            if cuppa.output_processor.command_available( "pkg-config" ):
                if 'QT5DIR' not in env:
                    self._set_qt5_dir( env )
                self._version = self._get_qt5_version()

        elif cuppa.build_platform.name() == "Windows":
            if 'QT5DIR' not in env:
                paths = glob.glob( 'C:\\Qt\\5.*\\*' )
                if len(paths):
                    paths.sort()
                    env['QT5DIR'] = paths[-1]

        if 'QT5DIR' not in env:
            logger.error( "Could not detect QT5 installation" )
            raise Qt5Exception( "Could not detect QT5 installation." )

        self._sys_include_paths = [ env['QT5DIR'] ]

        logger.debug( "Q5DIR detected as [{}]".format( as_info( env['QT5DIR'] ) ) )


    def _set_qt5_dir( self, env ):
        command = "pkg-config --cflags Qt5Core"
        try:
            cflags = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip() )
            if cflags:
                flags = env.ParseFlags( cflags )
                if 'CPPPATH' in flags:
                    shortest_path = flags['CPPPATH'][0]
                    for include in flags['CPPPATH']:
                        if len(include) < len(shortest_path):
                            shortest_path = include
                    env['QT5DIR'] = shortest_path
        except:
            logger.debug( "In _set_qt5_dir() failed to execute [{}]".format( command ) )


    def _get_qt5_version( self ):
        command = "pkg-config --modversion Qt5Core"
        try:
            return as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip() )
        except:
            logger.debug( "In _get_qt5_version() failed to execute [{}]".format( command ) )
            return None


    def __call__( self, env, toolchain, variant ):

        SCons.Script.Tool( 'qt5', toolpath=[ self._qt5_tool.base_local() ] )( env )

        if cuppa.build_platform.name() in ["Darwin", "Linux"]:
            env.MergeFlags("-fPIC")


    @classmethod
    def name( cls ):
        return cls._name

    def version( self ):
        return self._version

    def repository( self ):
        return "N/A"

    def branch( self ):
        return "N/A"

    def revisions( self ):
        return []

    def location( self ):
        return self._qt5_tool

    def includes( self ):
        return []

    def sys_includes( self ):
        return self._sys_include_paths

