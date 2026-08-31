#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.utility.object_target import artifact_target_for, object_target_for


pytestmark = pytest.mark.unit


class _Source:
    def __init__( self, path ):
        self.path = path

    def __str__( self ):
        return self.path


class _Env( dict ):
    def File( self, path ):
        return path.replace( '\\', '/' )


def _env( tmp_path ):
    working = tmp_path / '_build' / 'gcc' / 'dbg' / 'working'
    final = tmp_path / '_build' / 'gcc' / 'dbg' / 'final'
    return _Env({
        'build_root': str( tmp_path / '_build' ),
        'build_dir': str( working ),
        'abs_final_dir': str( final ),
    })


def test_nested_same_basename_objects_are_distinct( tmp_path ):
    env = _env( tmp_path )
    first = object_target_for( env, _Source( 'src/detail/except.cpp' ), '', '.o' )
    second = object_target_for( env, _Source( 'src/buffers/detail/except.cpp' ), '', '.o' )
    assert first != second
    assert first.endswith( 'src/detail/except.o' )
    assert second.endswith( 'src/buffers/detail/except.o' )


def test_flat_source_stays_directly_under_working( tmp_path ):
    env = _env( tmp_path )
    target = object_target_for( env, _Source( 'hello.cpp' ), '', '.o' )
    assert target.endswith( 'hello.o' )


def test_build_root_source_keeps_offset_from_working( tmp_path ):
    env = _env( tmp_path )
    build_dir = env['build_dir']
    source_path = build_dir + '/src/nested/deep.cpp'
    target = object_target_for( env, _Source( source_path ), '', '.o' )
    assert target.endswith( 'src/nested/deep.o' )


def test_nested_same_basename_artifacts_under_final_are_distinct( tmp_path ):
    env = _env( tmp_path )
    first = artifact_target_for( env, _Source( 'doc/a/readme.md' ), '.html' )
    second = artifact_target_for( env, _Source( 'doc/b/readme.md' ), '.html' )
    assert first != second
    assert first.replace( '\\', '/' ).endswith( 'final/doc/a/readme.html' )
    assert second.replace( '\\', '/' ).endswith( 'final/doc/b/readme.html' )


def test_flat_markdown_stays_directly_under_final( tmp_path ):
    env = _env( tmp_path )
    target = artifact_target_for( env, _Source( 'readme.md' ), '.html' )
    assert target.replace( '\\', '/' ).endswith( 'final/readme.html' )
    assert '/doc/' not in target.replace( '\\', '/' )


def test_artifact_respects_custom_output_dir( tmp_path ):
    env = _env( tmp_path )
    custom = str( tmp_path / 'staged' )
    target = artifact_target_for(
        env, _Source( 'doc/a/readme.md' ), '.html', output_dir=custom
    )
    assert target.replace( '\\', '/' ).endswith( 'staged/doc/a/readme.html' )


def test_run_redirect_extension( tmp_path ):
    env = _env( tmp_path )
    target = artifact_target_for( env, _Source( 'tools/gen' ), '.out' )
    assert target.replace( '\\', '/' ).endswith( 'final/tools/gen.out' )
