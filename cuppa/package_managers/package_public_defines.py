#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Public compile defines that travel with a GitLab package.

The package carries one list. ``BuildWith`` applies it when the headers go
on. A publisher may set that list itself, or pass :func:`cmake_public_defines`
so publish asks CMake for ``INTERFACE_COMPILE_DEFINITIONS`` after install.

See ``design/plans/package-public-defines.md``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

import SCons.Errors

from cuppa.log import logger
from cuppa.utility.types import is_string


_IMPORTED_TARGET = re.compile(
        r"\badd_(?:library|executable)\(\s*"
        r"([A-Za-z_][A-Za-z0-9_:.+-]*)"
        r"\s+[^)]*\bIMPORTED\b",
        re.IGNORECASE,
)
_SAFE_NAME = re.compile( r"^[A-Za-z_][A-Za-z0-9_:.+-]*\Z" )


class CmakePublicDefines:
    """Marker. Publish asks CMake; the sconscript does not run the query."""

    def __repr__( self ) -> str:
        return "cmake_public_defines()"


def cmake_public_defines() -> CmakePublicDefines:
    """Return the marker passed as ``GitlabPackagePublisher(public_defines=...)``.

    The call does not run CMake. After install, publish loads the package and
    reads each imported target's ``INTERFACE_COMPILE_DEFINITIONS``, including
    definitions that arrive through ``INTERFACE_LINK_LIBRARIES``.
    """
    return CmakePublicDefines()


def _define_token( text: str ) -> str | None:
    token = str( text ).strip().strip( '"' )
    if not token or token.startswith( "$<" ) or token.endswith( "-NOTFOUND" ):
        return None
    if any( char.isspace() for char in token ):
        return None
    return token


def normalise_public_defines( value: Any ) -> list[str] | None:
    """Return a list of define tokens, or ``None`` when omitted or empty.

    A string value is one define. ``[]`` publishes none. A define must be a
    single token (``USE_OS_TZDB=1`` or ``USE_OS_TZDB``).
    """
    if value is None:
        return None
    if isinstance( value, CmakePublicDefines ):
        raise SCons.Errors.StopError(
                "cmake_public_defines() has to be resolved while publishing, "
                "not written into cuppa-publish.json directly"
        )
    if isinstance( value, dict ):
        raise SCons.Errors.StopError(
                "Package public_defines is a list of tokens for the package, "
                "not a mapping of library stems"
        )
    if is_string( value ):
        pieces = [ value ]
    else:
        try:
            pieces = list( value )
        except TypeError as exc:
            raise SCons.Errors.StopError(
                    "Package public_defines must be a list of defines; got [{}]"
                    .format( type( value ).__name__ )
            ) from exc
    defines = []
    for piece in pieces:
        if not is_string( piece ) and not isinstance( piece, ( int, float ) ):
            raise SCons.Errors.StopError(
                    "Package public_defines entries must be strings; got [{}]"
                    .format( type( piece ).__name__ )
            )
        token = _define_token( str( piece ) )
        if token is None:
            raise SCons.Errors.StopError(
                    "Package public_defines has an unusable define [{}]".format( piece )
            )
        if token not in defines:
            defines.append( token )
    return defines or None


def install_cppdefines( env, defines: list[str] | None ) -> None:
    """Add ``defines`` to ``CPPDEFINES`` without duplicating an existing token."""
    if not defines:
        return
    current = list( env.get( "CPPDEFINES" ) or [] )
    present = { str( item ) for item in current }
    for define in defines:
        if str( define ) not in present:
            current.append( define )
            present.add( str( define ) )
    env["CPPDEFINES"] = current


def _define_key( token: str ) -> str:
    return token.split( "=", 1 )[0]


