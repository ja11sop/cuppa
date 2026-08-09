#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.configure import load_settings_file, read_setting, upsert_setting
from cuppa.dependencies.boost.version_and_location import (
        BOOST_LATEST_VERSION_KEY,
        archive_present_under_downloads,
        boost_latest_conf_path,
        boost_location_id,
        boost_version_key,
        current_boost_release,
        maybe_persist_boost_latest,
        resolve_boost_latest_version,
        version_is_higher,
)


pytestmark = pytest.mark.unit


class Env( object ):
    def __init__( self, options=None, values=None ):
        self._options = options or {}
        self._values = values or {}

    def get_option( self, name ):
        return self._options.get( name )

    def get( self, key, default=None ):
        return self._values.get( key, default )

    def __contains__( self, key ):
        return key in self._values

    def __getitem__( self, key ):
        return self._values[key]

    def __setitem__( self, key, value ):
        self._values[key] = value


def test_boost_location_id_default_does_not_force_latest_token():
    location, version, base, _patched = boost_location_id(
            Env( {}, { 'thirdparty': None } )
    )
    assert location is None
    assert version is None
    assert base is None


def test_boost_location_id_boost_latest_sets_latest_token():
    _location, version, _base, _patched = boost_location_id(
            Env( { 'boost-latest': True }, { 'thirdparty': None } )
    )
    assert version == 'latest'


def test_version_is_higher_compares_dotted_and_underscored():
    assert version_is_higher( '1.92.0', '1.91.0' )
    assert version_is_higher( '1_92_0', '1.91.0' )
    assert not version_is_higher( '1.91.0', '1.92.0' )
    assert version_is_higher( '1.92.0', None )
    assert boost_version_key( '1.91.0' ) == ( 1, 91, 0 )


def test_boost_latest_conf_path_project_when_downloads_under_sconstruct( tmp_path ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )
    env = Env( values={
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
    } )
    assert boost_latest_conf_path( env ) == os.path.join( str( project ), 'configure.conf' )


def test_boost_latest_conf_path_global_when_downloads_outside_project( tmp_path, monkeypatch ):
    project = tmp_path / 'proj'
    project.mkdir()
    downloads = tmp_path / 'shared_downloads'
    downloads.mkdir()
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setenv( 'HOME', str( fake_home ) )
    # expanduser("~") uses HOME on Linux
    env = Env( values={
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
    } )
    path = boost_latest_conf_path( env )
    assert path == os.path.join( str( fake_home ), '.cuppaconfig' )


def test_upsert_setting_preserves_other_keys( tmp_path ):
    conf = tmp_path / 'configure.conf'
    conf.write_text( "dbg = True\ntoolchains = ['gcc']\n", encoding='utf-8' )
    upsert_setting( str( conf ), BOOST_LATEST_VERSION_KEY, '1.92.0' )
    settings = load_settings_file( str( conf ) )
    assert settings['dbg'] is True
    assert settings['toolchains'] == ['gcc']
    assert settings[BOOST_LATEST_VERSION_KEY] == '1.92.0'


def test_resolve_prefers_stored_without_scrape( tmp_path, monkeypatch ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )
    conf = project / 'configure.conf'
    conf.write_text( "{} = 1.92.0\n".format( BOOST_LATEST_VERSION_KEY ), encoding='utf-8' )

    def fail_scrape():
        raise AssertionError( 'scrape should not run' )

    monkeypatch.setattr(
            'cuppa.dependencies.boost.version_and_location.scrape_latest_boost_version',
            fail_scrape,
    )
    env = Env( values={
        'offline': False,
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
    } )
    version, source = resolve_boost_latest_version( env, force_scrape=False )
    assert version == '1.92.0'
    assert source == 'stored'


def test_resolve_compiled_in_when_nothing_stored( tmp_path, monkeypatch ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )

    def fail_scrape():
        raise AssertionError( 'scrape should not run' )

    monkeypatch.setattr(
            'cuppa.dependencies.boost.version_and_location.scrape_latest_boost_version',
            fail_scrape,
    )
    env = Env( values={
        'offline': False,
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
    } )
    version, source = resolve_boost_latest_version( env, force_scrape=False )
    assert version == current_boost_release()
    assert source == 'compiled_in'


def test_resolve_force_scrape_uses_network_result( tmp_path, monkeypatch ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )
    monkeypatch.setattr(
            'cuppa.dependencies.boost.version_and_location.scrape_latest_boost_version',
            lambda: '1.93.0',
    )
    env = Env( values={
        'offline': False,
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
    } )
    version, source = resolve_boost_latest_version( env, force_scrape=True )
    assert version == '1.93.0'
    assert source == 'scraped'


def test_resolve_failed_scrape_marks_fallback( tmp_path, monkeypatch ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )
    monkeypatch.setattr(
            'cuppa.dependencies.boost.version_and_location.scrape_latest_boost_version',
            lambda: None,
    )
    env = Env( values={
        'offline': False,
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
    } )
    version, source = resolve_boost_latest_version( env, force_scrape=True )
    assert version == current_boost_release()
    assert source == 'scrape_failed_fallback'


def test_maybe_persist_updates_only_when_higher_and_archive_present( tmp_path ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )
    archive_name = 'https_archives.boost.io_release_1.92.0_source_boost_1_92_0.tar.gz'
    ( downloads / archive_name ).write_bytes( b'archive' )

    class Loc( object ):
        _local_folder = archive_name

        def get_cached_archive( self, cache_root, path ):
            candidate = os.path.join( cache_root, path )
            return candidate if os.path.exists( candidate ) else None

    env = Env( values={
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
        'configured_options': {},
    } )
    conf = boost_latest_conf_path( env )
    upsert_setting( conf, BOOST_LATEST_VERSION_KEY, '1.91.0' )

    assert maybe_persist_boost_latest( env, '1.92.0', 'scraped', Loc() )
    assert read_setting( conf, BOOST_LATEST_VERSION_KEY ) == '1.92.0'

    assert not maybe_persist_boost_latest( env, '1.90.0', 'scraped', Loc() )
    assert read_setting( conf, BOOST_LATEST_VERSION_KEY ) == '1.92.0'


def test_maybe_persist_skips_failed_scrape_fallback( tmp_path ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )
    archive_name = 'boost_archive.tar.gz'
    ( downloads / archive_name ).write_bytes( b'archive' )

    class Loc( object ):
        _local_folder = archive_name

        def get_cached_archive( self, cache_root, path ):
            candidate = os.path.join( cache_root, path )
            return candidate if os.path.exists( candidate ) else None

    env = Env( values={
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( project ),
        'abs_sconstruct_dir': str( project ),
    } )
    assert not maybe_persist_boost_latest(
            env, current_boost_release(), 'scrape_failed_fallback', Loc()
    )
    assert not os.path.exists( boost_latest_conf_path( env ) )


def test_archive_present_helper( tmp_path ):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    name = 'boost_1_91_0.tar.gz'
    ( downloads / name ).write_bytes( b'x' )

    class Loc( object ):
        _local_folder = name

        def get_cached_archive( self, cache_root, path ):
            for archive in os.listdir( cache_root ):
                if archive == path:
                    return os.path.join( cache_root, archive )
            return None

    env = Env( values={ 'downloads_root': str( downloads ) } )
    assert archive_present_under_downloads( env, Loc() )
