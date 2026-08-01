#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest
import SCons.Errors

from cuppa.build_with_conan import (
    _companion_c_compiler,
    _map_cppstd,
    compiler_executables_for,
    compiler_executables_to_cli,
    conan_deps,
    conan_dependency,
    conan_settings_for,
    load_sconsdeps,
    merge_conan_flags,
    modules_dirs_from_sconsdeps,
    settings_to_cli,
    version_summary_from_info,
    write_transient_conanfile,
)
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


SCONSDEPS_FIXTURE = """\
conandeps = {


        "conandeps" : {
            "CPPPATH"     : ['/fake/include'],
            "LIBPATH"     : ['/fake/lib'],
            "BINPATH"     : ['/fake/bin'],
            "LIBS"        : ['fmtd', 'm'],
            "FRAMEWORKS"  : [],
            "FRAMEWORKPATH" : [],
            "CPPDEFINES"  : [],
            "CXXFLAGS"    : [],
            "CCFLAGS"     : [],
            "SHLINKFLAGS" : [],
            "LINKFLAGS"   : [],
        },



        "fmt" : {
            "CPPPATH"     : ['/fake/include'],
            "LIBPATH"     : ['/fake/lib'],
            "BINPATH"     : ['/fake/bin'],
            "LIBS"        : [],
            "FRAMEWORKS"  : [],
            "FRAMEWORKPATH" : [],
            "CPPDEFINES"  : [],
            "CXXFLAGS"    : [],
            "CCFLAGS"     : [],
            "SHLINKFLAGS" : [],
            "LINKFLAGS"   : [],
        },
        "fmt_version" : "11.1.4",

}

Return('conandeps')
"""


class FakeToolchain(object):
    def __init__( self, family='gcc', major=15, stdlib=None, binary=None ):
        self._family = family
        self._reported_version = { 'major': major }
        self._version = str( major )
        self._short_version = str( major )
        self._stdlib = stdlib
        if binary is not None:
            self._binary = binary
        elif family == 'clang':
            self._binary = 'clang++'
        else:
            self._binary = 'g++'

    def family( self ):
        return self._family

    def version( self ):
        return self._version

    def short_version( self ):
        return self._short_version

    def binary( self ):
        return self._binary

    def abi( self, env ):
        return env.get( 'stdcpp' ) or 'c++2c'

    def abi_flag( self, env ):
        return '-std={}'.format( self.abi( env ) )

    def stdlib_flag( self, env ):
        if self._stdlib:
            return '-stdlib={}'.format( self._stdlib )
        return None


class RecordingEnv( FakeEnv ):
    def __init__( self, **kwargs ):
        super().__init__( **kwargs )
        self.merged = []
        self.env_paths = {}
        self.setdefault( 'ENV', {} )

    def MergeFlags( self, flags ):
        self.merged.append( flags )

    def PrependENVPath( self, key, path ):
        self.env_paths.setdefault( key, [] ).insert( 0, path )


def test_map_cppstd_common_values():
    assert _map_cppstd( 'c++20' ) == '20'
    assert _map_cppstd( 'c++2c' ) == '26'
    assert _map_cppstd( 'cxx2c' ) == '26'
    assert _map_cppstd( '-std=c++17' ) == '17'
    assert _map_cppstd( 'gnu++20' ) == 'gnu20'


def test_companion_c_compiler_from_cxx_drivers():
    assert _companion_c_compiler( 'clang++' ) == 'clang'
    assert _companion_c_compiler( 'clang++-22' ) == 'clang-22'
    assert _companion_c_compiler( '/opt/llvm/bin/clang++' ) == '/opt/llvm/bin/clang'
    assert _companion_c_compiler( 'g++' ) == 'gcc'
    assert _companion_c_compiler( 'g++-15' ) == 'gcc-15'


