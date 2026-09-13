#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import shlex

import pytest

from cuppa.buildsys import cmake


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
            generator=False,
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
            generator=False,
            extra_defines={ 'BUILD_TESTING': False, 'ENABLE_FOO': True },
    )
    assert '-DCMAKE_BUILD_TYPE=RelWithDebInfo' in args
    assert '-DBUILD_TESTING=OFF' in args
    assert '-DENABLE_FOO=ON' in args


def test_cmake_configure_args_omits_unmapped_stdcpp():
    args = cmake.cmake_configure_args(
            _env( 'dbg', stdcpp='c++latest' ),
            build_dir='out',
            generator=False,
    )
    assert not any( a.startswith( '-DCMAKE_CXX_STANDARD=' ) for a in args )


def test_cmake_configure_args_can_disable_pieces():
    args = cmake.cmake_configure_args(
            _env( 'dbg' ),
            build_dir='out',
            generator=False,
            include_build_type=False,
            include_cxx_compiler=False,
            cxx_standard=False,
    )
    assert args == [ '-B', 'out' ]


def test_resolve_cmake_generator_auto_ninja( monkeypatch ):
    monkeypatch.setattr( 'shutil.which', lambda name: '/usr/bin/ninja' if name == 'ninja' else None )
    assert cmake.resolve_cmake_generator( None ) == 'Ninja'
    args = cmake.cmake_configure_args(
            _env( 'dbg' ),
            build_dir='out',
            include_build_type=False,
            include_cxx_compiler=False,
            cxx_standard=False,
    )
    assert args == [ '-B', 'out', '-G', 'Ninja' ]


def test_resolve_cmake_generator_auto_without_ninja( monkeypatch ):
    monkeypatch.setattr( 'shutil.which', lambda name: None )
    assert cmake.resolve_cmake_generator( None ) is None
    args = cmake.cmake_configure_args(
            _env( 'dbg' ),
            build_dir='out',
            include_build_type=False,
            include_cxx_compiler=False,
            cxx_standard=False,
    )
    assert args == [ '-B', 'out' ]


def test_resolve_cmake_generator_false_omits():
    assert cmake.resolve_cmake_generator( False ) is None
    assert cmake.resolve_cmake_generator( 'Unix Makefiles' ) == 'Unix Makefiles'


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


def test_remove_empty_dirs_explicit_names( tmp_path ):
    parent = tmp_path / 'third_party'
    parent.mkdir()
    empty = parent / 'grpc-proto'
    empty.mkdir()
    populated = parent / 'upb'
    populated.mkdir()
    ( populated / 'file.c' ).write_text( 'x\n' )
    other_empty = parent / 'abseil-cpp'
    other_empty.mkdir()

    removed = cmake.remove_empty_dirs(
            parent,
            names=[ 'grpc-proto', 'upb', 'never-created', 'googleapis' ],
    )
    assert removed == [ 'grpc-proto' ]
    assert not empty.exists()
    assert other_empty.exists()
    assert populated.exists()


def test_remove_empty_dirs_all_empty_children( tmp_path ):
    parent = tmp_path / 'third_party'
    parent.mkdir()
    ( parent / 'grpc-proto' ).mkdir()
    ( parent / 'abseil-cpp' ).mkdir()
    populated = parent / 'upb'
    populated.mkdir()
    ( populated / 'file.c' ).write_text( 'x\n' )

    removed = cmake.remove_empty_dirs( parent )
    assert removed == [ 'abseil-cpp', 'grpc-proto' ]
    assert populated.exists()
    assert not ( parent / 'grpc-proto' ).exists()


def test_remove_empty_dirs_empty_names_list( tmp_path ):
    parent = tmp_path / 'third_party'
    parent.mkdir()
    ( parent / 'grpc-proto' ).mkdir()
    assert cmake.remove_empty_dirs( parent, names=[] ) == []
    assert ( parent / 'grpc-proto' ).exists()


