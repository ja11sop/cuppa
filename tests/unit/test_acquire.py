#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os
import tarfile

import pytest

import cuppa.progress
from cuppa.buildsys import acquire
from cuppa.methods.acquire import DownloadExtractMethod, RemoveEmptyDirsMethod
from cuppa.utility.download import DownloadError


pytestmark = pytest.mark.unit


@pytest.fixture
def silence_progress( monkeypatch ):
    monkeypatch.setattr(
            cuppa.progress.NotifyProgress,
            'add',
            classmethod( lambda cls, env, target: None ),
    )


class _RecordingEnv(dict):
    def __init__( self, *args, **kwargs ):
        dict.__init__( self, *args, **kwargs )
        self.commands = []
        self.cleans = []
        self._options = {}

    def get_option( self, name, default=None ):
        return self._options.get( name, default )

    def Command( self, target, source, action ):
        self.commands.append( {
                'target': target,
                'source': source,
                'action': action,
        } )
        return [ 'node:{}'.format( target ) ]

    def Clean( self, target, files ):
        self.cleans.append( ( target, files ) )


def _make_github_style_tarball( path, top_name='proj-1.0.0' ):
    with tarfile.open( path, 'w:gz' ) as handle:
        top = path.parent / '_tree' / top_name
        ( top / 'src' ).mkdir( parents=True )
        ( top / 'CMakeLists.txt' ).write_text( 'cmake_minimum_required(VERSION 3.16)\n' )
        ( top / 'src' / 'a.cpp' ).write_text( 'int main(){return 0;}\n' )
        handle.add( top, arcname=top_name )


def test_archive_basename_from_url():
    assert acquire.archive_basename_from_url(
            'https://github.com/org/proj/archive/v1.2.3.tar.gz'
    ) == 'v1.2.3.tar.gz'
    assert acquire.archive_basename_from_url(
            'https://example/download',
            archive='widget.tar.gz',
    ) == 'widget.tar.gz'
    with pytest.raises( ValueError ):
        acquire.archive_basename_from_url( 'https://example.com/download' )


def test_download_extract_strips_top_directory( tmp_path ):
    archive = tmp_path / 'v1.0.0.tar.gz'
    _make_github_style_tarball( archive )
    extract = tmp_path / 'working' / 'proj'
    marker = acquire.download_extract(
            archive.as_uri(),
            str( tmp_path / 'cached.tar.gz' ),
            str( extract ),
            strip_components=1,
            marker='CMakeLists.txt',
    )
    assert os.path.isfile( marker )
    assert ( extract / 'src' / 'a.cpp' ).is_file()
    assert not ( extract / 'proj-1.0.0' ).exists()


def test_download_extract_missing_marker_raises( tmp_path ):
    archive = tmp_path / 'v1.0.0.tar.gz'
    _make_github_style_tarball( archive )
    with pytest.raises( DownloadError ):
        acquire.download_extract(
                archive.as_uri(),
                str( tmp_path / 'cached.tar.gz' ),
                str( tmp_path / 'out' ),
                strip_components=1,
                marker='MISSING.txt',
        )


def test_remove_empty_dirs_still_via_acquire( tmp_path ):
    parent = tmp_path / 'third_party'
    ( parent / 'empty' ).mkdir( parents=True )
    ( parent / 'full' ).mkdir()
    ( parent / 'full' / 'f' ).write_text( 'x' )
    assert acquire.remove_empty_dirs( parent ) == [ 'empty' ]


def test_download_extract_method_registers_command( silence_progress ):
    env = _RecordingEnv( build_dir='_build/gcc/rel/working' )
    nodes = DownloadExtractMethod()(
            env,
            'https://github.com/org/proj/archive/v1.0.0.tar.gz',
            extract_dir='proj',
            marker='CMakeLists.txt',
    )
    assert nodes
    assert env.commands[0]['target'] == 'proj/CMakeLists.txt'
    assert env.cleans[0][1] == 'proj'


def test_remove_empty_dirs_method_from_acquire( silence_progress, tmp_path ):
    env = _RecordingEnv()
    nodes = RemoveEmptyDirsMethod()(
            env,
            [ 'src' ],
            parent=str( tmp_path / 'third_party' ),
            gitmodules=True,
            target='stamp.complete',
    )
    assert nodes == [ 'node:stamp.complete' ]


def test_download_extract_skips_when_amend_package_manifest( silence_progress ):
    env = _RecordingEnv( build_dir='_build/gcc/rel/working' )
    env._options['amend-package-manifest'] = True
    nodes = DownloadExtractMethod()(
            env,
            'https://github.com/org/proj/archive/v1.0.0.tar.gz',
            extract_dir='proj',
            marker='CMakeLists.txt',
    )
    assert nodes
    assert env.commands[0]['source'] == []
    assert env.cleans == []


def test_remove_empty_dirs_skips_when_amend_package_manifest( silence_progress, tmp_path ):
    env = _RecordingEnv()
    env._options['amend-package-manifest'] = True
    nodes = RemoveEmptyDirsMethod()(
            env,
            [ 'src' ],
            parent=str( tmp_path / 'third_party' ),
            target='stamp.complete',
    )
    assert nodes == [ 'node:stamp.complete' ]
    assert env.commands[0]['source'] == []

