
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.package_managers import conan as conan_pkg
from cuppa.package_managers import gitlab
from cuppa.utility.scons_nodes import resolve_existing_node_path


pytestmark = pytest.mark.unit


class _VariantDirNode:

    def __init__( self, path, source_path ):
        self._path = path
        self._source_path = source_path

    def __str__( self ):
        return str( self._path )

    def srcnode( self ):
        return self._source_path


def test_prefers_existing_generated_variant_dir( tmp_path ):
    generated = tmp_path / '_build' / 'working' / 'widget' / 'lib'
    generated.mkdir( parents=True )
    source = tmp_path / 'widget' / 'lib'
    node = _VariantDirNode( generated, source )

    assert resolve_existing_node_path( node ) == str( generated )


def test_falls_back_to_existing_source_dir( tmp_path ):
    generated = tmp_path / '_build' / 'working' / 'include'
    source = tmp_path / 'include'
    source.mkdir()
    node = _VariantDirNode( generated, source )

    assert resolve_existing_node_path( node ) == str( source )


def test_prefers_generated_when_both_exist( tmp_path ):
    generated = tmp_path / '_build' / 'working' / 'include'
    generated.mkdir( parents=True )
    source = tmp_path / 'include'
    source.mkdir()
    node = _VariantDirNode( generated, source )

    assert resolve_existing_node_path( node ) == str( generated )


def test_missing_paths_keep_generated_name( tmp_path ):
    generated = tmp_path / '_build' / 'working' / 'widget' / 'lib'
    source = tmp_path / 'widget' / 'lib'
    node = _VariantDirNode( generated, source )

    assert resolve_existing_node_path( node ) == str( generated )


def test_plain_string_path( tmp_path ):
    existing = tmp_path / 'include'
    existing.mkdir()
    assert resolve_existing_node_path( str( existing ) ) == str( existing )
    missing = tmp_path / 'nope'
    assert resolve_existing_node_path( str( missing ) ) == str( missing )


def test_srcnode_may_return_a_node( tmp_path ):
    generated = tmp_path / '_build' / 'working' / 'include'
    source = tmp_path / 'include'
    source.mkdir()
    node = _VariantDirNode( generated, _VariantDirNode( source, source ) )

    assert resolve_existing_node_path( node ) == str( source )


def test_publishers_share_the_helper():
    assert gitlab._resolve_node_path is resolve_existing_node_path
    assert conan_pkg._resolve_node_path is resolve_existing_node_path
