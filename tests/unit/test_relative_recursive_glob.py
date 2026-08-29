
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os
import re
import types

import pytest

import cuppa.methods.relative_recursive_glob as rrg
from cuppa.methods.relative_recursive_glob import (
        RecursiveGlobMethod,
        GlobFilesMethod,
        _as_regex,
        _directory_glob_pattern,
        _exclude_dirs_regex,
        _file_nodes_only,
        _files_from_dir_entries,
        _files_from_local_repository_globs,
        _is_dir_node,
        _is_mergeable_declared_file,
        _merge_unique_nodes,
        _node_key,
        _start_dir_node,
)
from cuppa.utility.glob_roots import DEFAULT_START


pytestmark = pytest.mark.unit


class _FakeNode:
    def __init__(
            self,
            name,
            *,
            abspath=None,
            exists=False,
            is_dir=False,
            src=None,
            remote_abspath=None,
            entries=None,
    ):
        self.name = name
        self.abspath = abspath or name
        self.path = name
        self._exists = exists
        self._is_dir = is_dir
        self._src = src
        self._remote_abspath = remote_abspath
        self.entries = entries if entries is not None else (
                { '.': self, '..': None } if is_dir else {}
        )

    def exists( self ):
        return self._exists

    def isdir( self ):
        return self._is_dir

    def srcnode( self ):
        return self._src if self._src is not None else self

    def rfile( self ):
        if self._remote_abspath is None:
            return self.srcnode()
        return _FakeNode( self.name, abspath=self._remote_abspath, exists=True )


def test_as_regex_accepts_string_and_compiled():
    compiled = _as_regex( '*.cpp' )
    assert compiled.match( 'foo.cpp' )
    assert not compiled.match( 'foo.ebs' )
    assert _as_regex( None ) is None
    same = re.compile( 'x' )
    assert _as_regex( same ) is same


def test_compat_wrappers_delegate_to_glob_roots( tmp_path ):
    env = {
            'sconstruct_dir': str( tmp_path ),
            'sconscript_dir': str( tmp_path ),
    }
    absolute, sconscript_dir = rrg.clean_start( env, 'src', DEFAULT_START )
    assert absolute.endswith( 'src' )
    assert sconscript_dir == str( tmp_path.resolve() )
    triple = rrg.relative_start( env, 'src', DEFAULT_START )
    assert triple[0] == absolute


def test_files_from_dir_entries_empty_entries_and_discard_dir_skip( tmp_path ):
    assert _files_from_dir_entries( _FakeNode( 'empty', is_dir=True, entries={} ), _as_regex( '*.ebs' ) ) == []
    assert _files_from_dir_entries( types.SimpleNamespace(), _as_regex( '*.ebs' ) ) == []

    marker = _FakeNode( 'CMakeLists.txt', abspath=str( tmp_path / 'CMakeLists.txt' ) )
    nested = _FakeNode( 'nested', is_dir=True, entries={ '.': None, '..': None } )
    start = _FakeNode( 'root', is_dir=True, entries={
            '.': None,
            '..': None,
            'nested': nested,
            'CMakeLists.txt': marker,
    } )
    # discard check must skip directory names and still see the marker file
    assert _files_from_dir_entries(
            start,
            _as_regex( '*.ebs' ),
            discard_pattern=_as_regex( 'CMakeLists.txt' ),
            is_subdir=True,
    ) == []


def test_is_mergeable_uses_isfile_when_exists_false( tmp_path ):
    path = tmp_path / 'present.ebs'
    path.write_text( 'x' )
    entry = _FakeNode(
            'present.ebs',
            abspath=str( tmp_path / 'build' / 'present.ebs' ),
            exists=False,
            src=_FakeNode( 'present.ebs', abspath=str( path ), exists=False ),
    )
    assert not _is_mergeable_declared_file( entry )


def test_source_node_without_callable_srcnode():
    node = types.SimpleNamespace( abspath='/x' )
    assert rrg._source_node( node ) is node
    assert rrg._node_exists( types.SimpleNamespace() ) is False