def union_target_defines( per_target: dict[str, list[str]] ) -> list[str]:
    """One package list from each target's consumer-visible defines.

    Target names are visited in sorted order. A later target that repeats a
    token is skipped. The same name with two values (``FOO=0`` and ``FOO=1``)
    is an error: the author sets ``public_defines`` explicitly.
    """
    chosen: dict[str, tuple[str, str]] = {}
    order: list[str] = []
    for target in sorted( per_target ):
        for token in per_target[target]:
            key = _define_key( token )
            previous = chosen.get( key )
            if previous is None:
                chosen[key] = ( token, target )
                order.append( token )
                continue
            if previous[0] == token:
                continue
            raise SCons.Errors.StopError(
                    "CMake public defines disagree on [{}]: [{}] from [{}] "
                    "and [{}] from [{}]. Set public_defines to the list this "
                    "package should carry.".format(
                            key, previous[0], previous[1], token, target,
                    )
            )
    return order


def cmake_package_names( package_dir: str ) -> list[str]:
    """``FooConfig.cmake`` / ``foo-config.cmake`` names under ``lib/cmake``."""
    root = os.path.join( package_dir, "lib", "cmake" )
    if not os.path.isdir( root ):
        return []
    names: list[str] = []
    for dirpath, dirnames, filenames in os.walk( root ):
        dirnames[:] = [ name for name in dirnames if name != ".git" ]
        for filename in filenames:
            if filename.endswith( "ConfigVersion.cmake" ):
                continue
            if filename.endswith( "Config.cmake" ):
                name = filename[: -len( "Config.cmake" )]
            elif filename.endswith( "-config.cmake" ):
                name = filename[: -len( "-config.cmake" )]
            else:
                continue
            if name and name not in names:
                names.append( name )
    return names


def imported_cmake_targets( package_dir: str ) -> list[str]:
    """Imported target names from installed ``*Targets.cmake`` files.

    Names only. The define values are what CMake reports for those targets,
    not the strings in the file.
    """
    root = os.path.join( package_dir, "lib", "cmake" )
    if not os.path.isdir( root ):
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk( root ):
        dirnames[:] = [ name for name in dirnames if name != ".git" ]
        for filename in sorted( filenames ):
            lower = filename.lower()
            if not lower.endswith( "targets.cmake" ):
                continue
            path = os.path.join( dirpath, filename )
            try:
                with open( path, encoding="utf-8", errors="replace" ) as handle:
                    text = handle.read()
            except OSError:
                continue
            for match in _IMPORTED_TARGET.finditer( text ):
                name = match.group( 1 )
                if name not in found:
                    found.append( name )
    return found


def _require_cmake_name( label: str, name: str ) -> None:
    if not _SAFE_NAME.match( name ):
        raise SCons.Errors.StopError(
                "Cannot ask CMake about {} [{}]".format( label, name )
        )


def _probe_configure_args( env ) -> list[str]:
    if env is None:
        return []
    from cuppa.buildsys.cmake import (
            _cxx_compiler,
            _variant_name,
            cmake_build_type_for_variant,
    )

    args = []
    try:
        cxx = _cxx_compiler( env )
    except ( KeyError, TypeError, AttributeError ):
        cxx = None
    if cxx:
        args.append( "-DCMAKE_CXX_COMPILER={}".format( cxx ) )
    try:
        build_type = cmake_build_type_for_variant( _variant_name( env ) )
    except ( KeyError, TypeError, AttributeError ):
        build_type = None
    if build_type:
        args.append( "-DCMAKE_BUILD_TYPE={}".format( build_type ) )
    return args


def _probe_cmake_lists( packages: list[str], targets: list[str] ) -> str:
    package_lines = "\n".join( '  "{}"'.format( name ) for name in packages )
    target_lines = "\n".join( '  "{}"'.format( name ) for name in targets )
    return """cmake_minimum_required(VERSION 3.20)
project(cuppa_public_defines LANGUAGES CXX)
set(_cuppa_packages
{packages}
)
foreach(pkg IN LISTS _cuppa_packages)
  find_package(${{pkg}} REQUIRED CONFIG)
endforeach()
set(_cuppa_targets
{targets}
)

function(_cuppa_write_define index tgt)
  if(NOT TARGET ${{tgt}})
    message(FATAL_ERROR "Cuppa public defines: CMake has no target ${{tgt}}")
  endif()
  # ``index`` and ``tgt`` expand now. The generator expression is evaluated
  # when CMake generates, so each file keeps the target it was called with.
  file(GENERATE OUTPUT "${{CMAKE_BINARY_DIR}}/define_${{index}}.txt"
    CONTENT "${{tgt}}=$<TARGET_PROPERTY:${{tgt}},INTERFACE_COMPILE_DEFINITIONS>\\n")
endfunction()

set(_i 0)
foreach(tgt IN LISTS _cuppa_targets)
  _cuppa_write_define("${{_i}}" "${{tgt}}")
  math(EXPR _i "${{_i}}+1")
endforeach()
""".format( packages=package_lines, targets=target_lines )