def test_compiler_executables_for_clang_and_gcc():
    clang = compiler_executables_for( FakeToolchain( family='clang', major=22 ) )
    assert clang == { 'c': 'clang', 'cpp': 'clang++' }
    versioned = compiler_executables_for(
        FakeToolchain( family='clang', major=22, binary='/usr/bin/clang++-22' )
    )
    assert versioned == { 'c': '/usr/bin/clang-22', 'cpp': '/usr/bin/clang++-22' }
    gcc = compiler_executables_for( FakeToolchain( family='gcc', major=15 ) )
    assert gcc == { 'c': 'gcc', 'cpp': 'g++' }
    assert compiler_executables_for( FakeToolchain( family='msvc', major=194 ) ) is None


def test_compiler_executables_to_cli_json():
    args = compiler_executables_to_cli( { 'c': 'clang', 'cpp': 'clang++' } )
    assert args[0] == '-c'
    assert args[1] == 'tools.build:compiler_executables={"c":"clang","cpp":"clang++"}'
    assert compiler_executables_to_cli( None ) == []


def test_modules_dirs_from_sconsdeps( tmp_path ):
    pkg = tmp_path / 'p'
    include = pkg / 'include'
    lib = pkg / 'lib'
    modules = pkg / 'modules'
    include.mkdir( parents=True )
    lib.mkdir()
    modules.mkdir()
    ( modules / 'module-map.json' ).write_text( '{}\n', encoding='utf-8' )
    info = {
        'conandeps': {
            'CPPPATH': [ str( include ) ],
            'LIBPATH': [ str( lib ) ],
        },
        'mylib': {
            'CPPPATH': [ str( include ) ],
            'LIBPATH': [ str( lib ) ],
        },
    }
    found = modules_dirs_from_sconsdeps( info )
    assert found == [ str( modules ) ]


def test_modules_dirs_from_sconsdeps_absent( tmp_path ):
    include = tmp_path / 'include'
    include.mkdir()
    info = { 'conandeps': { 'CPPPATH': [ str( include ) ] } }
    assert modules_dirs_from_sconsdeps( info ) == []


def test_conan_settings_for_msvc_runtime():
    env = FakeEnv( stdcpp='c++20', target_arch='x86_64' )
    toolset = type( 'Toolset', (), { 'major': 14, 'minor': 5 } )()
    toolchain = FakeToolchain( family='cl', major=19 )
    toolchain._toolset = toolset
    toolchain._short_version = '145'
    settings = conan_settings_for( env, toolchain, 'dbg' )
    assert settings['compiler'] == 'msvc'
    assert settings['compiler.version'] == '194'
    assert settings['compiler.runtime'] == 'dynamic'
    assert settings['compiler.runtime_type'] == 'Debug'
    assert 'compiler.libcxx' not in settings


def test_conan_settings_for_gcc_debug():
    env = FakeEnv( stdcpp='c++20', target_arch='x86_64' )
    toolchain = FakeToolchain( family='gcc', major=15 )
    settings = conan_settings_for( env, toolchain, 'dbg' )
    assert settings['build_type'] == 'Debug'
    assert settings['compiler'] == 'gcc'
    assert settings['compiler.version'] == '15'
    assert settings['compiler.cppstd'] == '20'
    assert settings['compiler.libcxx'] == 'libstdc++11'


def test_conan_settings_for_clang_libcxx():
    env = FakeEnv( stdcpp='c++20', target_arch='x86_64', **{ 'clang-stdlib': 'libc++' } )
    toolchain = FakeToolchain( family='clang', major=21, stdlib='libc++' )
    settings = conan_settings_for( env, toolchain, 'rel' )
    assert settings['build_type'] == 'Release'
    assert settings['compiler'] == 'clang'
    assert settings['compiler.libcxx'] == 'libc++'


def test_settings_to_cli_sorted():
    args = settings_to_cli( { 'compiler': 'gcc', 'build_type': 'Debug' } )
    assert args == [ '-s', 'build_type=Debug', '-s', 'compiler=gcc' ]


