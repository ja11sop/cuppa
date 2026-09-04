
#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost Package
#-------------------------------------------------------------------------------

import os.path

from cuppa.dependencies.boost.boost_library_methods import remove_system_static_lib
from cuppa.dependencies.boost.library_naming import static_library_name
from cuppa.dependencies.boost.library_dependencies import add_dependent_libraries
from cuppa.dependencies.boost.version_and_location import determine_latest_boost_version
from cuppa.build_with_package import package_dependency


def use_libs( package, libraries ):

    env = package._env
    version = package._version

    libraries = remove_system_static_lib( env, libraries, boost_version=version )
    required_libs = add_dependent_libraries( float(version), "static", libraries )

    static_libs = []
    for lib in required_libs:
        lib_name = static_library_name( env, lib, env['toolchain'], version.replace(".","_"), package._variant, True )
        lib_path = os.path.join( package.lib_dir(), lib_name )
        static_libs.append( env.File( lib_path ) )

    env.AppendUnique( STATICLIBS = static_libs )


def latest_release( offline=False ):
    """Concrete Boost version from boost.org / compiled-in fallback (opt-in).

    Pass the return value as ``version=`` to :func:`define` when you want the registry
    to supply that **upstream** release. Registry ``\"latest\"`` / ``None`` instead mean
    newest version published in the registry — see ``cuppa.package_managers.gitlab_latest``.
    """
    version_str = determine_latest_boost_version( offline )
    versions = version_str.split( "." )
    return ".".join( [ versions[0], versions[1] ] )


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


        # API needed to support boost test runners
        def numeric_version( self ):
            return float(self._version)


        def patched_test( self ):
            return self._patched

    return boost
