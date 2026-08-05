#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for archive product enumeration and Boost storage_clean paths."""

import os

import pytest

from cuppa.core.dependency_removal import enumerate_archive_product_dirs
from cuppa.dependencies.boost.library_naming import (
    b2_build_dir_toolset_token,
    b2_toolset_family_label,
    b2_toolset_family_token,
    directory_from_abi_flag,
    find_b2_build_dir_products,
    selection_tool_variant_tag,
    stage_directory,
    variant_name,
)
from cuppa.dependencies.build_with_boost import Boost


pytestmark = pytest.mark.unit


class _FakeToolchain( object ):
    def __init__( self, name='gcc153', family='gcc', major=15, minor=3 ):
        self._name = name
        self._family = family
        self._reported_version = { 'major': major, 'minor': minor }

    def name( self ):
        return self._name

    def toolset_name( self ):
        return self._family

    def version( self ):
        return '{}.{}'.format(
                self._reported_version['major'], self._reported_version['minor']
        )

    def cxx_version( self ):
        return str( self._reported_version['major'] )

    def abi_flag( self, env ):
        return env.get( 'abi_flag', '-std=c++2c' )


def test_variant_name_maps_dbg_to_debug():
    assert variant_name( 'dbg' ) == 'debug'
    assert variant_name( 'rel' ) == 'release'


def test_stage_directory_includes_abi_and_selection():
    toolchain = _FakeToolchain( 'gcc153' )
    path = stage_directory( toolchain, 'debug', 'x86_64', '-std=c++2c' )
    assert path == os.path.join( 'build.c++2c', 'gcc153', 'debug', 'x86_64' )


def test_directory_from_abi_flag_splits_value():
    assert directory_from_abi_flag( '-std=c++2c' ) == 'c++2c'
    assert directory_from_abi_flag( '' ) == ''


def test_b2_build_dir_toolset_token_linux_clang():
    toolchain = _FakeToolchain( 'clang211', family='clang', major=21, minor=1 )
    token = b2_build_dir_toolset_token( toolchain )
    assert token in ( 'clang-linux-21', 'clang-21', 'clang-darwin-21' )


def test_selection_tool_variant_tag():
    assert selection_tool_variant_tag(
            _FakeToolchain( 'clang211' ), 'dbg', 'x86_64'
    ) == 'clang211_dbg_x86_64'


def test_b2_toolset_family_token_strips_patch():
    assert b2_toolset_family_token( 'gcc-15' ) == 'gcc-15'
    assert b2_toolset_family_token( 'gcc-15.3' ) == 'gcc-15'
    assert b2_toolset_family_token( 'clang-linux-21.1' ) == 'clang-linux-21'
    assert b2_toolset_family_label( 'gcc-15.3' ) == 'gcc-15*'
    assert b2_toolset_family_label( 'gcc-15', 'debug' ) == 'gcc-15*/debug'


def test_find_b2_build_dir_products_prefers_variant_leaf( tmp_path ):
    bin_root = tmp_path / 'bin.c++2c'
    clang_debug = bin_root / 'boost' / 'bin.v2' / 'libs' / 'test' / 'clang-linux-21' / 'debug'
    clang_build = bin_root / 'boost' / 'bin.v2' / 'libs' / 'test' / 'build' / 'clang-linux-21'
    gcc_debug = bin_root / 'boost' / 'bin.v2' / 'libs' / 'test' / 'gcc-15' / 'debug'
    clang_debug.mkdir( parents=True )
    clang_build.mkdir( parents=True )
    gcc_debug.mkdir( parents=True )

    found = find_b2_build_dir_products( str( bin_root ), 'clang-linux-21', 'debug' )
    abs_found = { os.path.abspath( p ) for p in found }
    assert os.path.abspath( str( clang_debug ) ) in abs_found
    # Toolset dir without a debug child must not be selected for a debug clean.
    assert os.path.abspath( str( clang_build ) ) not in abs_found
    assert os.path.abspath( str( gcc_debug ) ) not in abs_found


def test_find_b2_variant_clean_skips_other_variant_parents( tmp_path ):
    """Release clean must not fall back to a toolset dir that only has debug products."""
    bin_root = tmp_path / 'bin.c++2c'
    parent = bin_root / 'boost' / 'bin.v2' / 'check' / 'predef' / 'clang-linux-21'
    ( parent / 'debug' ).mkdir( parents=True )
    found = find_b2_build_dir_products( str( bin_root ), 'clang-linux-21', 'release' )
    assert found == []
    found_debug = find_b2_build_dir_products( str( bin_root ), 'clang-linux-21', 'debug' )
    assert [ os.path.abspath( p ) for p in found_debug ] == [
            os.path.abspath( str( parent / 'debug' ) )
    ]


