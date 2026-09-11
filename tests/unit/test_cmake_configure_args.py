#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import shlex

import pytest

from cuppa.utility import cmake


pytestmark = pytest.mark.unit


class _FakeToolchain(object):
    def binary( self ):
        return '/opt/gcc/bin/g++'


class _FakeVariant(object):
    def __init__( self, name ):
        self._name = name

    def name( self ):
        return self._name


def _env( variant='dbg', stdcpp=None, cc='/opt/gcc/bin/gcc', cxx=None ):
    data = {
            'toolchain': _FakeToolchain(),
            'variant': _FakeVariant( variant ),
            'stdcpp': stdcpp,
            'CC': cc,
    }
    if cxx is not None:
        data['CXX'] = cxx
    return data


def test_cmake_build_type_for_variant():
    assert cmake.cmake_build_type_for_variant( 'dbg' ) == 'Debug'
    assert cmake.cmake_build_type_for_variant( 'rel' ) == 'Release'
    assert cmake.cmake_build_type_for_variant( 'cov' ) == 'RelWithDebInfo'
    assert cmake.cmake_build_type_for_variant( 'benchmark' ) is None
    assert cmake.cmake_build_type_for_variant( None ) is None


def test_cmake_cxx_standard_for_stdcpp():
    assert cmake.cmake_cxx_standard_for_stdcpp( 'c++20' ) == 20
    assert cmake.cmake_cxx_standard_for_stdcpp( 'c++2c' ) == 26
    assert cmake.cmake_cxx_standard_for_stdcpp( 'c++latest' ) is None
    assert cmake.cmake_cxx_standard_for_stdcpp( None ) is None


def test_cmake_configure_args_minimal_dbg():
    args = cmake.cmake_configure_args(
            _env( 'dbg' ),
            build_dir='_build/gcc_dbg',
            generator='Ninja',
            extra_defines={ 'WIDGET_BUILD_TESTS': 'OFF' },
    )
    assert args == [
            '-B', '_build/gcc_dbg',
            '-G', 'Ninja',
            '-DCMAKE_BUILD_TYPE=Debug',
            '-DCMAKE_CXX_COMPILER=/opt/gcc/bin/g++',
            '-DWIDGET_BUILD_TESTS=OFF',
    ]


def test_cmake_configure_args_install_prefix_and_source():
    args = cmake.cmake_configure_args(
            _env( 'rel', stdcpp='c++23' ),
            source_dir='.',
            build_dir='cmake-out',
            install_prefix='/tmp/final/installed',
            c_compiler=True,
    )
    assert args[:4] == [ '-S', '.', '-B', 'cmake-out' ]
    assert '-DCMAKE_BUILD_TYPE=Release' in args
    assert '-DCMAKE_CXX_COMPILER=/opt/gcc/bin/g++' in args
    assert '-DCMAKE_C_COMPILER=/opt/gcc/bin/gcc' in args
    assert '-DCMAKE_INSTALL_PREFIX=/tmp/final/installed' in args
    assert '-DCMAKE_CXX_STANDARD=23' in args


def test_cmake_configure_args_cov_and_bool_defines():
    args = cmake.cmake_configure_args(
            _env( 'cov' ),
            build_dir='out',
            extra_defines={ 'BUILD_TESTING': False, 'ENABLE_FOO': True },
    )
    assert '-DCMAKE_BUILD_TYPE=RelWithDebInfo' in args
    assert '-DBUILD_TESTING=OFF' in args
    assert '-DENABLE_FOO=ON' in args


def test_cmake_configure_args_omits_unmapped_stdcpp():
    args = cmake.cmake_configure_args(
            _env( 'dbg', stdcpp='c++latest' ),
            build_dir='out',
    )
    assert not any( a.startswith( '-DCMAKE_CXX_STANDARD=' ) for a in args )


def test_cmake_configure_args_can_disable_pieces():
    args = cmake.cmake_configure_args(
            _env( 'dbg' ),
            build_dir='out',
            include_build_type=False,
            include_cxx_compiler=False,
            cxx_standard=False,
    )
    assert args == [ '-B', 'out' ]


def test_cmake_configure_command_quotes():
    command = cmake.cmake_configure_command(
            _env( 'dbg' ),
            build_dir='/tmp/build dir',
            generator='Ninja',
    )
    assert command.startswith( 'cmake ' )
    tokens = shlex.split( command )
    assert tokens[0] == 'cmake'
    assert '-B' in tokens
    assert '/tmp/build dir' in tokens
    assert '-G' in tokens
    assert 'Ninja' in tokens
