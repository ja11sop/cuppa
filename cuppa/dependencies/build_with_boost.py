
#          Copyright Jamie Allsop 2011-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost
#-------------------------------------------------------------------------------
import os

# Cuppa Imports
from cuppa.colourise import as_notice
from cuppa.log       import logger

# Boost Imports
from cuppa.dependencies.boost.version_and_location  import boost_location_id, get_boost_location, get_boost_version
from cuppa.dependencies.boost.boost_exception       import BoostException
from cuppa.dependencies.boost.patch_boost           import patched_boost_test
from cuppa.dependencies.boost.boost_library_methods import BoostStaticLibraryMethod, BoostSharedLibraryMethod



class Boost(object):

    _name = 'boost'
    _cached_boost_locations = {}

    @classmethod
    def add_options( cls, add_option ):
        add_option( '--boost-latest', dest='boost-latest', action='store_true',
                    help='Specify that you want to use boost. The latest version will be downloaded and used.' )

        add_option( '--boost-version', dest='boost-version', type='string', nargs=1, action='store',
                    help='Boost Version to build against' )

        add_option( '--boost-home', dest='boost-home', type='string', nargs=1, action='store',
                    help='The location of the boost source code' )

        add_option( '--boost-location', dest='boost-location', type='string', nargs=1, action='store',
                    help='The location of the boost source code' )

        add_option( '--boost-build-always', dest='boost-build-always', action='store_true',
                    help="Pass this if your boost source may change (for example you are patching it)"
                         " and you want boost build to be executed each time the library is asked for" )

        add_option( '--boost-verbose-build', dest='boost-verbose-build', action='store_true',
                    help="Pass this option if you wish to see the command-line output of boost build" )

        add_option( '--boost-verbose-config', dest='boost-verbose-config', action='store_true',
                    help="Pass this option if you wish to see the configuration output of boost build" )

        add_option( '--boost-patch-boost-test', dest='boost-patch-boost-test', action='store_true',
                    help="Use this option to patch boost test so it uses the new Boost.Timer and provides more usable output" )



    @classmethod
    def add_to_env( cls, cuppa_env, add_dependency ):
        add_dependency( cls._name, cls.create )



    @classmethod
    def create( cls, env ):

        boost_id = boost_location_id( env )

        if not boost_id in cls._cached_boost_locations:
            logger.debug( "Adding boost [{}] to env".format( as_notice( str(boost_id) ) ) )
            cls._cached_boost_locations[ boost_id ] = get_boost_location( env, boost_id[0], boost_id[1], boost_id[2], boost_id[3] )

        location = cls._cached_boost_locations[ boost_id ]

        boost = None
        try:
            boost = cls( env, env[ 'platform' ], location )
        except BoostException as e:
            logger.error( "Could not create boost dependency - {}".format(e) )
            return None

        if not boost:
            logger.error( "Could not create boost dependency" )
            return None

        build_always   = env.get_option( 'boost-build-always' )
        verbose_build  = env.get_option( 'boost-verbose-build' )
        verbose_config = env.get_option( 'boost-verbose-config' )

        env.AddMethod(
                BoostStaticLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config),
                "BoostStaticLibrary"
        )
        env.AddMethod(
                BoostSharedLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config),
                "BoostSharedLibrary"
        )
        env.AddMethod(
                BoostStaticLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config),
                "BoostStaticLib"
        )
        env.AddMethod(
                BoostSharedLibraryMethod(
                        add_dependents=False,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config),
                "BoostSharedLib"
        )
        env.AddMethod(
                 BoostStaticLibraryMethod(
                        add_dependents=True,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config),
                "BoostStaticLibs"
        )
        env.AddMethod(
                BoostSharedLibraryMethod(
                        add_dependents=True,
                        build_always=build_always,
                        verbose_build=verbose_build,
                        verbose_config=verbose_config),
                "BoostSharedLibs"
        )
        return boost


    def __init__( self, cuppa_env, platform, location ):

        self._location = location
        self.values = {}
        self.values['home'] = self._location.local()

        self._patched_test = patched_boost_test( self.values['home'] )

        self.values['full_version'], self.values['version'], self.values['numeric_version'] = get_boost_version( self.values['home'] )

        self.values['revisions'] = self._location.revisions()

        self.values['include']  = [ self.values['home'] ]
        self.values['lib_base'] = os.path.join( self.values['home'], 'build' )
        self.values['location'] = self.values['home']
        if self.values['numeric_version'] > 1.39:
            self.values['library_mt_tag'] = ''
        else:
            # TODO - nonsense code - need to fix
            self.values['library_mt_tag'] = '-' + platform['toolchain_tag'] + '-mt'

        self.values['defines'] = [
            'BOOST_PARAMETER_MAX_ARITY=20',
            'BOOST_DATE_TIME_POSIX_TIME_STD_CONFIG',
            'BOOST_BIND_GLOBAL_PLACEHOLDERS',
        ]


    @classmethod
    def name( cls ):
        return cls._name

    def version( self ):
        return self.values['version']

    def repository( self ):
        return self._location.repository()

    def branch( self ):
        return self._location.branch()

    def revisions( self ):
        return self._location.revisions()

    def local( self ):
        return self._location.local()

    def location( self ):
        return self._location

    def local_sub_path( self, *paths ):
        return os.path.join( self._location.local(), *paths )

    def local_abs_path( self, *paths ):
        return os.path.abspath( os.path.join( self._location.local(), *paths ) )

    def includes( self ):
        return []

    def sys_includes( self ):
        return self.values['include']


    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( SYSINCPATH = self.values['include'] )
        env.AppendUnique( CPPDEFINES = self.values['defines'] )


    def numeric_version( self ):
        return self.values['numeric_version']


    def full_version( self ):
        return self.values['full_version']


    def lib( self, library ):
        return 'boost_' + library + self.values['library_mt_tag']


    def patched_test( self ):
        return self._patched_test
