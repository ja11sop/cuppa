#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.toolchains import toolchain_archive as ta


pytestmark = pytest.mark.unit


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
    assert ta.toolchain_name( 24, ta.qualifier_for_archive( url ) ) == \
        'clang24_profiles_2026_08_07_27'


def test_qualifier_for_non_release_url_uses_stem():
    url = 'https://example.com/builds/clang-profiles-linux-x86_64.tar.gz'
    assert ta.release_tag_from_url( url ) is None
    assert ta.qualifier_for_archive( url ) == 'clang_profiles_linux_x86_64'


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


def test_prepare_from_root( tmp_path ):
    root = tmp_path / 'clang'
    bindir = root / 'bin'
    bindir.mkdir( parents=True )
    clangxx = bindir / 'clang++'
    clangxx.write_text( '#!/bin/sh\necho "clang version 24.0.0"\n' )
    os.chmod( str( clangxx ), 0o755 )

    class Env( dict ):
        def get_option( self, name, default=None ):
            return self.get( name, default )

    cuppa_env = Env( {
        'sconstruct_dir': str( tmp_path ),
        'downloads_root': str( tmp_path / 'dl' ),
        'dependencies_root': str( tmp_path / 'deps' ),
        'offline': False,
    } )
    entry = ta.prepare_from_root( cuppa_env, str( root ) )
    assert entry['bin_dir'] == str( bindir )
    assert entry['qualifier'].startswith( 'local_' )


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


def test_discover_cached_skips_qualifier( tmp_path ):
    deps = tmp_path / 'deps'
    for qualifier in ( 'keep_me', 'skip_me' ):
        bindir = deps / 'toolchains' / 'clang' / qualifier / 'bin'
        bindir.mkdir( parents=True )
        ( bindir / 'clang++' ).write_text( '#!/bin/sh\n' )

    found = ta.discover_cached(
        { 'dependencies_root': str( deps ) },
        skip_qualifiers={ 'skip_me' },
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

    names = ta._register_entries(
        cuppa_env,
        [ {
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
