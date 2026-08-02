import os

import pytest

from cuppa.core import build_layout


pytestmark = pytest.mark.unit


def test_sanitise_abi_makes_plus_path_safe():
    assert build_layout.sanitise_abi( 'c++2c' ) == 'cxx2c'
    assert build_layout.sanitise_abi( 'c++20' ) == 'cxx20'


def test_tool_variant_dir_joins_the_four_segments():
    assert build_layout.tool_variant_dir( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) == os.path.join(
        'gcc15', 'dbg', 'x86_64', 'cxx2c'
    )


def test_discover_build_variants_finds_nested_and_root_layouts( tmp_path ):
    root = tmp_path / '_build'
    nested = root / 'test' / 'orders' / 'gcc15' / 'dbg' / 'x86_64' / 'cxx2c'
    ( nested / 'working' ).mkdir( parents=True )
    ( nested / 'final' ).mkdir()
    top = root / 'clang21' / 'rel' / 'x86_64' / 'cxx20'
    ( top / 'working' ).mkdir( parents=True )

    selected = [ os.path.join( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ]
    found = build_layout.discover_build_variants( str( root ), selected )

    assert len( found ) == 2
    by_variant = { entry.tool_variant: entry for entry in found }

    nested_entry = by_variant[ os.path.join( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ]
    assert nested_entry.sconscript == os.path.join( 'test', 'orders' )
    assert nested_entry.selected is True

    top_entry = by_variant[ os.path.join( 'clang21', 'rel', 'x86_64', 'cxx20' ) ]
    assert top_entry.sconscript == '.'
    assert top_entry.selected is False


def test_paths_ending_with_finds_every_matching_suffix( tmp_path ):
    root = tmp_path / '_build'
    first = root / 'a' / 'gcc' / 'dbg' / 'x86_64' / 'cxx2c'
    second = root / 'b' / 'gcc' / 'dbg' / 'x86_64' / 'cxx2c'
    other = root / 'a' / 'gcc' / 'rel' / 'x86_64' / 'cxx2c'
    first.mkdir( parents=True )
    second.mkdir( parents=True )
    other.mkdir( parents=True )

    matches = build_layout.paths_ending_with(
        str( root ), os.path.join( 'gcc', 'dbg', 'x86_64', 'cxx2c' )
    )
    assert sorted( matches ) == sorted( [ str( first ), str( second ) ] )
