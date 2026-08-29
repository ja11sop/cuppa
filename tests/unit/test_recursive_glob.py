
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.recursive_glob import glob as recursive_glob


pytestmark = pytest.mark.unit


def test_recursive_glob_finds_nested_matches( tmp_path ):
    scenarios = tmp_path / 'test' / 'scenarios'
    ( scenarios / 'deep' ).mkdir( parents=True )
    ( scenarios / 'top.ebs' ).write_text( 'top' )
    ( scenarios / 'deep' / 'nested.ebs' ).write_text( 'nested' )
    ( scenarios / 'deep' / 'skip.txt' ).write_text( 'no' )

    matches = recursive_glob( str( scenarios ), '*.ebs' )
    names = sorted( os.path.basename( path ) for path in matches )
    assert names == [ 'nested.ebs', 'top.ebs' ]


def test_recursive_glob_missing_or_empty_start_returns_empty( tmp_path ):
    missing = tmp_path / 'scenarios_output'
    assert recursive_glob( str( missing ), '*.ebs' ) == []

    empty = tmp_path / 'empty'
    empty.mkdir()
    assert recursive_glob( str( empty ), '*.ebs' ) == []


def test_recursive_glob_exclude_dirs_skips_named_folders( tmp_path ):
    root = tmp_path / 'tree'
    ( root / 'keep' ).mkdir( parents=True )
    ( root / 'build' ).mkdir()
    ( root / 'keep' / 'a.cpp' ).write_text( 'a' )
    ( root / 'build' / 'b.cpp' ).write_text( 'b' )

    matches = recursive_glob( str( root ), '*.cpp', exclude_dirs_pattern='build' )
    names = [ os.path.basename( path ) for path in matches ]
    assert names == [ 'a.cpp' ]


def test_recursive_glob_discard_pattern_drops_subdir( tmp_path ):
    root = tmp_path / 'tree'
    ( root / 'good' ).mkdir( parents=True )
    ( root / 'bad' ).mkdir()
    ( root / 'root.cpp' ).write_text( 'root' )
    ( root / 'good' / 'ok.cpp' ).write_text( 'ok' )
    ( root / 'bad' / 'CMakeLists.txt' ).write_text( 'cmake' )
    ( root / 'bad' / 'hidden.cpp' ).write_text( 'hidden' )

    matches = recursive_glob(
            str( root ),
            '*.cpp',
            discard_pattern='CMakeLists.txt',
    )
    names = sorted( os.path.basename( path ) for path in matches )
    assert names == [ 'ok.cpp', 'root.cpp' ]
