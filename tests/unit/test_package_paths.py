#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for BuildWith package path helpers."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from cuppa.package_managers import package_paths


pytestmark = pytest.mark.unit


class _Package:
    def __init__( self, root: Path, version: str ):
        self._root = root
        self._version = version

    def package_dir( self ):
        return str( self._root )

    def version( self ):
        return self._version

    def lib_dir( self ):
        return str( self._root / 'lib' )


class _Wrapper:
    def __init__( self, package ):
        self._package = package

    def package( self ):
        return self._package


def _env_with_packages( mapping ):
    def build_with( name ):
        if name not in mapping:
            raise KeyError( name )
        return mapping[name]
    return SimpleNamespace( BuildWith=build_with )


def test_package_dir_version_bin_lib( tmp_path: Path ):
    root = tmp_path / 'protobuf' / '36.1'
    ( root / 'bin' ).mkdir( parents=True )
    ( root / 'lib' ).mkdir()
    env = _env_with_packages( {
            'protobuf': _Wrapper( _Package( root, '36.1' ) ),
    } )
    assert package_paths.package_dir( env, 'protobuf' ) == str( root )
    assert package_paths.package_version( env, 'protobuf' ) == '36.1'
    assert package_paths.package_lib( env, 'protobuf' ) == str( root / 'lib' )
    assert package_paths.package_bin( env, 'protobuf' ) == str( root / 'bin' )
    assert package_paths.package_bin( env, 'protobuf', 'protoc' ) == str(
            root / 'bin' / 'protoc'
    )


def test_cmake_prefix_path_for_preserves_order( tmp_path: Path ):
    from cuppa.buildsys import cmake

    otel = tmp_path / 'otel'
    grpc = tmp_path / 'grpc'
    proto = tmp_path / 'proto'
    for path in ( otel, grpc, proto ):
        path.mkdir()
    env = _env_with_packages( {
            'opentelemetry_cpp': _Wrapper( _Package( otel, '1.28.0' ) ),
            'grpc': _Wrapper( _Package( grpc, '1.84.0' ) ),
            'protobuf': _Wrapper( _Package( proto, '36.1' ) ),
    } )
    assert cmake.cmake_prefix_path_for(
            env, 'opentelemetry_cpp', 'grpc', 'protobuf',
    ) == ';'.join( [ str( otel ), str( grpc ), str( proto ) ] )


def test_package_bin_rejects_bad_name():
    import SCons.Errors

    env = _env_with_packages( {} )
    with pytest.raises( SCons.Errors.StopError, match="name" ):
        package_paths.package_dir( env, 12 )


def test_package_dir_accepts_dependency_object( tmp_path: Path ):
    root = tmp_path / 'grpc' / '1.84.0'
    root.mkdir( parents=True )
    wrapper = _Wrapper( _Package( root, '1.84.0' ) )
    wrapper.name = lambda: 'grpc'
    env = _env_with_packages( { 'grpc': wrapper } )
    assert package_paths.package_dir( env, wrapper ) == str( root )
    assert package_paths.package_bin( env, wrapper, 'grpc_cpp_plugin' ) == str(
            root / 'bin' / 'grpc_cpp_plugin'
    )
