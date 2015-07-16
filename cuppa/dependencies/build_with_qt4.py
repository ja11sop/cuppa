
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Qt4
#-------------------------------------------------------------------------------

import subprocess
import shlex

# Cuppa Imports
import cuppa.location
import cuppa.output_processor
import cuppa.build_platform
from cuppa.colourise import as_info, as_warning

import SCons.Script


class Qt4Exception(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class build_with_qt4(object):

    _name = "qt4"

    @classmethod
    def add_options( cls, add_option ):
        pass

    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        try:
            add_dependency( cls._name, cls( env ) )
        except Qt4Exception:
            print as_warning( env, "cuppa: warning: Could not create dependency [{}]. Dependency not available.".format( cls._name ) )


    def __init__( self, env ):

        url = "hg+https://bitbucket.org/dirkbaechle/scons_qt4"

        try:
            self._location = cuppa.location.Location( env, url, extra_sub_path = "qt4" )
        except cuppa.location.LocationException:
            print as_warning( env, "cuppa: qt4: warning: Could not retrieve url [{}]".format( url ) )
            raise Qt4Exception( "Could not retrieve scons_qt4 from [{}]".format( url ) )

        self._version = "4"

        if cuppa.build_platform.name() in ["Darwin", "Linux"]:
            if not cuppa.output_processor.command_available( "pkg-config" ):
                return
            if 'QT4DIR' not in env:
                self._set_qt4_dir( env )
            self._version = self._get_qt4_version()


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
                print "cuppa: qt4: Q4DIR detected as [{}]".format( as_info( env, env['QT4DIR'] ) )
        except:
            #TODO: Warning?
            pass


    def _get_qt4_version( self ):
        command = "pkg-config --modversion QtCore"
        try:
            return subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip()
        except:
            #TODO: Warning?
            return None


    def __call__( self, env, toolchain, variant ):

        SCons.Script.Tool( 'qt4', toolpath=[ self._location.base_local() ] )( env )

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


