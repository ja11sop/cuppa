#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.cpp.gcov_data import (
        coverage_data_dir,
        coverage_env_step,
        gcov_run_dir,
        relocated_gcda_path,
        stage_gcno,
        stage_gcov_source,
)

pytestmark = pytest.mark.unit


def _env( tmp_path, actions ):
    return { "variant_actions": actions, "abs_build_dir": str( tmp_path / "_build" ) }


def test_no_data_dir_or_env_step_without_cov( tmp_path ):
    env = _env( tmp_path, { "test": True } )
    assert coverage_data_dir( env, "final/alpha" ) is None
    assert coverage_env_step( env, "final/alpha" ) is None


def test_data_dir_is_per_program_under_build_dir_and_creates_nothing( tmp_path ):
    env = _env( tmp_path, { "cov": True, "test": True } )
    alpha = coverage_data_dir( env, "_build/final/alpha" )
    beta = coverage_data_dir( env, "_build/final/beta" )
    assert alpha == os.path.join( str( tmp_path / "_build" ), "gcov-data", "alpha" )
    assert alpha != beta
    assert not os.path.exists( alpha )


def test_env_step_adds_prefix_with_no_strip_and_keeps_the_rest( tmp_path ):
    env = _env( tmp_path, { "cov": True } )
    step = coverage_env_step( env, "final/alpha" )
    assert step( { "PATH": "/bin" } ) == {
            "PATH": "/bin",
            "GCOV_PREFIX": coverage_data_dir( env, "final/alpha" ),
            "GCOV_PREFIX_STRIP": "0",
    }


def test_relocated_gcda_keeps_prefix_for_absolute_stem( tmp_path ):
    stem = str( tmp_path / "working" / "lib" / "shared" )
    data_dir = str( tmp_path / "gcov-data" / "alpha" )
    assert relocated_gcda_path( data_dir, stem ) == data_dir + stem + ".gcda"


def test_stage_gcov_source_copies_relative_source( tmp_path, monkeypatch ):
    project = tmp_path / "proj"
    ( project / "suite" ).mkdir( parents=True )
    source = project / "suite" / "alpha_test.cpp"
    source.write_text( "int main(){return 0;}\n", encoding="utf-8" )
    run_dir = gcov_run_dir( str( tmp_path / "gcov-data" / "alpha" ) )
    monkeypatch.chdir( project )

    assert stage_gcov_source( run_dir, "suite/alpha_test.cpp" ) == "suite/alpha_test.cpp"
    copied = os.path.join( run_dir, "suite", "alpha_test.cpp" )
    assert os.path.isfile( copied )
    assert not os.path.islink( copied )
    assert open( copied, encoding="utf-8" ).read() == source.read_text( encoding="utf-8" )


def test_stage_gcov_source_leaves_absolute_source_alone( tmp_path ):
    absolute = str( tmp_path / "a.cpp" )
    run_dir = gcov_run_dir( str( tmp_path / "gcov-data" / "alpha" ) )
    assert stage_gcov_source( run_dir, absolute ) == absolute
    assert os.listdir( run_dir ) == []


def _object( tmp_path ):
    stem = tmp_path / "working" / "shared"
    stem.parent.mkdir()
    gcno = tmp_path / "working" / "shared.gcno"
    gcno.write_text( "notes", encoding="utf-8" )
    data_dir = str( tmp_path / "gcov-data" / "alpha" )
    return str( stem ), data_dir, gcno


def test_stage_gcno_links_beside_relocated_gcda( tmp_path ):
    stem, data_dir, gcno = _object( tmp_path )
    relocated = relocated_gcda_path( data_dir, stem )
    os.makedirs( os.path.dirname( relocated ) )
    with open( relocated, "w", encoding="utf-8" ) as counts:
        counts.write( "counts" )

    private = stage_gcno( stem, data_dir )

    assert private == os.path.splitext( relocated )[0]
    beside = private + ".gcno"
    assert os.path.islink( beside )
    assert os.path.realpath( beside ) == os.path.realpath( gcno )
    assert not os.path.islink( relocated )


def test_stage_gcno_copies_when_symlink_is_unavailable( tmp_path, monkeypatch ):
    stem, data_dir, gcno = _object( tmp_path )
    relocated = relocated_gcda_path( data_dir, stem )
    os.makedirs( os.path.dirname( relocated ) )
    with open( relocated, "w", encoding="utf-8" ) as counts:
        counts.write( "counts" )

    def _refuse( source, dest ):
        raise OSError( "symlinks are not available" )

    monkeypatch.setattr( os, "symlink", _refuse )
    private = stage_gcno( stem, data_dir )
    beside = private + ".gcno"
    assert os.path.isfile( beside )
    assert not os.path.islink( beside )
    assert open( beside, encoding="utf-8" ).read() == gcno.read_text( encoding="utf-8" )


def test_stage_gcno_replaces_a_previous_link( tmp_path ):
    stem, data_dir, gcno = _object( tmp_path )
    relocated = relocated_gcda_path( data_dir, stem )
    os.makedirs( os.path.dirname( relocated ) )
    with open( relocated, "w", encoding="utf-8" ) as counts:
        counts.write( "counts" )
    first = stage_gcno( stem, data_dir )
    gcno.write_text( "notes-again", encoding="utf-8" )
    assert stage_gcno( stem, data_dir ) == first
    assert os.path.realpath( first + ".gcno" ) == os.path.realpath( gcno )


def test_stage_gcno_without_relocated_gcda_uses_absolute_stem( tmp_path ):
    stem, data_dir, _gcno = _object( tmp_path )
    assert stage_gcno( os.path.relpath( stem ), data_dir ) == stem
    assert not os.path.exists( data_dir )
