
#          Copyright Jamie Allsop 2015-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Quince
#-------------------------------------------------------------------------------

import os.path
import subprocess
import shlex
import platform
import glob
import six

# Cuppa Imports
import cuppa.location
import cuppa.output_processor
from cuppa.log import logger

# Quince Imports
from cuppa.build_with_location import location_dependency, LibraryMethod
from cuppa.utility.python2to3 import as_str, Exception



class QuinceException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)



class build_with_quince( location_dependency( 'quince', sys_include="include", source_path="src", linktype="static" ) ):

    def __init__( self, env, location, includes=[], sys_includes=[], source_path=None, linktype=None ):
        super(build_with_quince,self).__init__( env, location, includes, sys_includes, source_path, linktype )

        def update_env( env ):
            env.BuildWith('boost')

        env.AddMethod( LibraryMethod( self, update_env ), "QuinceLibrary" )


    def __call__( self, env, toolchain, variant ):
        super(build_with_quince,self).__call__( env, toolchain, variant )

        env.AppendUnique( STATICLIBS = [
                env.QuinceLibrary(),
                env.BoostStaticLibs( [
                        'filesystem',
                        'system',
                        'thread',
                ] ),
        ] )


class quince_date_lib( location_dependency( 'quince_date_lib', sys_include='include', location='git+https://github.com/HowardHinnant/date.git', linktype='static' ) ):
    def __call__( self, env, toolchain, variant ):
        super( quince_date_lib, self ).__call__( env, toolchain, variant )
        sources = env.Glob( self.local_sub_path( 'src/tz.cpp' ) )
        library = self.build_library_from_source( env, sources, "tz" )
        env.Append( STATICLIBS = [ library ] )
        env.AppendUnique( SHAREDLIBS = [ 'curl' ] )


class quince_postgresql( location_dependency( 'quince-postgresql', sys_include="include", source_path="src", linktype="static" ) ):

    def __init__( self, env, location, includes=[], sys_includes=[], source_path=None, linktype=None ):
        super(quince_postgresql,self).__init__( env, location, includes, sys_includes, source_path, linktype )

        self._flags = self.get_flags( location )

        def update_env( env ):
            env.BuildWith('boost')
            env.BuildWith('quince_date_lib')

        env.AddMethod( LibraryMethod( self, update_env ), "QuincePostgresqlLibrary" )


    def __call__( self, env, toolchain, variant ):
        super(quince_postgresql,self).__call__( env, toolchain, variant )

        env.AppendUnique( INCPATH     = self._flags['INCPATH'] )
        env.AppendUnique( LIBPATH     = self._flags['LIBPATH'] )
        env.AppendUnique( DYNAMICLIBS = self._flags['DYNAMICLIBS'] )

        quince_postgresql_lib = env.QuincePostgresqlLibrary()
        quince_lib = env.QuinceLibrary()

        env.Append( STATICLIBS = [
                quince_postgresql_lib,
                quince_lib,
                env.BoostStaticLibs( [ 'date_time' ] ),
        ] )

        env['dependencies']['quince_date_lib']( env )( env, toolchain, variant )


    @classmethod
    def get_flags( cls, location ):

        flags = {}
        flags['INCPATH'] = [ os.path.join( location.local(), "include" ) ]

        pg_config = "pg_config"
        if platform.system() == "Windows":
            pg_config = pg_config + ".exe"
            if not cuppa.output_processor.command_available( pg_config ):
                # try to find the Postgresql install
                program_files = os.environ.get( "ProgramW6432" )
                postgresql_base = os.path.join( program_files, "PostgreSQL" )
                if os.path.exists( postgresql_base ):
                    paths = glob.glob( postgresql_base + '\\*' )
                    if len(paths):
                        paths.sort()
                        latest = paths[-1]
                        pg_config = '\"' + os.path.join( latest, "bin", pg_config ) + '\"'

        if cuppa.output_processor.command_available( pg_config ):
            command = "{pg_config} --includedir".format( pg_config = pg_config )
            libpq_include = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip() )
            flags['INCPATH'].append( libpq_include )

            command = "{pg_config} --libdir".format( pg_config = pg_config )
            libpq_libpath = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip() )
            flags['LIBPATH'] = [ libpq_libpath ]
        else:
            logger.error( "postgresql: pg_config not available so cannot determine LIBPATH for postgres libraries" )
            raise QuinceException( "pg_config not available" )

        flags['DYNAMICLIBS'] = [ 'pq' ]

        return flags



class quince_sqlite( location_dependency( 'quince-sqlite', sys_include="include", source_path="src", linktype="static" ) ):


    def __init__( self, env, location, includes=[], sys_includes=[], source_path=None, linktype=None ):
        super(quince_sqlite,self).__init__( env, location, includes, sys_includes, source_path, linktype )

        self._flags = self.get_flags( env, location )

        def update_env( env ):
            env.BuildWith('boost')

        env.AddMethod( LibraryMethod( self, update_env ), "QuinceSqliteLibrary" )


    def __call__( self, env, toolchain, variant ):
        super(quince_sqlite,self).__call__( env, toolchain, variant )

        for name, flags in six.iteritems(self._flags):
            if flags:
                env.AppendUnique( **{ name: flags } )

        quince_sqlite_lib = env.QuinceSqliteLibrary()
        quince_lib = env.QuinceLibrary()

        env.Append( STATICLIBS  = [
                quince_sqlite_lib,
                quince_lib,
                env.BoostStaticLibs( [
                    'date_time',
                    'filesystem',
                ] ),
        ] )


    @classmethod
    def get_flags( cls, env, location ):

        flags = {}
        if cuppa.output_processor.command_available( "pkg-config"):
            command = "pkg-config --cflags --libs sqlite3"
            cflags = subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT ).strip()
            cls._flags = env.ParseFlags( cflags )
            if 'CPPPATH' in cls._flags:
                cls._flags['SYSINCPATH'] = cls._flags['CPPPATH']
                del cls._flags['CPPPATH']

            if 'LIBS' in cls._flags:
                cls._flags['DYNAMICLIBS'] = cls._flags['LIBS']
                del cls._flags['LIBS']

        if not 'INCPATH' in cls._flags:
            cls._flags['INCPATH'] = []
        cls._flags['INCPATH'].append( os.path.join( location.local(), "include" ) )

        return flags

