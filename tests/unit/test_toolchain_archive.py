#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import json
import os
import subprocess
import tarfile

import pytest

from cuppa.toolchains import toolchain_archive as ta


pytestmark = pytest.mark.unit


class Env( dict ):
    def get_option( self, name, default=None ):
        return self.get( name, default )


def _cuppa_env( tmp_path, **extra ):
    env = Env( {
        'sconstruct_dir': str( tmp_path ),
        'downloads_root': str( tmp_path / 'dl' ),
        'dependencies_root': str( tmp_path / 'deps' ),
        'offline': False,
    } )
    env.update( extra )
    return env


def test_sanitise_token():
    assert ta.sanitise_token( 'profiles-2026-08-07-27' ) == 'profiles_2026_08_07_27'
    assert ta.sanitise_token( '///' ) == 'unknown'


def test_release_tag_from_github_download_url():
    url = (
        'https://github.com/cppalliance/clang/releases/download/'
        'profiles-2026-08-07-27/clang-profiles-linux-x86_64.tar.gz'
    )
    assert ta.release_tag_from_url( url ) == 'profiles-2026-08-07-27'
    assert ta.qualifier_for_archive( url ) == 'profiles_2026_08_07_27'
    assert ta.toolchain_name( 'clang', 24, ta.qualifier_for_archive( url ) ) == \
        'clang24_profiles_2026_08_07_27'


def test_qualifier_for_non_release_url_uses_stem():
    url = 'https://example.com/builds/clang-profiles-linux-x86_64.tar.gz'
    assert ta.release_tag_from_url( url ) is None
    assert ta.qualifier_for_archive( url ) == 'clang_profiles_linux_x86_64'


def test_archive_family_and_deb_qualifier():
    url = (
        'https://deb.debian.org/debian/pool/main/g/gcc-snapshot/'
        'gcc-snapshot_20260725-1_amd64.deb'
    )
    assert ta.archive_family_from_name( url ) == 'gcc'
    assert ta.qualifier_for_archive( url ) == 'gcc_snapshot_20260725_1_amd64'
    assert ta.archive_family_from_name( 'clang.tgz' ) == 'clang'
    assert ta.archive_family_from_name( 'gcc-snapshot-linux.tar.xz' ) == 'gcc'
    assert ta.archive_family_from_name( 'clang-custom_1_amd64.deb' ) == 'clang'
    # No name token → None (caller probes contents or falls back to extension).
    assert ta.archive_family_from_name( 'mystery-toolchain_1_amd64.deb' ) is None
    assert ta.archive_family_from_name( 'mystery-toolchain.tar.gz' ) is None
    assert ta.archive_family_from_extension( 'mystery-toolchain_1_amd64.deb' ) == 'gcc'
    assert ta.archive_family_from_extension( 'mystery-toolchain.tar.gz' ) == 'clang'


def test_probe_archive_family_from_tar_members( tmp_path ):
    """Ambiguous basename: family comes from g++ / clang++ inside the archive."""
    payload = tmp_path / 'tree'
    bindir = payload / 'opt' / 'bin'
    bindir.mkdir( parents=True )
    ( bindir / 'g++' ).write_text( '#!/bin/sh\n' )
    archive = tmp_path / 'mystery-toolchain.tar.gz'
    with tarfile.open( str( archive ), 'w:gz' ) as handle:
        handle.add( str( bindir / 'g++' ), arcname='opt/bin/g++' )
    assert ta.probe_archive_family( str( archive ) ) == 'gcc'
    assert ta.resolve_archive_family( str( archive ), archive_path=str( archive ) ) == 'gcc'

    clang_archive = tmp_path / 'mystery-clangish.tar.gz'
    ( bindir / 'clang++' ).write_text( '#!/bin/sh\n' )
    ( bindir / 'g++' ).unlink()
    with tarfile.open( str( clang_archive ), 'w:gz' ) as handle:
        handle.add( str( bindir / 'clang++' ), arcname='opt/bin/clang++' )
    assert ta.probe_archive_family( str( clang_archive ) ) == 'clang'