def _parse_probe_output( text: str ) -> tuple[str, list[str]]:
    line = ( text or "" ).strip()
    if "=" not in line:
        raise SCons.Errors.StopError(
                "CMake public-defines probe returned [{}]".format( line )
        )
    target, raw = line.split( "=", 1 )
    defines = []
    for piece in raw.split( ";" ):
        token = _define_token( piece )
        if token and token not in defines:
            defines.append( token )
    return target, defines


def query_cmake_public_defines( package_dir: str, env=None ) -> list[str] | None:
    """Ask CMake what consumers of this installed package are compiled with.

    Returns ``None`` when the exported targets carry no concrete defines.
    """
    packages = cmake_package_names( package_dir )
    if not packages:
        raise SCons.Errors.StopError(
                "cmake_public_defines() found no CMake package config under [{}]"
                .format( os.path.join( package_dir, "lib", "cmake" ) )
        )
    targets = imported_cmake_targets( package_dir )
    if not targets:
        raise SCons.Errors.StopError(
                "cmake_public_defines() found CMake package(s) [{}] but no "
                "imported targets under [{}]".format(
                        ", ".join( packages ),
                        os.path.join( package_dir, "lib", "cmake" ),
                )
        )
    for name in packages:
        _require_cmake_name( "package", name )
    for name in targets:
        _require_cmake_name( "target", name )

    cmake = shutil.which( "cmake" )
    if not cmake:
        raise SCons.Errors.StopError(
                "cmake_public_defines() needs cmake on PATH"
        )

    logger.info(
            "Asking CMake for public defines of [{}] ({})".format(
                    package_dir, ", ".join( targets ),
            )
    )
    with tempfile.TemporaryDirectory( prefix="cuppa-public-defines-" ) as probe:
        source = os.path.join( probe, "src" )
        build = os.path.join( probe, "build" )
        os.makedirs( source )
        with open( os.path.join( source, "CMakeLists.txt" ), "w", encoding="utf-8" ) as handle:
            handle.write( _probe_cmake_lists( packages, targets ) )
        command = [
                cmake, "-S", source, "-B", build,
                "-DCMAKE_PREFIX_PATH={}".format( os.path.abspath( package_dir ) ),
        ]
        command.extend( _probe_configure_args( env ) )
        result = subprocess.run(
                command, capture_output=True, text=True,
        )
        if result.returncode != 0:
            detail = ( result.stderr or result.stdout or "" ).strip()
            raise SCons.Errors.StopError(
                    "Asking CMake for public defines failed:\n{}".format( detail )
            )
        per_target: dict[str, list[str]] = {}
        for index in range( len( targets ) ):
            path = os.path.join( build, "define_{}.txt".format( index ) )
            try:
                with open( path, encoding="utf-8" ) as handle:
                    text = handle.read()
            except OSError as exc:
                raise SCons.Errors.StopError(
                        "CMake did not report public defines for [{}] ({})"
                        .format( targets[index], exc )
                ) from exc
            target, defines = _parse_probe_output( text )
            per_target[target] = defines

    defines = union_target_defines( per_target )
    if defines:
        logger.info( "CMake public defines: {}".format( ", ".join( defines ) ) )
    else:
        logger.info( "CMake exported no public compile defines" )
    return defines or None


def resolve_public_defines( explicit: Any, package_dir: str, env=None ) -> list[str] | None:
    """Author list, or the CMake answer when ``explicit`` is the marker.

    ``None`` publishes no field. It does not scan the install.
    """
    if isinstance( explicit, CmakePublicDefines ):
        return query_cmake_public_defines( package_dir, env )
    if explicit is None:
        return None
    return normalise_public_defines( explicit )
