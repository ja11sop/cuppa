
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Quince
#-------------------------------------------------------------------------------

import glob
import os.path
import subprocess
import shlex

# Cuppa Imports
import cuppa.location
import cuppa.output_processor



class build_with_quince(object):

    _name = "quince"

    @classmethod
    def add_options( cls, add_option ):

        location_name = cls._name + "-location"
        add_option( '--' + location_name, dest=location_name, type='string', nargs=1, action='store',
                    help = cls._name + ' location to build against' )

    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        location = env.get_option( cls._name + "-location" )
        if not location:
            location = env['thirdparty']
        if not location:
            print "No location specified for dependency [{}]. Dependency not available.".format( cls._name.title() )

        add_dependency( cls._name, cls( env, location ) )


    def __init__( self, env, location ):

        self._location = cuppa.location.Location( env, location )

        self._includes = [ os.path.join( self._location.local(), "include" ) ]
        src_glob = os.path.join( self._location.local(), "src", "*.cpp" )
        self._sources = glob.glob( src_glob )


    def __call__( self, env, toolchain, variant ):

        env.AppendUnique( INCPATH = self._includes )

        static_quince = env.BuildStaticLib( "quince", self._sources )

        env.BuildWith( 'boost' )

        env.AppendUnique( STATICLIBS = [
                static_quince,
                env.BoostStaticLibs( [
                        'filesystem',
                        'system',
                        'thread',
                ] )
        ] )


    def name( self ):
        return self._name

    def version( self ):
        return str(self._location.version())

    def repository( self ):
        return self._location.repository()

    def branch( self ):
        return self._location.branch()

    def revisions( self ):
        return self._location.revisions()



class quince_postgresql(object):

    _name = "quince-postgresql"

    @classmethod
    def add_options( cls, add_option ):

        location_name = cls._name + "-location"
        add_option( '--' + location_name, dest=location_name, type='string', nargs=1, action='store',
                    help = cls._name + ' location to build against' )

    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        location = env.get_option( cls._name + "-location" )
        if not location:
            location = env['thirdparty']
        if not location:
            print "No location specified for dependency [{}]. Dependency not available.".format( cls._name.title() )

        add_dependency( cls._name, cls( env, location ) )


    def __init__( self, env, location ):

        self._location = cuppa.location.Location( env, location )

        self._flags = {}
        self._flags['INCPATH'] = [ os.path.join( self._location.local(), "include" ) ]

        if cuppa.output_processor.command_available( "pg_config"):
            command = "pg_config --includedir"
            libpq_include = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip()
            self._flags['INCPATH'].append( libpq_include )

            command = "pg_config --libdir"
            libpq_libpath = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip()
            self._flags['LIBPATH'] = [ libpq_libpath ]

        self._flags['DYNAMICLIBS'] = [ 'pq' ]

        src_glob = os.path.join( self._location.local(), "src", "*.cpp" )
        self._sources = glob.glob( src_glob )


    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( INCPATH     = self._flags['INCPATH'] )
        env.AppendUnique( LIBPATH     = self._flags['LIBPATH'] )
        env.AppendUnique( DYNAMICLIBS = self._flags['DYNAMICLIBS'] )
        static_quince_postgresql = env.BuildStaticLib( "quince-postgresql", self._sources )
        env.AppendUnique( STATICLIBS  = [
                static_quince_postgresql,
                env.BoostStaticLibs( [ 'date_time' ] )
        ] )


    def name( self ):
        return self._name

    def version( self ):
        return str(self._location.version())

    def repository( self ):
        return self._location.repository()

    def branch( self ):
        return self._location.branch()

    def revisions( self ):
        return self._location.revisions()
