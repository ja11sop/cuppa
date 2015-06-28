
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Qt5
#-------------------------------------------------------------------------------

import subprocess
import shlex

# Cuppa Imports
import cuppa.location
import cuppa.output_processor
import cuppa.build_platform
from cuppa.colourise import as_info

import SCons.Script



class build_with_qt5(object):

    _name = "qt5"

    @classmethod
    def add_options( cls, add_option ):
        pass

    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        add_dependency( cls._name, cls( env ) )


    def __init__( self, env ):

        self._location = cuppa.location.Location(
                env,
                "hg+https://bitbucket.org/dirkbaechle/scons_qt5",
                extra_sub_path = "qt5"
        )

        if not cuppa.output_processor.command_available( "pkg-config" ):
            return

        self._version = "5"

        if cuppa.build_platform.name() in ["Darwin", "Linux"]:
            if 'QT5DIR' not in env:
                self._set_qt5_dir( env )
            self._version = self._get_qt5_version()


    def _set_qt5_dir( self, env ):
        command = "pkg-config --cflags Qt5Core"
        try:
            includes = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip().split()
            if includes:
                shortest_path = includes[0]
                for include in includes:
                    if len(include) < len(shortest_path):
                        shortest_path = include
                qt5dir = env.ParseFlags( shortest_path )['CPPPATH'][0]
                env['QT5DIR'] = qt5dir
                print "cuppa: qt5: Q5DIR detected as [{}]".format( as_info( env, env['QT5DIR'] ) )
        except:
            #TODO: Warning?
            pass


    def _get_qt5_version( self ):
        command = "pkg-config --modversion Qt5Core"
        try:
            return subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip()
        except:
            #TODO: Warning?
            return None


    def __call__( self, env, toolchain, variant ):

        SCons.Script.Tool( 'qt5',toolpath=[self._location.base_local()] )( env )

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