def test_find_clang_bin_dir( tmp_path ):
    root = tmp_path / 'install'
    bindir = root / 'bin'
    bindir.mkdir( parents=True )
    ( bindir / 'clang++' ).write_text( '#!/bin/sh\n' )
    assert ta.find_clang_bin_dir( str( root ) ) == str( bindir )


def test_find_clang_bin_dir_nested( tmp_path ):
    root = tmp_path / 'extract'
    bindir = root / 'install-abc' / 'bin'
    bindir.mkdir( parents=True )
    ( bindir / 'clang++' ).write_text( '#!/bin/sh\n' )
    assert ta.find_clang_bin_dir( str( root ) ) == str( bindir )


def test_find_gcc_bin_dir_nested( tmp_path ):
    root = tmp_path / 'extract'
    bindir = root / 'usr' / 'lib' / 'gcc-snapshot' / 'bin'
    bindir.mkdir( parents=True )
    ( bindir / 'g++' ).write_text( '#!/bin/sh\n' )
    assert ta.find_gcc_bin_dir( str( root ) ) == str( bindir )


def test_prepare_from_root_persists_external_registration( tmp_path ):
    root = tmp_path / 'clang'
    bindir = root / 'bin'
    bindir.mkdir( parents=True )
    clangxx = bindir / 'clang++'
    clangxx.write_text( '#!/bin/sh\necho "clang version 24.0.0"\n' )
    os.chmod( str( clangxx ), 0o755 )

    cuppa_env = _cuppa_env( tmp_path )
    entry = ta.prepare_from_root( cuppa_env, str( root ), ta.FAMILY_CLANG )
    assert entry['bin_dir'] == str( bindir )
    assert entry['qualifier'].startswith( 'local_' )
    assert entry['kind'] == 'external'
    assert entry['family'] == 'clang'
    meta_path = ta.metadata_path( entry['extract_root'] )
    assert os.path.isfile( meta_path )
    with open( meta_path ) as handle:
        meta = json.load( handle )
    assert meta['kind'] == 'external'
    assert meta['prefix'] == os.path.abspath( str( root ) )
    assert os.path.isfile( os.path.join( str( root ), 'bin', 'clang++' ) )


def test_prepare_from_gcc_root( tmp_path ):
    root = tmp_path / 'gcc-snap'
    bindir = root / 'bin'
    bindir.mkdir( parents=True )
    gxx = bindir / 'g++'
    gxx.write_text( '#!/bin/sh\necho "g++ (Debian) 16.0.1"\n' )
    os.chmod( str( gxx ), 0o755 )
    ( bindir / 'gcc' ).write_text( '#!/bin/sh\necho "gcc (Debian) 16.0.1"\n' )
    os.chmod( str( bindir / 'gcc' ), 0o755 )

    cuppa_env = _cuppa_env( tmp_path )
    entry = ta.prepare_from_root( cuppa_env, str( root ), ta.FAMILY_GCC )
    assert entry['family'] == 'gcc'
    assert entry['bin_dir'] == str( bindir )
    assert ta.is_external_registration( entry['extract_root'] )


def test_discover_cached( tmp_path ):
    deps = tmp_path / 'deps'
    qualifier = 'profiles_2026_08_07_27'
    bindir = deps / 'toolchains' / 'clang' / qualifier / 'bin'
    bindir.mkdir( parents=True )
    ( bindir / 'clang++' ).write_text( '#!/bin/sh\n' )

    env = { 'dependencies_root': str( deps ) }
    found = ta.discover_cached( env )
    assert len( found ) == 1
    assert found[0]['qualifier'] == qualifier
    assert found[0]['kind'] == 'cached'
    assert found[0]['family'] == 'clang'