def test_add_to_env_registers_methods():
    registered = {}

    class CuppaEnv:
        def add_method( self, name, method ):
            registered[name] = method

    cuppa_env = CuppaEnv()
    RecursiveGlobMethod.add_to_env( cuppa_env )
    GlobFilesMethod.add_to_env( cuppa_env )
    assert set( registered ) == { 'RecursiveGlob', 'GlobFiles' }
    assert callable( registered['RecursiveGlob'] )
    assert callable( registered['GlobFiles'] )


def test_exclude_dirs_regex_defaults_and_skips_absolute( tmp_path ):
    env = {
            'dependencies_root': str( tmp_path / 'deps' ),
            'build_root': str( tmp_path / '_build' ),
    }
    assert _exclude_dirs_regex( env, DEFAULT_START, DEFAULT_START ) is None
    assert _exclude_dirs_regex( env, [], DEFAULT_START ) is None

    pattern = _exclude_dirs_regex( env, [ 'build', str( tmp_path / 'abs' ), '..' ], DEFAULT_START )
    assert pattern.match( 'build' )
    assert not pattern.match( 'src' )


def test_directory_glob_pattern_shapes( tmp_path ):
    sconscript = str( tmp_path / 'project' )
    src = str( tmp_path / 'project' / 'src' )
    assert _directory_glob_pattern( sconscript, sconscript, '.', '*.cpp' ) == '*.cpp'
    # rel_start from src back to sconscript is '..' — absolute pattern form
    climbed = _directory_glob_pattern( src, sconscript, '..', '*.cpp' )
    assert climbed.replace( '\\', '/' ).endswith( 'src/*.cpp' )
    # start under sconscript with a non-climbing rel_start uses a relative Glob pattern
    relative = _directory_glob_pattern( src, sconscript, 'not-a-climb', '*.cpp' )
    assert relative.replace( '\\', '/' ) == 'src/*.cpp'


def test_file_nodes_only_drops_directories():
    files = _file_nodes_only( [
            _FakeNode( 'a.cpp', is_dir=False ),
            _FakeNode( 'subdir', is_dir=True ),
    ] )
    assert [ node.name for node in files ] == [ 'a.cpp' ]


def test_start_dir_node_prefers_sconscript_relative():
    calls = []

    class Env:
        def Dir( self, path ):
            calls.append( path )
            return path

    env = Env()
    sconscript = '/proj'
    assert _start_dir_node( env, '/proj', sconscript ) == '.'
    assert _start_dir_node( env, '/proj/src', sconscript ) == 'src'
    assert _start_dir_node( env, '/elsewhere', sconscript ) == '/elsewhere'
    assert calls == [ '.', 'src', '/elsewhere' ]


def test_is_dir_node_falls_back_to_isdir():
    assert _is_dir_node( _FakeNode( 'd', is_dir=True ) )
    assert not _is_dir_node( _FakeNode( 'f.cpp', is_dir=False ) )


def test_is_dir_node_uses_scons_class_even_when_isdir_false():
    from SCons.Node.FS import FS

    fs = FS()
    declared_dir = fs.Dir( 'declared_only_dir' )
    declared_file = fs.File( 'declared_only_dir/ghost.cpp' )
    assert declared_dir.isdir() is False
    assert _is_dir_node( declared_dir ) is True
    assert _is_dir_node( declared_file ) is False


def test_is_mergeable_declared_file_filters_disk_and_repository( tmp_path ):
    on_disk = tmp_path / 'local.ebs'
    on_disk.write_text( 'x' )
    repo_file = tmp_path / 'repo' / 'from_repo.ebs'
    repo_file.parent.mkdir()
    repo_file.write_text( 'y' )

    ghost = _FakeNode(
            'ghost.ebs',
            abspath=str( tmp_path / 'ghost.ebs' ),
            exists=False,
    )
    assert _is_mergeable_declared_file( ghost )

    local = _FakeNode(
            'local.ebs',
            abspath=str( tmp_path / 'build' / 'local.ebs' ),
            exists=False,
            src=_FakeNode( 'local.ebs', abspath=str( on_disk ), exists=True ),
    )
    assert not _is_mergeable_declared_file( local )

    from_repo = _FakeNode(
            'from_repo.ebs',
            abspath=str( tmp_path / 'build' / 'from_repo.ebs' ),
            exists=False,
            src=_FakeNode(
                    'from_repo.ebs',
                    abspath=str( tmp_path / 'from_repo.ebs' ),
                    exists=False,
            ),
            remote_abspath=str( repo_file ),
    )
    assert not _is_mergeable_declared_file( from_repo )


