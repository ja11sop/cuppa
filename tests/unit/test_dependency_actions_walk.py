"""Unit tests for dependency tree discovery under dependencies_root."""

import pytest

from cuppa.core.dependency_actions import _walk_dependency_trees


pytestmark = pytest.mark.unit


def test_walk_keeps_vcs_trees_as_single_top_level_entries( tmp_path ):
    root = tmp_path / 'dependencies'
    vcs = root / 'git_https_github.com__fmtlib_fmt.git'
    ( vcs / 'include' / 'fmt' ).mkdir( parents=True )
    ( vcs / 'test' / 'unit' ).mkdir( parents=True )
    ( vcs / 'doc' ).mkdir( parents=True )

    walked = sorted( _walk_dependency_trees( str( root ) ) )
    assert walked == [ str( vcs ) ]


def test_walk_yields_package_version_under_tool_variant( tmp_path ):
    root = tmp_path / 'dependencies'
    boost = root / 'gcc153_rel_x86_64_cxx2c' / 'boost' / '1.91'
    capy = root / 'gcc153_rel_x86_64_cxx2c' / 'capy' / 'develop'
    boost.mkdir( parents=True )
    capy.mkdir( parents=True )
    # Nested source-like noise must not appear.
    ( boost / 'include' / 'boost' ).mkdir( parents=True )

    walked = sorted( _walk_dependency_trees( str( root ) ) )
    assert walked == sorted( [ str( boost ), str( capy ) ] )


def test_walk_yields_conan_fingerprint_dirs( tmp_path ):
    root = tmp_path / 'dependencies'
    install = root / 'conan' / 'fmt' / 'abcd1234efgh5678'
    install.mkdir( parents=True )
    ( install / 'SConscript_conandeps' ).write_text( '', encoding='utf-8' )

    walked = list( _walk_dependency_trees( str( root ) ) )
    assert walked == [ str( install ) ]


def test_walk_skips_inventory_dir( tmp_path ):
    root = tmp_path / 'dependencies'
    ( root / '.cuppa-inventory' ).mkdir( parents=True )
    tree = root / 'widget@master'
    tree.mkdir()

    walked = list( _walk_dependency_trees( str( root ) ) )
    assert walked == [ str( tree ) ]