def test_discover_cached_external_gcc( tmp_path ):
    prefix = tmp_path / 'outside'
    bindir = prefix / 'bin'
    bindir.mkdir( parents=True )
    ( bindir / 'g++' ).write_text( '#!/bin/sh\n' )

    deps = tmp_path / 'deps'
    qualifier = 'local_deadbeef'
    extract_root = deps / 'toolchains' / 'gcc' / qualifier
    extract_root.mkdir( parents=True )
    ta.write_registration(
            str( extract_root ), 'gcc', 'external', prefix=str( prefix ),
    )

    found = ta.discover_cached( { 'dependencies_root': str( deps ) } )
    assert len( found ) == 1
    assert found[0]['family'] == 'gcc'
    assert found[0]['bin_dir'] == str( bindir )
    assert found[0]['extract_root'] == str( extract_root )


def test_discover_cached_skips_keys( tmp_path ):
    deps = tmp_path / 'deps'
    for qualifier in ( 'keep_me', 'skip_me' ):
        bindir = deps / 'toolchains' / 'clang' / qualifier / 'bin'
        bindir.mkdir( parents=True )
        ( bindir / 'clang++' ).write_text( '#!/bin/sh\n' )

    found = ta.discover_cached(
        { 'dependencies_root': str( deps ) },
        skip_keys={ ( 'clang', 'skip_me' ) },
    )
    assert [ entry['qualifier'] for entry in found ] == [ 'keep_me' ]


def test_register_skips_existing_name( tmp_path ):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    ( bindir / 'clang++' ).write_text( '#!/bin/sh\n' )

    preexisting = object()
    cuppa_env = {
        'toolchains': { 'clang24_profiles_2026_08_07_27': preexisting },
    }
    added = []

    class FakeClang( object ):
        @classmethod
        def version_from_command( cls, cxx ):
            return {
                'major': 24,
                'minor': 0,
                'version': '24.0.0',
                'short_version': '24.0',
                'name': 'clang24',
            }

        def __init__( self, *args, **kwargs ):
            raise AssertionError( 'should not construct when name exists' )

    names = ta._register_clang_entries(
        cuppa_env,
        [ {
            'family': 'clang',
            'source': str( tmp_path ),
            'qualifier': 'profiles_2026_08_07_27',
            'bin_dir': str( bindir ),
            'extract_root': str( tmp_path ),
            'kind': 'cached',
        } ],
        lambda name, toolchain: added.append( name ),
        lambda name: None,
        FakeClang,
        'libstdc++',
        False,
        skip_existing=True,
    )
    assert names == []
    assert added == []
    assert cuppa_env['toolchains']['clang24_profiles_2026_08_07_27'] is preexisting


def test_register_gcc_sets_ownership_and_name( tmp_path ):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    gxx = bindir / 'g++'
    gxx.write_text( '#!/bin/sh\necho "g++ (Debian) 16.0.1"\n' )
    os.chmod( str( gxx ), 0o755 )

    dep_root = tmp_path / 'deps' / 'toolchains' / 'gcc' / 'local_abcd1234'
    dep_root.mkdir( parents=True )
    cuppa_env = { 'toolchains': {} }
    added = []

    class FakeGcc( object ):
        @classmethod
        def version_from_command( cls, cxx, prefix ):
            return {
                'major': 16,
                'minor': 0,
                'version': '16.0',
                'short_version': '160',
                'name': 'gcc160',
                'toolchain': prefix,
            }

        def __init__( self, name, cxx_version, reported, cxx_path ):
            self._name = name
            self._cxx_path = cxx_path
            self.values = {
                'CXX': os.path.join( cxx_path, 'g++' ),
                'CC': os.path.join( cxx_path, 'gcc' ),
            }

    names = ta._register_gcc_entries(
        cuppa_env,
        [ {
            'family': 'gcc',
            'source': str( tmp_path ),
            'qualifier': 'local_abcd1234',
            'bin_dir': str( bindir ),
            'extract_root': str( dep_root ),
            'kind': 'external',
        } ],
        lambda name, toolchain: added.append( ( name, toolchain ) ),
        lambda name: None,
        FakeGcc,
        skip_existing=False,
    )
    assert names == [ 'gcc16_local_abcd1234' ]
    assert added[0][0] == 'gcc16_local_abcd1234'
    assert added[0][1]._toolchain_dep_root == str( dep_root )


