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
acquire (see ``env.DownloadExtract`` / ``env.RemoveEmptyDirs`` in
``cuppa.methods.acquire``), copy/Install into a package layout, and
``PublishPackage``.
"""

import os

import cuppa.progress

from cuppa.utility.command import run
from cuppa.buildsys.cmake import (
        cmake_build_command,
        cmake_build_jobs,
        cmake_configure_command,
        resolve_cmake_generator,
)
from cuppa.package_managers.package_amend import (
        amend_package_manifest_enabled,
        skip_builder_for_amend,
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


def _terse_summary_parts( *parts ):
    """Join non-empty summary tokens with spaces for a delegated file cell.

    These are argv-like fragments (``-B …``, ``-G Ninja``), not Cuppa status
    fields. Spaces keep them pasteable; middots stay between sconscript /
    variant / action / file on the status line.
    """
    return " ".join( str( part ) for part in parts if part )

def _command_nodes(
        env,
        target,
        source,
        command,
        working_dir,
        clean_paths=None,
        terse_action=None,
        terse_summary=None,
        after=None,
):
    action = run(
            command,
            working_dir=working_dir,
            terse_summary=terse_summary,
            terse_action=terse_action,
    )
    if after is not None:
        action = [ action, after ]
    nodes = env.Command(
            target,
            source,
            action,
    )
    cuppa.progress.label_terse_action(
            nodes, terse_action, summary=terse_summary,
    )
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
        # generator=None → Ninja when available; False → omit -G (see
        # cuppa.buildsys.cmake.resolve_cmake_generator).
        if target is None:
            target = 'cmake.configure.complete'
        if amend_package_manifest_enabled( env ):
            return skip_builder_for_amend( env, target, 'CMakeConfigure' )
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
        summary_parts = []
        if build_dir:
            summary_parts.append( '-B {}'.format( build_dir ) )
        resolved_generator = resolve_cmake_generator( generator )
        if resolved_generator:
            summary_parts.append( '-G {}'.format( resolved_generator ) )
        return _command_nodes(
                env,
                target,
                source,
                command,
                working_dir,
                clean_paths=[ cmake_build_tree_path( working_dir, build_dir ) ],
                terse_action='cmake-configure',
                terse_summary=_terse_summary_parts( *summary_parts ) or None,
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CMakeConfigure', cls() )


class CMakeBuildMethod(object):
    """``env.CMakeBuild(source, build_dir=…, working_dir=…, jobs=…)``.

    With ``jobs=None`` (default), passes ``--parallel N`` when Cuppa
    ``--parallel`` set ``env['parallel']`` and ``env['job_count'] >= 2``,
    otherwise ``--parallel 1`` so Ninja does not use all CPUs. Pass
    ``jobs=False`` to omit; pass a positive int to override.
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
        if amend_package_manifest_enabled( env ):
            return skip_builder_for_amend( env, target, 'CMakeBuild' )
        resolved_jobs = cmake_build_jobs( env, jobs=jobs )
        command = cmake_build_command(
                build_dir,
                jobs=resolved_jobs,
                cmake=cmake,
        )
        summary_parts = [ '-B {}'.format( build_dir ) ]
        if resolved_jobs is not None:
            summary_parts.append( '--parallel {}'.format( resolved_jobs ) )
        return _command_nodes(
                env,
                target,
                source,
                command,
                working_dir,
                clean_paths=[ cmake_build_tree_path( working_dir, build_dir ) ],
                terse_action='cmake-build',
                terse_summary=_terse_summary_parts( *summary_parts ),
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CMakeBuild', cls() )


class CMakeInstallMethod(object):
    """``env.CMakeInstall(source, build_dir=…, working_dir=…, target=…)``.

    Runs ``cmake --build <build_dir> --target install`` (or ``cmake_target``),
    then rewrites installed ``*.pc`` files when ``CMAKE_INSTALL_PREFIX`` is
    inside this package's build tree.
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
        if amend_package_manifest_enabled( env ):
            return skip_builder_for_amend( env, target, 'CMakeInstall' )
        resolved_jobs = cmake_build_jobs( env, jobs=jobs )
        command = cmake_build_command(
                build_dir,
                jobs=resolved_jobs,
                target=cmake_target,
                cmake=cmake,
        )
        summary_parts = [ '--target {}'.format( cmake_target ) ]
        if build_dir:
            summary_parts.insert( 0, '-B {}'.format( build_dir ) )
        build_tree = cmake_build_tree_path( working_dir, build_dir )

        def _relocate_pkgconfig( target, source, env ):
            from cuppa.buildsys.pkgconfig import relocate_cmake_install
            relocate_cmake_install( env, build_tree )
            return None

        return _command_nodes(
                env,
                target,
                source,
                command,
                working_dir,
                clean_paths=[ build_tree ],
                terse_action='cmake-install',
                terse_summary=_terse_summary_parts( *summary_parts ),
                after=_relocate_pkgconfig,
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'CMakeInstall', cls() )


class RelocatePkgConfigMethod(object):
    """``env.RelocatePkgConfig(source, prefix=…)``.

    Rewrites ``*.pc`` under ``prefix`` after ``source`` (usually a CMake
    install). ``CMakeInstall`` does this itself when the build cache records
    a prefix inside the package tree. Use this for a tree that was staged
    some other way.
    """

    def __call__( self, env, source, prefix ):
        prefix_path = _node_abspath( prefix )
        stamp = "relocate-pkgconfig-{}".format(
                str( prefix_path ).replace( os.sep, "_" ).replace( ":", "_" )
        )

        def _relocate( target, source, env ):
            from cuppa.buildsys.pkgconfig import relocate_pkgconfig
            relocate_pkgconfig( prefix_path )
            return None

        return env.Command( stamp, source, _relocate )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'RelocatePkgConfig', cls() )
