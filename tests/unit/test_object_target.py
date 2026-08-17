#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.utility.object_target import object_target_for


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
    return _Env({
        'build_root': str( tmp_path / '_build' ),
        'build_dir': str( working ),
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
