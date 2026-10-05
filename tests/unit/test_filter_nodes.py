
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

import cuppa.utility.filter as filter_mod
from cuppa.utility.filter import _node_path_forms, filter_nodes


pytestmark = pytest.mark.unit


class _FakeFileNode:
    """Minimal stand-in for SCons.Node.FS.File for path-form tests."""

    def __init__( self, path, abspath=None ):
        self.path = path
        self.abspath = abspath or path

    def __str__( self ):
        return self.abspath


def test_node_path_forms_include_relative_and_absolute():
    node = _FakeFileNode( 'src/foo_test.cpp', abspath='/proj/src/foo_test.cpp' )
    forms = _node_path_forms( node )
    assert 'src/foo_test.cpp' in forms
    assert '/proj/src/foo_test.cpp' in forms


def test_filter_matches_project_relative_pattern_on_absolute_str( monkeypatch ):
    node = _FakeFileNode( 'src/foo_test.cpp', abspath='/proj/src/foo_test.cpp' )
    monkeypatch.setattr( filter_mod, 'Node', _FakeFileNode )
    monkeypatch.setattr( filter_mod.os.path, 'exists', lambda p: True )
    monkeypatch.setattr( filter_mod.os.path, 'isdir', lambda p: False )

    matched = filter_nodes( [ node ], match_patterns='src/*_test.cpp' )
    assert matched == [ node ]

    excluded = filter_nodes(
            [ node ],
            match_patterns='*.cpp',
            exclude_patterns='src/*_test.cpp',
    )
    assert excluded == []


def test_filter_matches_basename_style_on_relative_path( monkeypatch ):
    node = _FakeFileNode( 'tests/hello_test.cpp', abspath='/proj/tests/hello_test.cpp' )
    monkeypatch.setattr( filter_mod, 'Node', _FakeFileNode )
    monkeypatch.setattr( filter_mod.os.path, 'exists', lambda p: True )
    monkeypatch.setattr( filter_mod.os.path, 'isdir', lambda p: False )

    matched = filter_nodes( [ node ], match_patterns='*_test.cpp' )
    assert matched == [ node ]


def test_missing_extensionless_final_program_does_not_warn( monkeypatch, caplog ):
    """Not-yet-built Programs under final/ are not warn-noise under --cascade-plan."""
    node = _FakeFileNode(
            '_build/test/gcc16/dbg/x86_64/cxx2c/final/order_matcher',
            abspath='/proj/_build/test/gcc16/dbg/x86_64/cxx2c/final/order_matcher',
    )
    monkeypatch.setattr( filter_mod, 'Node', _FakeFileNode )
    monkeypatch.setattr( filter_mod.os.path, 'exists', lambda p: False )

    with caplog.at_level( 'DEBUG' ):
        matched = filter_nodes( [ node ], match_patterns='*/final/*' )

    assert matched == []
    assert not any( record.levelname == 'WARNING' for record in caplog.records )
    assert 'probably a directory' not in caplog.text
    assert any(
            record.levelname == 'DEBUG'
            and 'does not exist yet' in record.message
            for record in caplog.records
    )


def test_missing_path_with_extension_still_matches( monkeypatch, caplog ):
    node = _FakeFileNode(
            '_build/test/working/foo.o',
            abspath='/proj/_build/test/working/foo.o',
    )
    monkeypatch.setattr( filter_mod, 'Node', _FakeFileNode )
    monkeypatch.setattr( filter_mod.os.path, 'exists', lambda p: False )

    with caplog.at_level( 'WARNING' ):
        matched = filter_nodes( [ node ], match_patterns='*.o' )

    assert matched == [ node ]
    assert not any( record.levelname == 'WARNING' for record in caplog.records )


def test_existing_directory_stays_out_of_file_matches( monkeypatch, caplog ):
    node = _FakeFileNode( 'include', abspath='/proj/include' )
    monkeypatch.setattr( filter_mod, 'Node', _FakeFileNode )
    monkeypatch.setattr( filter_mod.os.path, 'exists', lambda p: True )
    monkeypatch.setattr( filter_mod.os.path, 'isdir', lambda p: True )

    with caplog.at_level( 'DEBUG' ):
        matched = filter_nodes( [ node ], match_patterns='*' )

    assert matched == []
    assert not any( record.levelname == 'WARNING' for record in caplog.records )
    assert any(
            record.levelname == 'DEBUG' and 'is a directory' in record.message
            for record in caplog.records
    )