def test_conan_deps_requires_source():
    with pytest.raises( SCons.Errors.StopError ):
        conan_deps( 'empty' )


def test_write_transient_and_version_summary( tmp_path ):
    path = write_transient_conanfile( str( tmp_path / 'conanfile.txt' ), [ 'fmt/[*]' ] )
    text = open( path, encoding='utf-8' ).read()
    assert 'fmt/[*]' in text
    assert 'SConsDeps' in text
    assert version_summary_from_info( { 'fmt_version': '11.1.4', 'conandeps': {} } ) == 'fmt=11.1.4'


def test_merge_conan_flags_skips_binpath_and_sets_runtime( monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Linux' )
    env = RecordingEnv()
    merge_conan_flags( env, {
        'CPPPATH': ['/i'],
        'LIBPATH': ['/l'],
        'BINPATH': ['/b'],
        'LIBS': ['fmtd'],
        'CXXFLAGS': [],
    } )
    assert env.merged == [ { 'CPPPATH': ['/i'], 'LIBPATH': ['/l'], 'LIBS': ['fmtd'] } ]
    assert env.env_paths['PATH'] == ['/b']
    assert env.env_paths['LD_LIBRARY_PATH'] == ['/l']


def test_load_and_apply_fixture_via_generators_folder( tmp_path, monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Linux' )
    install = tmp_path / 'install'
    install.mkdir()
    ( install / 'SConscript_conandeps' ).write_text( SCONSDEPS_FIXTURE, encoding='utf-8' )

    Dep = conan_deps( name='conan', generators_folder=str( install ) )
    env = RecordingEnv(
            sconstruct_dir=str( tmp_path ),
            dependencies_root=str( tmp_path / 'dl' ),
            offline=False,
            stdcpp='c++20',
            target_arch='x86_64',
    )
    dep = Dep.create( env )
    dep( env, FakeToolchain(), 'dbg' )

    assert env.merged
    assert env.merged[0]['CPPPATH'] == ['/fake/include']
    assert env.merged[0]['LIBS'] == ['fmtd', 'm']
    assert dep.version() == 'fmt=11.1.4'
    assert dep.repository() == 'conan'


def test_missing_sconsdeps_stop_error( tmp_path ):
    empty = tmp_path / 'empty'
    empty.mkdir()
    Dep = conan_deps( name='conan', generators_folder=str( empty ) )
    env = RecordingEnv( sconstruct_dir=str( tmp_path ) )
    dep = Dep.create( env )
    with pytest.raises( SCons.Errors.StopError ):
        dep( env, FakeToolchain(), 'dbg' )


def test_conan_dependency_default_requires():
    Dep = conan_dependency( 'fmt' )
    assert Dep.name() == 'fmt'
    assert Dep._requires == [ 'fmt/[*]' ]


def test_offline_install_fails_without_conan( tmp_path, monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_with_conan._find_conan_executable', lambda: None )
    conanfile = tmp_path / 'conanfile.txt'
    conanfile.write_text( '[requires]\nfmt/[*]\n\n[generators]\nSConsDeps\n', encoding='utf-8' )
    Dep = conan_deps( name='conan', conanfile=str( conanfile ) )
    env = RecordingEnv(
            sconstruct_dir=str( tmp_path ),
            dependencies_root=str( tmp_path / 'dl' ),
            offline=True,
            stdcpp='c++20',
            target_arch='x86_64',
    )
    dep = Dep.create( env )
    with pytest.raises( SCons.Errors.StopError, match='Conan CLI not found' ):
        dep( env, FakeToolchain(), 'dbg' )


def test_load_sconsdeps_direct( tmp_path ):
    install = tmp_path / 'inst'
    install.mkdir()
    ( install / 'SConscript_conandeps' ).write_text( SCONSDEPS_FIXTURE, encoding='utf-8' )
    info = load_sconsdeps( str( install ) )
    assert 'conandeps' in info
    assert info['fmt_version'] == '11.1.4'
