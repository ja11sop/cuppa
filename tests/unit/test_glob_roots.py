
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.utility.glob_roots import resolve_glob_start, relative_glob_start


pytestmark = pytest.mark.unit


def _env( tmp_path, sconscript_rel='.', sconstruct_rel='.' ):
    project = tmp_path / 'project'
    project.mkdir()
    sconstruct = project / sconstruct_rel if sconstruct_rel != '.' else project
    sconscript = project / sconscript_rel if sconscript_rel != '.' else project
    if sconstruct_rel != '.':
        sconstruct.mkdir( parents=True, exist_ok=True )
    if sconscript_rel != '.' and sconscript != sconstruct:
        sconscript.mkdir( parents=True, exist_ok=True )
    return {
            'sconstruct_dir': str( sconstruct.resolve() ),
            'sconscript_dir': str( sconscript.resolve() ),
    }


def test_resolve_default_start_is_sconscript_dir( tmp_path ):
    env = _env( tmp_path, sconscript_rel='lib' )
    start, sconscript_dir = resolve_glob_start( env )
    assert start == sconscript_dir
    assert start.endswith( os.path.join( 'project', 'lib' ) )


def test_resolve_relative_start_from_sconscript( tmp_path ):
    env = _env( tmp_path, sconscript_rel='lib' )
    ( tmp_path / 'project' / 'lib' / 'src' ).mkdir()
    start, _ = resolve_glob_start( env, start='src' )
    assert start.endswith( os.path.join( 'project', 'lib', 'src' ) )


def test_resolve_hash_slash_from_sconstruct_root( tmp_path ):
    env = _env( tmp_path, sconscript_rel='lib' )
    ( tmp_path / 'project' / 'src' ).mkdir()
    start, sconscript_dir = resolve_glob_start( env, start='#/src' )
    assert start.endswith( os.path.join( 'project', 'src' ) )
    assert sconscript_dir.endswith( os.path.join( 'project', 'lib' ) )


def test_resolve_hash_without_slash( tmp_path ):
    env = _env( tmp_path )
    ( tmp_path / 'project' / 'include' ).mkdir()
    start, _ = resolve_glob_start( env, start='#include' )
    assert start.endswith( os.path.join( 'project', 'include' ) )


def test_resolve_absolute_start( tmp_path ):
    env = _env( tmp_path )
    abs_src = ( tmp_path / 'elsewhere' / 'src' )
    abs_src.mkdir( parents=True )
    start, _ = resolve_glob_start( env, start=str( abs_src ) )
    assert start == str( abs_src.resolve() )


def test_relative_glob_start_reports_climb( tmp_path ):
    env = _env( tmp_path, sconscript_rel='lib' )
    ( tmp_path / 'project' / 'src' ).mkdir()
    absolute, rel_start, sconscript_dir = relative_glob_start( env, start='#/src' )
    assert absolute.endswith( os.path.join( 'project', 'src' ) )
    assert sconscript_dir.endswith( os.path.join( 'project', 'lib' ) )
    assert rel_start == os.path.join( os.pardir, 'lib' )
