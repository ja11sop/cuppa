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

    env = {
        'sconstruct_dir': str( tmp_path ),
        'downloads_root': str( tmp_path / 'dl' ),
        'dependencies_root': str( tmp_path / 'deps' ),
        'offline': False,
    }
    # Minimal stand-in: prepare_from_root only needs expand path
    class Env( dict ):
        def get_option( self, name, default=None ):
            return self.get( name, default )

    cuppa_env = Env( env )
    entry = ta.prepare_from_root( cuppa_env, str( root ) )
    assert entry['bin_dir'] == str( bindir )
    assert entry['qualifier'].startswith( 'local_' )