def test_files_from_dir_entries_nested_ghost_and_exclude( tmp_path ):
    ghost = _FakeNode(
            'ghost.ebs',
            abspath=str( tmp_path / 'src' / 'nested' / 'ghost.ebs' ),
            exists=False,
    )
    nested = _FakeNode( 'nested', is_dir=True, entries={
            '.': None,
            '..': None,
            'ghost.ebs': ghost,
    } )
    # Make nested look like SCons.Dir for isinstance path when possible
    skip_dir = _FakeNode( 'build', is_dir=True, entries={ '.': None, '..': None } )
    on_disk = _FakeNode(
            'on_disk.ebs',
            abspath=str( tmp_path / 'src' / 'on_disk.ebs' ),
            exists=True,
    )
    ( tmp_path / 'src' ).mkdir()
    ( tmp_path / 'src' / 'on_disk.ebs' ).write_text( 'x' )
    on_disk_src = _FakeNode(
            'on_disk.ebs',
            abspath=str( tmp_path / 'src' / 'on_disk.ebs' ),
            exists=True,
    )
    on_disk = _FakeNode(
            'on_disk.ebs',
            abspath=str( tmp_path / 'build' / 'on_disk.ebs' ),
            exists=False,
            src=on_disk_src,
    )

    start = _FakeNode( 'src', is_dir=True, entries={
            '.': None,
            '..': None,
            'nested': nested,
            'build': skip_dir,
            'on_disk.ebs': on_disk,
    } )

    # Force Dir-like detection via isdir() for fakes (not real SCons instances)
    found = _files_from_dir_entries(
            start,
            _as_regex( '*.ebs' ),
            exclude_dirs_regex=re.compile( 'build' ),
    )
    assert [ node.name for node in found ] == [ 'ghost.ebs' ]


def test_files_from_dir_entries_discard_pattern_clears_subdir( tmp_path ):
    marker = _FakeNode( 'CMakeLists.txt', abspath=str( tmp_path / 'bad' / 'CMakeLists.txt' ) )
    hidden = _FakeNode(
            'hidden.ebs',
            abspath=str( tmp_path / 'bad' / 'hidden.ebs' ),
            exists=False,
    )
    bad = _FakeNode( 'bad', is_dir=True, entries={
            '.': None,
            '..': None,
            'CMakeLists.txt': marker,
            'hidden.ebs': hidden,
    } )
    start = _FakeNode( 'root', is_dir=True, entries={
            '.': None,
            '..': None,
            'bad': bad,
    } )
    found = _files_from_dir_entries(
            start,
            _as_regex( '*.ebs' ),
            discard_pattern=_as_regex( 'CMakeLists.txt' ),
    )
    assert found == []


def test_merge_unique_nodes_dedupes_by_source_abspath():
    a1 = _FakeNode( 'a.ebs', abspath='/proj/a.ebs' )
    a2 = _FakeNode(
            'a.ebs',
            abspath='/build/a.ebs',
            src=_FakeNode( 'a.ebs', abspath='/proj/a.ebs' ),
    )
    b = _FakeNode( 'b.ebs', abspath='/proj/b.ebs' )
    merged = _merge_unique_nodes( [ a1 ], [ a2, b ] )
    assert [ node.name for node in merged ] == [ 'a.ebs', 'b.ebs' ]
    assert _node_key( a1 ) == _node_key( a2 )


