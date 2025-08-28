
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost Library Methods
#-------------------------------------------------------------------------------

# SCons Imports
from SCons.Script import AlwaysBuild, Flatten

# Cuppa Imports
from cuppa.colourise import colour_items
from cuppa.log       import logger

# Boost Imports
from cuppa.dependencies.boost.boost_builder import BoostLibraryBuilder


def remove_system_static_lib( env, libraries ):
    boost_version = env['dependencies']['boost']( env ).numeric_version()
    if boost_version >= 1.89:
        try:
            libraries.remove( 'system' )
            logger.debug( "Removed 'system' static_lib for boost 1.89 or above" )
        except ValueError:
            pass
    return libraries


class BoostStaticLibraryMethod(object):

    def __init__( self, add_dependents=False, build_always=False, verbose_build=False, verbose_config=False ):
        self._add_dependents = add_dependents
        self._build_always   = build_always
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config


    def __call__( self, env, libraries ):

        if not self._add_dependents:
            logger.warn( "BoostStaticLibrary() is deprecated, use BoostStaticLibs() or BoostStaticLib() instead" )
        libraries = remove_system_static_lib( env, libraries )
        libraries = Flatten( [ libraries ] )

        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']( env )

        logger.trace( "Build static libraries [{}]".format( colour_items( libraries ) ) )

        library = BoostLibraryBuilder(
                Boost,
                add_dependents = self._add_dependents,
                verbose_build  = self._verbose_build,
                verbose_config = self._verbose_config )( env, None, None, libraries, 'static' )
        if self._build_always:
            return AlwaysBuild( library )
        else:
            return library



class BoostSharedLibraryMethod(object):

    def __init__( self, add_dependents=False, build_always=False, verbose_build=False, verbose_config=False ):
        self._add_dependents = add_dependents
        self._build_always   = build_always
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config

    def __call__( self, env, libraries ):
        if not self._add_dependents:
            logger.warn( "BoostSharedLibrary() is deprecated, use BoostSharedLibs() or BoostSharedLib() instead" )
        libraries = Flatten( [ libraries ] )

        if not 'boost' in env['BUILD_WITH']:
            env.BuildWith( 'boost' )
        Boost = env['dependencies']['boost']( env )

        for library in libraries:
            if library.startswith('log'):
                env.AppendUnique( CPPDEFINES = 'BOOST_LOG_DYN_LINK' )
            elif library == 'chrono':
                env.AppendUnique( CPPDEFINES = 'BOOST_CHRONO_DYN_LINK' )
            elif library == 'filesystem':
                env.AppendUnique( CPPDEFINES = 'BOOST_FILESYSTEM_DYN_LINK' )
            elif library == 'date_time':
                env.AppendUnique( CPPDEFINES = 'BOOST_DATE_TIME_DYN_LINK' )
            elif library == 'regex':
                env.AppendUnique( CPPDEFINES = 'BOOST_REGEX_DYN_LINK' )
            elif library == 'system':
                env.AppendUnique( CPPDEFINES = 'BOOST_SYSTEM_DYN_LINK' )

        library = BoostLibraryBuilder(
                Boost,
                add_dependents = self._add_dependents,
                verbose_build  = self._verbose_build,
                verbose_config = self._verbose_config )( env, None, None, libraries, 'shared' )
        if self._build_always:
            return AlwaysBuild( library )
        else:
            return library
