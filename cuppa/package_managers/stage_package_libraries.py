#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Stage / collect Cuppa package shared libraries beside tip programs
#-------------------------------------------------------------------------------

"""Copy package shared libraries next to a tip program for detached runs.

Construction ``ENV`` injection (`runtime_paths.apply_package_runtime_paths`)
covers Cuppa-spawned processes only. Tip binaries run from a shell, IDE, or
container need the libs under ``$ORIGIN/lib`` (Windows: beside the exe) plus
relocatable RPATH. Absolute dependency-cache RPATH stays out of policy.

Library set comes from ``_cuppa_package_link_contrib`` shared stems + libpath
(recorded by ``use_libs`` / defaults). See
``design/plans/package-runtime-deploy.md``.
"""

from __future__ import annotations

import os

from SCons.Script import Flatten

import cuppa.build_platform
from cuppa.colourise import as_info, as_notice
from cuppa.log import logger
from cuppa.package_managers.package_link_libs import (
        _LINK_CONTRIB_KEY,
        _shared_stem_from_filename,
        env_lib_naming,
        find_shared_library_path,
)


def package_shared_library_files( env ):
    """Return sorted unique shared library paths from package link contributions.

    Includes every matching soname / real file for each recorded shared stem
    under each contribution ``libpath`` (not only the preferred unversioned
    name). Empty when there are no shared package contributions.
    """
    store = env.get( _LINK_CONTRIB_KEY ) or {}
    if not store:
        return []

    lib_prefix, lib_suffix, shlib_prefix, shlib_suffix = env_lib_naming( env )
    del lib_prefix, lib_suffix  # naming helper returns the full tuple

    found = []
    seen = set()
    for contrib in store.values():
        shared = list( contrib.get( "shared" ) or [] )
        if not shared:
            continue
        library_prefix = contrib.get( "library_prefix" ) or ""
        for lib_dir in contrib.get( "libpath" ) or []:
            if not lib_dir:
                continue
            for stem in shared:
                for path in _shared_files_for_stem(
                        lib_dir,
                        str( stem ),
                        shlib_prefix,
                        shlib_suffix,
                        library_prefix=library_prefix,
                ):
                    if path not in seen:
                        seen.add( path )
                        found.append( path )
    return found


def _stem_match_candidates( stem, library_prefix="" ):
    """Return stem forms that may appear in filenames for a recorded link stem."""
    candidates = { str( stem ) }
    prefix = library_prefix or ""
    if prefix:
        text = str( stem )
        if text.startswith( prefix ):
            candidates.add( text[len( prefix ):] )
        else:
            candidates.add( prefix + text )
    return candidates


def _shared_files_for_stem(
        lib_dir, stem, shlib_prefix, shlib_suffix, library_prefix="",
):
    """All shared artefacts in ``lib_dir`` for ``stem`` (sonames included)."""
    if not lib_dir or not os.path.isdir( lib_dir ):
        primary = find_shared_library_path(
                lib_dir, stem, shlib_prefix, shlib_suffix,
                library_prefix=library_prefix,
        )
        return [ primary ] if primary else []

    wanted = _stem_match_candidates( stem, library_prefix=library_prefix )
    matches = []
    for fname in sorted( os.listdir( lib_dir ) ):
        path = os.path.join( lib_dir, fname )
        if not ( os.path.isfile( path ) or os.path.islink( path ) ):
            continue
        # Filename stem without stripping library_prefix — compare to candidates.
        found = _shared_stem_from_filename(
                fname, shlib_prefix, shlib_suffix, library_prefix="",
        )
        if found in wanted:
            matches.append( path )

    if matches:
        return matches

    primary = find_shared_library_path(
            lib_dir, stem, shlib_prefix, shlib_suffix,
            library_prefix=library_prefix,
    )
    return [ primary ] if primary else []


def package_runtime_rpath_linkflags( platform_name=None ):
    """Return linker flags that embed relocatable ORIGIN / loader_path RPATH.

    Empty on Windows (side-by-side DLL stage; no RPATH). Uses ``$$ORIGIN`` so
    SCons subst leaves a literal ``$ORIGIN`` for the linker.
    """
    if platform_name is None:
        platform_name = cuppa.build_platform.name()
    if platform_name == "Windows":
        return []
    if platform_name == "Darwin":
        return [
                "-Wl,-rpath,@loader_path",
                "-Wl,-rpath,@loader_path/lib",
        ]
    # Linux and other ELF: $$ → $ after SCons subst
    return [
            "-Wl,-rpath,$$ORIGIN",
            "-Wl,-rpath,$$ORIGIN/lib",
    ]