def test_enumerate_archive_product_dirs( tmp_path ):
    home = tmp_path / 'clean'
    dbg = home / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    rel = home / 'build.c++2c' / 'gcc153' / 'release' / 'x86_64'
    bindir = home / 'bin.c++2c'
    gcc_bin = bindir / 'boost' / 'bin.v2' / 'libs' / 'system' / 'gcc-15' / 'debug'
    gcc_sibling = bindir / 'boost' / 'bin.v2' / 'libs' / 'filesystem' / 'gcc-15' / 'debug'
    dbg.mkdir( parents=True )
    rel.mkdir( parents=True )
    gcc_bin.mkdir( parents=True )
    gcc_sibling.mkdir( parents=True )
    ( home / 'boost' ).mkdir()

    found = enumerate_archive_product_dirs( str( home ) )
    assert all( isinstance( unit, dict ) for unit in found )
    stage_paths = {
            os.path.abspath( p )
            for unit in found if unit.get( 'kind' ) == 'stage'
            for p in unit['paths']
    }
    assert os.path.abspath( str( dbg ) ) in stage_paths
    assert any( 'release' in p for p in stage_paths )

    bin_units = [ unit for unit in found if unit.get( 'kind' ) == 'bin_toolset' ]
    assert len( bin_units ) == 1
    assert bin_units[0]['tool_variant'] == 'gcc-15*'
    assert bin_units[0]['path'].rstrip( '/\\' ).endswith( 'bin.c++2c' )
    assert len( bin_units[0]['paths'] ) == 2

    stage_units = [ unit for unit in found if unit.get( 'kind' ) == 'stage' ]
    assert any( unit['tool_variant'] == 'gcc153/debug/x86_64' for unit in stage_units )
    assert all( unit['path'].rstrip( '/\\' ).endswith( 'build.c++2c' ) for unit in stage_units )