def test_wipe_external_registration_leaves_prefix( tmp_path ):
    prefix = tmp_path / 'outside'
    bindir = prefix / 'bin'
    bindir.mkdir( parents=True )
    marker = bindir / 'g++'
    marker.write_text( '#!/bin/sh\n' )

    extract_root = tmp_path / 'deps' / 'toolchains' / 'gcc' / 'local_abcd'
    ta.write_registration(
            str( extract_root ), 'gcc', 'external', prefix=str( prefix ),
    )
    assert ta.is_external_registration( str( extract_root ) )
    import shutil
    shutil.rmtree( str( extract_root ) )
    assert marker.is_file()
    assert not extract_root.exists()


@pytest.mark.skipif(
    not getattr( __import__( 'shutil' ), 'which', lambda n: None )( 'ar' )
    or not getattr( __import__( 'shutil' ), 'which', lambda n: None )( 'tar' ),
    reason='ar/tar required to build and extract a .deb fixture',
)
def test_prepare_from_deb_archive( tmp_path ):
    """Minimal .deb with nested bin/g++ extracts under toolchains/gcc/."""
    payload = tmp_path / 'payload'
    nested = payload / 'usr' / 'lib' / 'gcc-snapshot' / 'bin'
    nested.mkdir( parents=True )
    gxx = nested / 'g++'
    gxx.write_text( '#!/bin/sh\necho "g++ (Debian) 16.0.1"\n' )
    os.chmod( str( gxx ), 0o755 )
    ( nested / 'gcc' ).write_text( '#!/bin/sh\necho "gcc (Debian) 16.0.1"\n' )
    os.chmod( str( nested / 'gcc' ), 0o755 )

    data_tar = tmp_path / 'data.tar.gz'
    with tarfile.open( str( data_tar ), 'w:gz' ) as archive:
        archive.add( str( payload / 'usr' ), arcname='usr' )

    staging = tmp_path / 'ar-stage'
    staging.mkdir()
    ( staging / 'debian-binary' ).write_text( '2.0\n' )
    control_tar = staging / 'control.tar.gz'
    with tarfile.open( str( control_tar ), 'w:gz' ) as archive:
        pass
    import shutil
    shutil.copy( str( data_tar ), str( staging / 'data.tar.gz' ) )
    deb_path = tmp_path / 'gcc-snapshot_20260725-1_amd64.deb'
    subprocess.check_call(
            [ 'ar', 'r', str( deb_path ), 'debian-binary', 'control.tar.gz', 'data.tar.gz' ],
            cwd=str( staging ),
    )

    cuppa_env = _cuppa_env( tmp_path )
    entry = ta.prepare_from_archive( cuppa_env, str( deb_path ) )
    assert entry['family'] == 'gcc'
    assert entry['qualifier'] == 'gcc_snapshot_20260725_1_amd64'
    assert entry['bin_dir'].endswith( os.path.join( 'gcc-snapshot', 'bin' ) )
    assert os.path.isfile( os.path.join( entry['bin_dir'], 'g++' ) )
    assert 'toolchains/gcc/' in entry['extract_root'].replace( '\\', '/' )


def test_remind_reuse_names( caplog ):
    import logging
    cuppa_env = {
        'toolchain_archive_names': [ 'clang24_profiles_2026_08_07_27' ],
    }
    with caplog.at_level( logging.INFO ):
        ta.remind_reuse_names( cuppa_env )
    assert any(
        '--toolchains=clang24_profiles_2026_08_07_27' in record.getMessage()
        for record in caplog.records
    )


def test_remind_reuse_names_noop_without_names( caplog ):
    import logging
    with caplog.at_level( logging.INFO ):
        ta.remind_reuse_names( {} )
    assert not any( 'Reuse this toolchain' in record.getMessage() for record in caplog.records )