def test_recursive_glob_method_merges_declared_with_disk( tmp_path, monkeypatch ):
    root = tmp_path / 'project'
    scenarios = root / 'test' / 'scenarios'
    scenarios.mkdir( parents=True )
    ( scenarios / 'on_disk.ebs' ).write_text( 'disk' )

    ghost = _FakeNode(
            'ghost.ebs',
            abspath=str( scenarios / 'ghost.ebs' ),
            exists=False,
    )
    start_dir = _FakeNode( 'scenarios', is_dir=True, entries={
            '.': None,
            '..': None,
            'ghost.ebs': ghost,
            'on_disk.ebs': _FakeNode(
                    'on_disk.ebs',
                    abspath=str( scenarios / 'on_disk.ebs' ),
                    exists=True,
            ),
    } )

    created = []

    class Env( dict ):
        def File( self, path ):
            node = _FakeNode( os.path.basename( path ), abspath=path )
            created.append( node )
            return node

        def Dir( self, path ):
            return start_dir

    env = Env( {
            'sconstruct_dir': str( root ),
            'sconscript_dir': str( root ),
            'dependencies_root': str( tmp_path / 'deps' ),
            'build_root': str( tmp_path / '_build' ),
    } )

    monkeypatch.setattr( rrg, '_start_dir_node', lambda *a, **k: start_dir )

    nodes = RecursiveGlobMethod()(
            env,
            '*.ebs',
            start=str( scenarios ),
            exclude_dirs=[],
    )
    names = sorted( node.name for node in nodes )
    assert names == [ 'ghost.ebs', 'on_disk.ebs' ]


def test_files_from_local_repository_globs_calls_dir_glob_per_local_dir( tmp_path ):
    root = tmp_path / 'src'
    nested = root / 'nested'
    nested.mkdir( parents=True )
    ( root / 'local.cpp' ).write_text( 'l' )
    ( nested / 'deep.cpp' ).write_text( 'd' )

    calls = []

    class GlobDir:
        def __init__( self, label ):
            self.label = label

        def Dir( self, rel ):
            return GlobDir( self.label + '/' + rel.replace( '\\', '/' ) )

        def glob( self, pattern ):
            calls.append( ( self.label, pattern ) )
            if self.label.endswith( 'nested' ):
                return [ _FakeNode( 'deep.cpp', is_dir=False ) ]
            return [
                    _FakeNode( 'local.cpp', is_dir=False ),
                    _FakeNode( 'from_repo.cpp', is_dir=False ),
            ]

    found = _files_from_local_repository_globs(
            GlobDir( 'src' ),
            str( root ),
            '*.cpp',
    )
    assert sorted( node.name for node in found ) == [
            'deep.cpp', 'from_repo.cpp', 'local.cpp',
    ]
    assert ( 'src', '*.cpp' ) in calls
    assert any( label.endswith( 'nested' ) and pattern == '*.cpp' for label, pattern in calls )


def test_files_from_local_repository_globs_honours_discard( tmp_path ):
    root = tmp_path / 'src'
    bad = root / 'bad'
    bad.mkdir( parents=True )
    ( root / 'ok.cpp' ).write_text( 'o' )
    ( bad / 'CMakeLists.txt' ).write_text( 'c' )
    ( bad / 'hidden.cpp' ).write_text( 'h' )

    class GlobDir:
        def Dir( self, rel ):
            return self

        def glob( self, pattern ):
            return [ _FakeNode( 'ok.cpp', is_dir=False ) ]

    found = _files_from_local_repository_globs(
            GlobDir(),
            str( root ),
            '*.cpp',
            discard_pattern='CMakeLists.txt',
    )
    assert [ node.name for node in found ] == [ 'ok.cpp' ]


def test_glob_files_method_filters_dirs_from_glob( tmp_path ):
    class Env( dict ):
        def Glob( self, pattern ):
            assert 'src' in pattern.replace( '\\', '/' ) and pattern.endswith( '*.cpp' )
            return [
                    _FakeNode( 'hello.cpp', is_dir=False ),
                    _FakeNode( 'nested', is_dir=True ),
            ]

    env = Env( {
            'sconstruct_dir': str( tmp_path ),
            'sconscript_dir': str( tmp_path ),
    } )
    ( tmp_path / 'src' ).mkdir()
    nodes = GlobFilesMethod()( env, '*.cpp', start='src' )
    assert [ node.name for node in nodes ] == [ 'hello.cpp' ]
