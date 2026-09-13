#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CMake configure / build argv helpers (cuppa.buildsys)
#-------------------------------------------------------------------------------

"""Build ``cmake`` configure and ``cmake --build`` argv from a Cuppa ``env``.

Public API for publisher sconscripts. Option B covers configure flags;
``env.CMakeConfigure`` / ``CMakeBuild`` / ``CMakeInstall`` compose these with
``cuppa.utility.command.run``. Prefer reading ``env['toolchain']`` /
``env['variant']`` / ``env['parallel']`` / ``env['job_count']`` so unit tests
can pass plain mappings; sconscript authors still use ``env.Toolchain()`` /
``env.Variant()`` elsewhere.

Also: ``cmake_prefix_path`` / ``cmake_prefix_path_for`` /
``cmake_install_rpath_defines`` / ``resolve_cmake_generator`` for shared-package
``CMAKE_PREFIX_PATH``, install vs build-tree RPATH, and default ``-G Ninja``
when ``ninja`` is on ``PATH``. Package path lookup lives in
``cuppa.package_managers.package_paths``; prefer ``env.CMakePrefixPathFor`` /
``env.PackageBin`` from sconscripts.

Acquire / staging helpers (``remove_empty_dirs``, ``env.DownloadExtract``,
``env.RemoveEmptyDirs``) live in ``cuppa.buildsys.acquire`` /
``cuppa.methods.acquire``. This module re-exports ``remove_empty_dirs`` and
gitmodules helpers for one cycle so existing ``from cuppa.buildsys import cmake``
imports keep working.

Future siblings (for example ``cuppa.buildsys.b2``) belong in this package.
"""

import shlex

from cuppa.buildsys.acquire import (
        gitmodules_child_names,
        gitmodules_paths,
        remove_empty_dirs,
        resolve_gitmodules_path,
)

__all__ = [
        'gitmodules_child_names',
        'gitmodules_paths',
        'remove_empty_dirs',
        'resolve_gitmodules_path',
        'cmake_build_type_for_variant',
        'cmake_cxx_standard_for_stdcpp',
        'cmake_configure_args',
        'cmake_configure_command',
        'cmake_build_jobs',
        'cmake_build_args',
        'cmake_build_command',
        'cmake_prefix_path',
        'cmake_prefix_path_for',
        'cmake_install_rpath_defines',
        'resolve_cmake_generator',
]


# Cuppa variant.name() → CMAKE_BUILD_TYPE. Unknown names fall back to Release
# only when the caller asks for a build type; prefer explicit mapping in docs.
_VARIANT_BUILD_TYPE = {
        'dbg': 'Debug',
        'rel': 'Release',
        'cov': 'RelWithDebInfo',
}

# Cuppa --stdcpp / StdCpp() token → CMAKE_CXX_STANDARD. Experimental /
# vendor-latest tokens that CMake may not accept as an integer are omitted
# (return None).
_STDCPP_CXX_STANDARD = {
        'c++98': 98,
        'c++03': 98,
        'c++0x': 11,
        'c++11': 11,
        'c++1y': 14,
        'c++14': 14,
        'c++1z': 17,
        'c++17': 17,
        'c++2a': 20,
        'c++20': 20,
        'c++2b': 23,
        'c++23': 23,
        'c++2c': 26,
        'c++26': 26,
        # c++latest: omit — not a portable CMAKE_CXX_STANDARD value
}


def cmake_build_type_for_variant( variant_name ):
    """Return ``CMAKE_BUILD_TYPE`` for a Cuppa variant name, or ``None`` if unknown."""
    if not variant_name:
        return None
    return _VARIANT_BUILD_TYPE.get( str( variant_name ) )


def cmake_cxx_standard_for_stdcpp( standard ):
    """Return ``CMAKE_CXX_STANDARD`` int for a Cuppa dialect token, or ``None`` to omit."""
    if not standard:
        return None
    return _STDCPP_CXX_STANDARD.get( str( standard ) )


def _variant_name( env ):
    variant = env['variant']
    name = getattr( variant, 'name', None )
    if callable( name ):
        return name()
    return str( variant )


def _cxx_compiler( env ):
    toolchain = env.get( 'toolchain' )
    binary = getattr( toolchain, 'binary', None )
    if callable( binary ):
        return binary()
    return env.get( 'CXX' )