def ensure_package_runtime_rpath( env, platform_name=None ):
    """AppendUnique ORIGIN / loader_path RPATH flags onto ``env`` (no-op on Windows)."""
    flags = package_runtime_rpath_linkflags( platform_name=platform_name )
    if flags:
        env.AppendUnique( LINKFLAGS = flags )


def ensure_package_runtime_rpath_on_nodes( nodes, platform_name=None ):
    """AppendUnique RPATH onto each program node's build env (post-``Program``)."""
    flags = package_runtime_rpath_linkflags( platform_name=platform_name )
    if not flags:
        return
    for node in Flatten( [ nodes ] ):
        build_env = None
        getter = getattr( node, "get_build_env", None )
        if callable( getter ):
            try:
                build_env = getter()
            except Exception:
                build_env = None
        if build_env is None:
            build_env = getattr( node, "env", None )
        if build_env is not None:
            build_env.AppendUnique( LINKFLAGS = flags )


def stage_directory_for_program( program_node, platform_name=None ):
    """Return the directory that should receive staged package libs for ``program_node``."""
    if platform_name is None:
        platform_name = cuppa.build_platform.name()
    prog_path = _node_abspath( program_node )
    prog_dir = os.path.dirname( prog_path )
    if platform_name == "Windows":
        return prog_dir
    return os.path.join( prog_dir, "lib" )


def _node_abspath( node ):
    if hasattr( node, "get_abspath" ):
        return node.get_abspath()
    return os.path.abspath( str( node ) )


def _program_nodes( programs ):
    return [ node for node in Flatten( [ programs ] ) if node is not None ]


def install_package_shared_libraries( env, destination, sources=None ):
    """``Install`` package shared library files into ``destination``.

    ``sources`` defaults to :func:`package_shared_library_files`. Returns the
    Install node list (possibly empty).
    """
    if sources is None:
        sources = package_shared_library_files( env )
    sources = [ path for path in Flatten( [ sources ] ) if path ]
    if not sources or not destination:
        return []

    dest = destination
    if not hasattr( dest, "get_abspath" ):
        dest = env.Dir( dest )

    installed = []
    for source in sources:
        installed.extend( Flatten( [ env.Install( dest, source ) ] ) )
    return installed


def stage_package_libraries_for_programs(
        env, programs, platform_name=None, apply_rpath=True,
):
    """Stage package shared libs for each program; optional RPATH on nodes.

    Returns the list of Install nodes. Programs ``Requires`` / ``Clean`` the
    staged copies when any were produced.
    """
    if platform_name is None:
        platform_name = cuppa.build_platform.name()

    sources = package_shared_library_files( env )
    program_nodes = _program_nodes( programs )
    if apply_rpath and program_nodes:
        ensure_package_runtime_rpath_on_nodes(
                program_nodes, platform_name=platform_name,
        )

    if not sources or not program_nodes:
        return []

    installed = []
    # Group programs by stage directory so multi-program calls share Installs.
    by_dest = {}
    for node in program_nodes:
        dest = stage_directory_for_program( node, platform_name=platform_name )
        by_dest.setdefault( dest, [] ).append( node )

    for dest, nodes in by_dest.items():
        copied = install_package_shared_libraries( env, dest, sources=sources )
        if not copied:
            continue
        installed.extend( copied )
        for node in nodes:
            env.Requires( node, copied )
            env.Clean( node, copied )
        logger.debug(
                "Staged [{}] package shared libraries under [{}] for [{}]".format(
                        as_info( str( len( sources ) ) ),
                        as_notice( dest ),
                        as_notice( ", ".join( str( n ) for n in nodes ) ),
                )
        )
    return installed


def collect_package_libraries( env, destination, programs=None ):
    """Copy package shared libraries into ``destination`` (Docker / assembly).

    ``programs`` are optional Requires edges so collect runs with those
    targets. Always copies; library set is the same as Stage.
    """
    sources = package_shared_library_files( env )
    if not sources:
        return []

    installed = install_package_shared_libraries(
            env, destination, sources=sources,
    )
    if installed and programs is not None:
        for node in _program_nodes( programs ):
            env.Requires( node, installed )
            env.Clean( node, installed )
    if installed:
        logger.debug(
                "Collected [{}] package shared libraries into [{}]".format(
                        as_info( str( len( sources ) ) ),
                        as_notice( str( destination ) ),
                )
        )
    return installed


def should_stage_package_libraries( env, stage_package_libraries=None ):
    """Resolve the Build default / disable flag."""
    if stage_package_libraries is not None:
        return bool( stage_package_libraries )
    if "stage_package_libraries" in env:
        return bool( env.get( "stage_package_libraries" ) )
    return True
