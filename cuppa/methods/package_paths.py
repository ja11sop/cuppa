#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   env.PackageDir / PackageBin / PackageLib / PackageVersion / CMakePrefixPathFor
#-------------------------------------------------------------------------------

"""Construction-environment methods for BuildWith package layout paths."""

from cuppa.buildsys.cmake import cmake_prefix_path_for
from cuppa.package_managers import package_paths


class PackageDirMethod(object):
    """``env.PackageDir(name_or_dep)`` — absolute package root."""

    def __call__( self, env, name_or_dep ):
        return package_paths.package_dir( env, name_or_dep )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'PackageDir', cls() )


class PackageBinMethod(object):
    """``env.PackageBin(name_or_dep, *parts)`` — path under package ``bin/``."""

    def __call__( self, env, name_or_dep, *parts ):
        return package_paths.package_bin( env, name_or_dep, *parts )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'PackageBin', cls() )


class PackageLibMethod(object):
    """``env.PackageLib(name_or_dep)`` — package ``lib/`` directory."""

    def __call__( self, env, name_or_dep ):
        return package_paths.package_lib( env, name_or_dep )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'PackageLib', cls() )


class PackageVersionMethod(object):
    """``env.PackageVersion(name_or_dep)`` — concrete package version string."""

    def __call__( self, env, name_or_dep ):
        return package_paths.package_version( env, name_or_dep )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'PackageVersion', cls() )


class CMakePrefixPathForMethod(object):
    """``env.CMakePrefixPathFor(*names_or_deps)`` — ``;``-joined package roots."""

    def __call__( self, env, *names_or_deps ):
        return cmake_prefix_path_for( env, *names_or_deps )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CMakePrefixPathFor', cls() )