def _define_args( defines ):
    """Turn a dict into ``-DNAME=value`` tokens (``True`` → ``-DNAME=ON``)."""
    args = []
    if not defines:
        return args
    for key in sorted( defines.keys(), key=str ):
        value = defines[ key ]
        name = str( key )
        if value is True:
            args.append( '-D{}=ON'.format( name ) )
        elif value is False:
            args.append( '-D{}=OFF'.format( name ) )
        elif value is None:
            args.append( '-D{}'.format( name ) )
        else:
            args.append( '-D{}={}'.format( name, value ) )
    return args


def cmake_configure_args(
        env,
        build_dir=None,
        source_dir=None,
        generator=None,
        install_prefix=None,
        c_compiler=False,
        cxx_standard=True,
        extra_defines=None,
        include_build_type=True,
        include_cxx_compiler=True,
):
    """Return cmake **configure** argv tokens (without a leading ``cmake``).

    Parameters mirror the Antora Cuppa→CMake mapping:

    - ``build_dir`` / ``source_dir`` → ``-B`` / ``-S``
    - ``generator`` → ``-G`` via :func:`resolve_cmake_generator` (``None`` =
      Ninja when ``ninja`` is on ``PATH``; ``False`` = omit ``-G``)
    - active variant → ``-DCMAKE_BUILD_TYPE=…`` (``dbg``/``rel``/``cov``; omit if
      unknown unless you set ``include_build_type=False``)
    - active toolchain ``.binary()`` (else ``env['CXX']``) → ``CMAKE_CXX_COMPILER``
    - ``c_compiler=True`` → also ``CMAKE_C_COMPILER`` from ``env['CC']`` when set
    - ``cxx_standard=True`` → ``CMAKE_CXX_STANDARD`` when ``env['stdcpp']`` maps
    - ``install_prefix`` → ``CMAKE_INSTALL_PREFIX``
    - ``extra_defines`` → additional ``-DNAME=value`` (bool → ON/OFF)

    Does **not** add Cuppa coverage flags for ``cov``: Cuppa ``--cov`` does not
    instrument a pure CMake compile.
    """
    args = []
    if source_dir is not None:
        args.extend( [ '-S', str( source_dir ) ] )
    if build_dir is not None:
        args.extend( [ '-B', str( build_dir ) ] )
    resolved_generator = resolve_cmake_generator( generator )
    if resolved_generator is not None:
        args.extend( [ '-G', str( resolved_generator ) ] )

    if include_build_type:
        build_type = cmake_build_type_for_variant( _variant_name( env ) )
        if build_type is not None:
            args.append( '-DCMAKE_BUILD_TYPE={}'.format( build_type ) )

    if include_cxx_compiler:
        cxx = _cxx_compiler( env )
        if cxx:
            args.append( '-DCMAKE_CXX_COMPILER={}'.format( cxx ) )

    if c_compiler:
        cc = env.get( 'CC' )
        if cc:
            args.append( '-DCMAKE_C_COMPILER={}'.format( cc ) )

    if install_prefix is not None:
        args.append( '-DCMAKE_INSTALL_PREFIX={}'.format( str( install_prefix ) ) )

    if cxx_standard:
        standard = env.get( 'stdcpp' )
        mapped = cmake_cxx_standard_for_stdcpp( standard )
        if mapped is not None:
            args.append( '-DCMAKE_CXX_STANDARD={}'.format( mapped ) )

    args.extend( _define_args( extra_defines ) )
    return args


def cmake_configure_command(
        env,
        cmake='cmake',
        **kwargs
):
    """Return a shell command string suitable for ``cuppa.utility.command.run``."""
    tokens = [ cmake ] + list( cmake_configure_args( env, **kwargs ) )
    return ' '.join( shlex.quote( str( token ) ) for token in tokens )


def cmake_build_jobs( env, jobs=None ):
    """Resolve a ``cmake --build --parallel`` job count, or ``None`` to omit.

    ``jobs``:

    - ``None`` (default): use ``env['job_count']`` when ``env['parallel']`` is
      true and the count is at least 2 (Cuppa ``--parallel``)
    - ``False`` or ``0``: omit ``--parallel`` / ``-j``
    - positive ``int``: that many jobs (manual override)
    """
    if jobs is False or jobs == 0:
        return None
    if jobs is not None:
        count = int( jobs )
        if count < 1:
            return None
        return count
    if env.get( 'parallel' ) and int( env.get( 'job_count' ) or 1 ) >= 2:
        return int( env['job_count'] )
    return None


