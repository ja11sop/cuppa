#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os
from pathlib import Path

import pytest

from cuppa.cpp.gcov_notes import (
        apply_gcov_prefix,
        coverage_notes_prefix,
        relocated_gcda_path,
        stage_gcov_object,
        stage_gcov_source,
)

pytestmark = pytest.mark.unit


class _Env( dict ):
    def get( self, key, default=None ):
        return dict.get( self, key, default )


def test_notes_prefix_is_per_binary_and_absent_without_cov( tmp_path ):
    env = _Env(
            variant_actions={ "test": True },
            sconscript_file=str( tmp_path / "sconscript" ),
            abs_build_dir=str( tmp_path / "_build" ),
    )
    assert coverage_notes_prefix( env, "final/alpha" ) is None

    env["variant_actions"] = { "cov": True, "test": True }
    alpha = coverage_notes_prefix( env, "final/alpha" )
    beta = coverage_notes_prefix( env, "final/beta" )
    assert alpha != beta
    assert alpha.endswith( os.path.join( "gcov-notes", "sconscript", "alpha" ) )
    assert os.path.isdir( alpha )
    child = {}
    apply_gcov_prefix( child, alpha )
    assert child["GCOV_PREFIX"] == alpha
    assert child["GCOV_PREFIX_STRIP"] == "0"


def test_stage_gcov_source_keeps_relative_name( tmp_path, monkeypatch ):
    project = tmp_path / "proj"
    source_dir = project / "suite"
    source_dir.mkdir( parents=True )
    source = source_dir / "alpha_test.cpp"
    source.write_text( "int main(){return 0;}\n", encoding="utf-8" )
    text_dir = tmp_path / "gcov-text"
    text_dir.mkdir()
    monkeypatch.chdir( project )
    staged = stage_gcov_source( str( text_dir ), "suite/alpha_test.cpp" )
    assert staged == "suite/alpha_test.cpp"
    link = text_dir / "suite" / "alpha_test.cpp"
    assert link.is_symlink()
    assert os.path.realpath( link ) == os.path.realpath( source )


def test_stage_gcov_object_points_at_relocated_gcda( tmp_path ):
    build = tmp_path / "obj"
    build.mkdir()
    stem = build / "alpha"
    gcno = Path( str( stem ) + ".gcno" )
    gcno.write_text( "notes", encoding="utf-8" )
    prefix = tmp_path / "gcov-notes" / "alpha"
    relocated = Path( relocated_gcda_path( str( prefix ), str( stem ) ) )
    relocated.parent.mkdir( parents=True )
    relocated.write_text( "counts", encoding="utf-8" )
    text_dir = tmp_path / "gcov-text"
    text_dir.mkdir()
    private = stage_gcov_object( str( text_dir ), str( stem ), str( prefix ) )
    assert os.path.realpath( private + ".gcno" ) == os.path.realpath( gcno )
    assert os.path.realpath( private + ".gcda" ) == os.path.realpath( relocated )
    assert private != str( stem )


def test_notes_prefix_uses_first_node_not_list_repr( tmp_path ):
    class _Nodes( object ):
        def __init__( self, path ):
            self._path = path
        def __getitem__( self, index ):
            return self._path
        def __str__( self ):
            return "['{}']".format( self._path )

    env = _Env(
            variant_actions={ "cov": True },
            sconscript_file="sconscript",
            abs_build_dir=str( tmp_path / "build" ),
    )
    prefix = coverage_notes_prefix( env, _Nodes( str( tmp_path / "build" / "final" / "beta_cov" ) ) )
    assert prefix.endswith( os.path.join( "gcov-notes", "sconscript", "beta_cov" ) )
    assert "'" not in prefix
