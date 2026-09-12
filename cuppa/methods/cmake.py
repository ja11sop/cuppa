#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CMakeConfigure / CMakeBuild / CMakeInstall (Option C)
#-------------------------------------------------------------------------------

"""Graph nodes for driving an external CMake project from a publisher sconscript.

Compose Option B helpers (``cmake_configure_command`` / ``cmake_build_command``)
with ``cuppa.utility.command.run`` and ``env.Command``. Callers still own
acquire, copy/Install into a package layout, and ``PublishPackage``.
"""

import os

import cuppa.progress

from cuppa.utility.command import run
from cuppa.buildsys.cmake import (
        cmake_build_command,
        cmake_build_jobs,
        cmake_configure_command,
)


def _node_abspath( path ):
    from SCons.Node import Node
    if isinstance( path, Node ):
        return path.abspath
    return os.path.abspath( str( path ) )


def cmake_build_tree_path( working_dir, build_dir ):
    """Absolute path of the CMake ``-B`` tree for ``env.Clean`` registration."""
    if build_dir is None:
        return None
    build_dir = str( build_dir )
    if os.path.isabs( build_dir ):
        return build_dir
    if working_dir is None:
        return None
    return os.path.join( _node_abspath( working_dir ), build_dir )


def _command_nodes( env, target, source, command, working_dir, clean_paths=None ):
    nodes = env.Command( target, source, run( command, working_dir=working_dir ) )
    if clean_paths:
        for path in clean_paths:
            if path:
                env.Clean( nodes, path )
    cuppa.progress.NotifyProgress.add( env, nodes )
    return nodes


class CMakeConfigureMethod(object):
    """``env.CMakeConfigure(source, working_dir=…, build_dir=…, …)``.

    Registers ``env.Clean`` on the CMake ``-B`` tree so ``cuppa -c`` removes it
    (stamps alone are not enough when ``-B`` lives under a location dependency).
    """

    def __call__(
            self,
            env,
            source,
            working_dir,
            target=None,
            build_dir=None,
            source_dir=None,
            generator=None,
            install_prefix=None,
            c_compiler=False,
            cxx_standard=True,
            extra_defines=None,
            include_build_type=True,
            include_cxx_compiler=True,
            cmake='cmake',
    ):
        if target is None:
            target = 'cmake.configure.complete'
        command = cmake_configure_command(
                env,
                cmake=cmake,
                build_dir=build_dir,
                source_dir=source_dir,
                generator=generator,
                install_prefix=install_prefix,
                c_compiler=c_compiler,
                cxx_standard=cxx_standard,
                extra_defines=extra_defines,
                include_build_type=include_build_type,
                include_cxx_compiler=include_cxx_compiler,
        )
        return _command_nodes(
                env,
                target,
                source,
                command,
                working_dir,
                clean_paths=[ cmake_build_tree_path( working_dir, build_dir ) ],
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CMakeConfigure', cls() )


class CMakeBuildMethod(object):
    """``env.CMakeBuild(source, build_dir=…, working_dir=…, jobs=…)``.

    With ``jobs=None`` (default), passes ``--parallel N`` when Cuppa
    ``--parallel`` set ``env['parallel']`` and ``env['job_count'] >= 2``.
    Pass ``jobs=False`` to omit; pass a positive int to override.
    Also ``Clean``s the CMake ``-B`` tree (same as configure).
    """

    def __call__(
            self,
            env,
            source,
            build_dir,
            working_dir,
            target=None,
            jobs=None,
            cmake='cmake',
    ):
        if target is None:
            target = 'cmake.build.complete'
        resolved_jobs = cmake_build_jobs( env, jobs=jobs )
        command = cmake_build_command(
                build_dir,
                jobs=resolved_jobs,
                cmake=cmake,
        )
        return _command_nodes(
                env,
                target,
                source,
                command,
                working_dir,
                clean_paths=[ cmake_build_tree_path( working_dir, build_dir ) ],
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CMakeBuild', cls() )


class CMakeInstallMethod(object):
    """``env.CMakeInstall(source, build_dir=…, working_dir=…, target=…)``.

    Runs ``cmake --build <build_dir> --target install`` (or ``cmake_target``).
    Default ``jobs=False`` omits ``--parallel``; pass ``jobs=None`` to honour
    Cuppa ``--parallel``, or a positive int to override.
    Also ``Clean``s the CMake ``-B`` tree (same as configure).
    """

    def __call__(
            self,
            env,
            source,
            build_dir,
            working_dir,
            target=None,
            cmake_target='install',
            jobs=False,
            cmake='cmake',
    ):
        if target is None:
            target = 'cmake.install.complete'
        resolved_jobs = cmake_build_jobs( env, jobs=jobs )
        command = cmake_build_command(
                build_dir,
                jobs=resolved_jobs,
                target=cmake_target,
                cmake=cmake,
        )
        return _command_nodes(
                env,
                target,
                source,
                command,
                working_dir,
                clean_paths=[ cmake_build_tree_path( working_dir, build_dir ) ],
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CMakeInstall', cls() )
