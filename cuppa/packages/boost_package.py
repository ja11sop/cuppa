
#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost Package
#-------------------------------------------------------------------------------

import os.path

from cuppa.dependencies.boost.library_naming import static_library_name
from cuppa.dependencies.boost.library_dependencies import add_dependent_libraries
from cuppa.dependencies.boost.version_and_location import determine_latest_boost_verion
from cuppa.log import logger
from cuppa.colourise import as_info
from cuppa.build_with_package import package_dependency


def use_libs( package, libraries ):

    env = package._env
    version = package._version

    required_libs = add_dependent_libraries( float(version), "static", libraries )

    static_libs = []
    for lib in required_libs:
        lib_name = static_library_name( env, lib, env['toolchain'], version.replace(".","_"), package._variant, True )
        lib_path = os.path.join( package.lib_dir(), lib_name )
        static_libs.append( env.File( lib_path ) )

    env.AppendUnique( STATICLIBS = static_libs )


def default_version( package, version, env ):
    if version == "latest" or version == None:
        version_str = determine_latest_boost_verion( env['offline'] )
        versions = version_str.split(".")
        package._version = ".".join( [versions[0], versions[1]] )
        logger.info( "No Boost package version specified, using [{}]".format( as_info( package._version ) ) )


def define( registry=None, version=None, variant=None, patched=True ):

    class boost( package_dependency(
            'boost_package',
            registry = registry,
            package  = 'boost',
            version  = version,
            variant  = variant,
            patched  = patched
    ) ):

        def __call__( self, env, toolchain, variant ):
            env.MergeFlags( '-DBOOST_PARAMETER_MAX_ARITY=20' )
            env.MergeFlags( '-DBOOST_DATE_TIME_POSIX_TIME_STD_CONFIG' )
            env.MergeFlags( '-DBOOST_BIND_GLOBAL_PLACEHOLDERS' )
            if self._patched:
                env.MergeFlags( '-DBOOST_TEST_USE_QUALIFIED_COMMANDLINE_ARGUMENTS' )

            self._package.initialise_build_variant( env, toolchain, variant )


        def use_libs( self, libs ):
            import cuppa
            cuppa.packages.boost_package.use_libs( self._package, libs )


        @classmethod
        def default_version( cls, version, env ):
            import cuppa
            cuppa.packages.boost_package.default_version( cls, version, env )


        # API needed to support boost test runners
        def numeric_version( self ):
            return float(self._version)


        def patched_test( self ):
            return self._patched

    return boost