def test_enumerate_skips_empty_bin_root_husk( tmp_path ):
    home = tmp_path / 'clean'
    ( home / 'bin.c++2c' / 'boost' / 'bin.v2' / 'libs' / 'system' ).mkdir( parents=True )
    ( home / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64' ).mkdir( parents=True )
    found = enumerate_archive_product_dirs( str( home ) )
    assert all( unit.get( 'kind' ) != 'bin_root' for unit in found )
    assert not any( unit.get( 'kind' ) == 'bin_toolset' for unit in found )
    assert any( unit.get( 'kind' ) == 'stage' for unit in found )


def test_enumerate_folds_b2_patch_toolsets_into_family( tmp_path ):
    home = tmp_path / 'clean'
    bindir = home / 'bin.c++2c'
    ( bindir / 'boost' / 'bin.v2' / 'libs' / 'a' / 'gcc-15' / 'debug' ).mkdir( parents=True )
    ( bindir / 'boost' / 'bin.v2' / 'libs' / 'b' / 'gcc-15.3' / 'release' ).mkdir( parents=True )
    found = enumerate_archive_product_dirs( str( home ) )
    bin_units = [ unit for unit in found if unit.get( 'kind' ) == 'bin_toolset' ]
    assert len( bin_units ) == 1
    assert bin_units[0]['tool_variant'] == 'gcc-15*'
    assert len( bin_units[0]['paths'] ) == 2


def test_find_b2_prunes_nested_toolset_and_variant( tmp_path ):
    """Parent toolset dir + variant child must not both be returned."""
    bin_root = tmp_path / 'bin.c++2c'
    parent = (
            bin_root / 'boost' / 'bin.v2' / 'libs' / 'config' / 'checks'
            / 'architecture' / 'clang-linux-21'
    )
    child = parent / 'debug'
    child.mkdir( parents=True )
    ( parent / 'some_obj.o' ).write_text( 'x', encoding='utf-8' )

    found = find_b2_build_dir_products( str( bin_root ), 'clang-linux-21', 'debug' )
    abs_found = [ os.path.abspath( p ) for p in found ]
    assert abs_found == [ os.path.abspath( str( child ) ) ]


def test_boost_storage_clean_folds_bin_paths_into_one_target( tmp_path ):
    extract = tmp_path / 'boost_extract'
    home = extract / 'clean'
    stage = home / 'build.c++2c' / 'clang211' / 'debug' / 'x86_64'
    bindir = home / 'bin.c++2c'
    arch = (
            bindir / 'boost' / 'bin.v2' / 'libs' / 'config' / 'checks'
            / 'architecture' / 'clang-linux-21'
    )
    ( arch / 'debug' ).mkdir( parents=True )
    stage.mkdir( parents=True )
    ( home / 'boost' ).mkdir()
    ( home / 'boost' / 'version.hpp' ).write_text(
            '#define BOOST_VERSION 109100\n',
            encoding='utf-8',
    )

    boost = Boost.__new__( Boost )
    boost._location = type( 'Loc', (), {
        'local': lambda self: str( home ),
        'base_local': lambda self: str( extract ),
        '_base_local_directory': str( extract ),
    } )()
    boost.values = { 'home': str( home ), 'version': '1.91.0', 'full_version': '1_91_0' }

    toolchain = _FakeToolchain( 'clang211', family='clang', major=21, minor=1 )
    env = { 'abi_flag': '-std=c++2c', 'target_arch': 'x86_64', 'toolchain': toolchain }
    selection = {
        'toolchain': toolchain,
        'variant': 'dbg',
        'target_arch': 'x86_64',
    }
    result = boost.storage_clean( env, selection )
    assert len( result['targets'] ) == 2
    bin_targets = [ t for t in result['targets'] if t['label'].endswith( 'bin.c++2c' ) ]
    stage_targets = [ t for t in result['targets'] if t['label'].endswith( 'build.c++2c' ) ]
    assert len( bin_targets ) == 1
    assert len( stage_targets ) == 1
    assert bin_targets[0]['tool_variant'] == 'clang-linux-21*/debug'
    assert stage_targets[0]['tool_variant'] == 'clang211/debug/x86_64'
    # Nested parent must not appear alongside the variant leaf.
    assert len( bin_targets[0]['paths'] ) == 1
    assert bin_targets[0]['paths'][0].endswith( os.path.join( 'clang-linux-21', 'debug' ) )


def test_boost_storage_clean_returns_stage_and_toolset_bin_targets( tmp_path ):
    extract = tmp_path / 'boost_extract'
    home = extract / 'clean'
    stage = home / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    bindir = home / 'bin.c++2c'
    gcc_bin = bindir / 'boost' / 'bin.v2' / 'libs' / 'system' / 'gcc-15' / 'debug'
    clang_bin = bindir / 'boost' / 'bin.v2' / 'libs' / 'system' / 'clang-linux-21' / 'debug'
    stage.mkdir( parents=True )
    gcc_bin.mkdir( parents=True )
    clang_bin.mkdir( parents=True )
    ( home / 'boost' ).mkdir()
    ( home / 'boost' / 'version.hpp' ).write_text(
            '#define BOOST_VERSION 109100\n',
            encoding='utf-8',
    )

    boost = Boost.__new__( Boost )
    boost._location = type( 'Loc', (), {
        'local': lambda self: str( home ),
        'base_local': lambda self: str( extract ),
        '_base_local_directory': str( extract ),
    } )()
    boost.values = { 'home': str( home ), 'version': '1.91.0', 'full_version': '1_91_0' }

    env = { 'abi_flag': '-std=c++2c', 'target_arch': 'x86_64', 'toolchain': _FakeToolchain() }
    selection = {
        'toolchain': _FakeToolchain(),
        'variant': 'dbg',
        'target_arch': 'x86_64',
    }
    result = boost.storage_clean( env, selection )
    assert result is not None
    assert result['extract'] == str( extract )
    abs_paths = [ os.path.abspath( p ) for p in result['paths'] ]
    assert os.path.abspath( str( stage ) ) in abs_paths
    assert os.path.abspath( str( gcc_bin ) ) in abs_paths
    assert os.path.abspath( str( clang_bin ) ) not in abs_paths
    assert os.path.abspath( str( bindir ) ) not in abs_paths

    labels = [ target['label'] for target in result['targets'] ]
    assert any( label.endswith( 'build.c++2c' ) for label in labels )
    assert any( label.endswith( 'bin.c++2c' ) for label in labels )
    by_label = { target['label']: target['tool_variant'] for target in result['targets'] }
    assert by_label[ next( l for l in labels if l.endswith( 'build.c++2c' ) ) ] == 'gcc153/debug/x86_64'
    assert by_label[ next( l for l in labels if l.endswith( 'bin.c++2c' ) ) ] == 'gcc-15*/debug'


def test_boost_storage_clean_empty_when_nothing_built( tmp_path ):
    extract = tmp_path / 'boost_extract'
    home = extract / 'clean'
    home.mkdir( parents=True )
    ( home / 'boost' ).mkdir()
    ( home / 'boost' / 'version.hpp' ).write_text(
            '#define BOOST_VERSION 109100\n',
            encoding='utf-8',
    )

    boost = Boost.__new__( Boost )
    boost._location = type( 'Loc', (), {
        'local': lambda self: str( home ),
        'base_local': lambda self: str( extract ),
    } )()
    boost.values = { 'home': str( home ) }

    env = { 'abi_flag': '-std=c++2c', 'target_arch': 'x86_64' }
    selection = {
        'toolchain': _FakeToolchain(),
        'variant': 'dbg',
        'target_arch': 'x86_64',
    }
    result = boost.storage_clean( env, selection )
    assert result['paths'] == []
    assert result['targets'] == []
    assert result['extract'] == str( extract )


def test_boost_location_id_accepts_boost_patched_alias():
    from cuppa.dependencies.boost.version_and_location import boost_location_id

    class Env( object ):
        def __init__( self, options ):
            self._options = options

        def get_option( self, name ):
            return self._options.get( name )

        def __getitem__( self, key ):
            return { 'thirdparty': None }[key]

    assert boost_location_id( Env( { 'boost-patched': True } ) )[3]
    assert boost_location_id( Env( { 'boost-patch-boost-test': True } ) )[3]
    assert not boost_location_id( Env( {} ) )[3]