def test_gitmodules_paths_and_child_names( tmp_path ):
    repo = tmp_path / 'src'
    third_party = repo / 'third_party'
    third_party.mkdir( parents=True )
    gitmodules = repo / '.gitmodules'
    gitmodules.write_text(
            '[submodule "third_party/grpc-proto"]\n'
            '\tpath = third_party/grpc-proto\n'
            '\turl = https://example.com/grpc-proto.git\n'
            '[submodule "third_party/cares/cares"]\n'
            '\tpath = third_party/cares/cares\n'
            '\turl = https://example.com/cares.git\n'
            '[submodule "third_party/abseil-cpp"]\n'
            'path=third_party/abseil-cpp\n'
    )
    assert cmake.gitmodules_paths( gitmodules ) == [
            'third_party/grpc-proto',
            'third_party/cares/cares',
            'third_party/abseil-cpp',
    ]
    assert cmake.gitmodules_child_names( third_party, gitmodules ) == [
            'grpc-proto',
            'abseil-cpp',
    ]


def test_remove_empty_dirs_gitmodules_true( tmp_path ):
    repo = tmp_path / 'src'
    third_party = repo / 'third_party'
    third_party.mkdir( parents=True )
    ( repo / '.gitmodules' ).write_text(
            '[submodule "third_party/grpc-proto"]\n'
            '\tpath = third_party/grpc-proto\n'
            '[submodule "third_party/abseil-cpp"]\n'
            '\tpath = third_party/abseil-cpp\n'
    )
    ( third_party / 'grpc-proto' ).mkdir()
    ( third_party / 'abseil-cpp' ).mkdir()
    stray = third_party / 'not-a-submodule'
    stray.mkdir()
    populated = third_party / 'upb'
    populated.mkdir()
    ( populated / 'file.c' ).write_text( 'x\n' )

    removed = cmake.remove_empty_dirs( third_party, gitmodules=True )
    assert removed == [ 'grpc-proto', 'abseil-cpp' ]
    assert stray.exists()
    assert populated.exists()


def test_remove_empty_dirs_names_overrides_gitmodules( tmp_path ):
    repo = tmp_path / 'src'
    third_party = repo / 'third_party'
    third_party.mkdir( parents=True )
    ( repo / '.gitmodules' ).write_text(
            '[submodule "third_party/grpc-proto"]\n'
            '\tpath = third_party/grpc-proto\n'
            '[submodule "third_party/abseil-cpp"]\n'
            '\tpath = third_party/abseil-cpp\n'
    )
    ( third_party / 'grpc-proto' ).mkdir()
    ( third_party / 'abseil-cpp' ).mkdir()

    removed = cmake.remove_empty_dirs(
            third_party,
            names=[ 'grpc-proto' ],
            gitmodules=True,
    )
    assert removed == [ 'grpc-proto' ]
    assert ( third_party / 'abseil-cpp' ).exists()


def test_cmake_prefix_path_joins_with_semicolon():
    assert cmake.cmake_prefix_path( '/a', None, '/b', '' ) == '/a;/b'
    assert cmake.cmake_prefix_path() == ''


def test_cmake_prefix_path_for_uses_package_dirs( tmp_path ):
    from types import SimpleNamespace

    class Package:
        def __init__( self, root ):
            self._root = root

        def package_dir( self ):
            return str( self._root )

    class Wrapper:
        def __init__( self, package ):
            self._package = package

        def package( self ):
            return self._package

    a = tmp_path / 'a'
    b = tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    packages = {
            'a': Wrapper( Package( a ) ),
            'b': Wrapper( Package( b ) ),
    }
    env = SimpleNamespace( BuildWith=lambda name: packages[name] )
    assert cmake.cmake_prefix_path_for( env, 'a', 'b' ) == '{};{}'.format( a, b )


def test_cmake_install_rpath_defines_default_build_tree_safe():
    defines = cmake.cmake_install_rpath_defines(
            extra_install=[ '/protobuf/lib' ],
            extra_build=[ '/protobuf/lib' ],
    )
    assert defines == {
            'CMAKE_BUILD_WITH_INSTALL_RPATH': False,
            'CMAKE_INSTALL_RPATH': '$ORIGIN/../lib;/protobuf/lib',
            'CMAKE_BUILD_RPATH': '$ORIGIN;/protobuf/lib',
    }


def test_cmake_install_rpath_defines_can_opt_into_install_rpath_during_build():
    defines = cmake.cmake_install_rpath_defines(
            build_with_install_rpath=True,
            build_rpath=None,
    )
    assert defines['CMAKE_BUILD_WITH_INSTALL_RPATH'] is True
    assert defines['CMAKE_INSTALL_RPATH'] == '$ORIGIN/../lib'
    assert 'CMAKE_BUILD_RPATH' not in defines