def cmake_build_args( build_dir, jobs=None, target=None ):
    """Return ``cmake --build`` argv tokens (without a leading ``cmake``).

    ``jobs`` must already be resolved (positive ``int`` or ``None`` to omit).
    Uses CMake's generator-agnostic ``--parallel N`` rather than ``-- -j N``.
    """
    args = [ '--build', str( build_dir ) ]
    if target is not None:
        args.extend( [ '--target', str( target ) ] )
    if jobs is not None:
        args.extend( [ '--parallel', str( int( jobs ) ) ] )
    return args


def cmake_build_command( build_dir, jobs=None, target=None, cmake='cmake' ):
    """Return a ``cmake --build`` shell string for ``cuppa.utility.command.run``."""
    tokens = [ cmake ] + list( cmake_build_args( build_dir, jobs=jobs, target=target ) )
    return ' '.join( shlex.quote( str( token ) ) for token in tokens )


def resolve_cmake_generator( generator=None ):
    """Resolve a CMake ``-G`` value, or ``None`` to omit ``-G``.

    - ``None`` (default): ``Ninja`` when ``ninja`` is on ``PATH``, else omit
    - ``False``: always omit ``-G`` (CMake's own default generator)
    - other values: ``str(generator)`` as the exact ``-G`` argument
    """
    if generator is False:
        return None
    if generator is None:
        import shutil
        if shutil.which( 'ninja' ):
            return 'Ninja'
        return None
    return str( generator )


def cmake_prefix_path( *dirs ):
    """Return a ``CMAKE_PREFIX_PATH`` value (CMake ``;``-joined).

    Empty or ``None`` entries are skipped. Suitable for
    ``extra_defines={'CMAKE_PREFIX_PATH': cmake_prefix_path(a, b)}``.
    Prefer ``env.CMakePrefixPathFor(*names)`` /
    ``cmake_prefix_path_for(env, *names)`` when the dirs come from
    ``BuildWith`` packages.
    """
    parts = [ str( path ) for path in dirs if path ]
    return ';'.join( parts )


def cmake_prefix_path_for( env, *package_names ):
    """``CMAKE_PREFIX_PATH`` from ``BuildWith`` package roots (order preserved).

    Each argument may be a BuildWith name string or a dependency object.
    First match wins for CMake ``find_package`` when prefixes overlap — put
    more specific packages first (for example OpenTelemetry before gRPC
    before Protobuf). Prefer ``env.CMakePrefixPathFor`` from sconscripts.
    """
    from cuppa.package_managers.package_paths import package_dir

    return cmake_prefix_path(
            *( package_dir( env, name ) for name in package_names )
    )


def cmake_install_rpath_defines(
        install_rpath='$ORIGIN/../lib',
        build_rpath='$ORIGIN',
        extra_install=(),
        extra_build=(),
        build_with_install_rpath=False,
):
    """Return ``extra_defines`` for install vs build-tree RPATH.

    Default story for shared-library publishers:

    - **Install:** ``CMAKE_INSTALL_RPATH=$ORIGIN/../lib`` (packaged ``bin/`` →
      ``lib/``)
    - **Build:** ``CMAKE_BUILD_RPATH=$ORIGIN`` so in-tree tools beside their
      ``.so`` (for example ``grpc_cpp_plugin``) resolve without relying on
      install layout
    - ``CMAKE_BUILD_WITH_INSTALL_RPATH`` defaults to **False** so the build
      RPATH is used during ``CMakeBuild``

    Pass absolute dependency ``lib/`` dirs via ``extra_install`` /
    ``extra_build`` when a plugin links packaged Protobuf (or similar). Prefer
    that over embedding relocatable-cache absolute RPATHs into consumer link
    lines.
    """
    install_parts = [ install_rpath ] if install_rpath else []
    install_parts.extend( str( path ) for path in extra_install if path )
    build_parts = [ build_rpath ] if build_rpath else []
    build_parts.extend( str( path ) for path in extra_build if path )
    defines = {
            'CMAKE_BUILD_WITH_INSTALL_RPATH': bool( build_with_install_rpath ),
    }
    if install_parts:
        defines['CMAKE_INSTALL_RPATH'] = ';'.join( install_parts )
    if build_parts:
        defines['CMAKE_BUILD_RPATH'] = ';'.join( build_parts )
    return defines

