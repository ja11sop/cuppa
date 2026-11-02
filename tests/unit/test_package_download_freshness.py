#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for online GitLab package archive freshness."""

from types import SimpleNamespace

import pytest

from cuppa.package_managers.gitlab import (
        GitlabPackageDependency,
        package_file_name,
        reset_refresh_downloads_session_for_tests,
)
from cuppa.package_managers.package_download_freshness import (
        MATCH,
        STALE,
        UNVERIFIED,
        check_cached_archive_freshness,
        identity_from_headers,
        read_archive_freshness,
        record_archive_freshness_from_head,
        url_for_cached_archive,
        write_archive_freshness,
)
from cuppa.utility.download import DownloadError
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


@pytest.fixture( autouse=True )
def _reset_refresh_session():
    reset_refresh_downloads_session_for_tests()
    yield
    reset_refresh_downloads_session_for_tests()


def _env( tmp_path, **kwargs ):
    downloads = tmp_path / 'downloads'
    dependencies = tmp_path / 'dependencies'
    downloads.mkdir()
    dependencies.mkdir()
    toolchain = SimpleNamespace( package_name=lambda: 'gcc15' )
    variant = SimpleNamespace( name=lambda: 'rel' )
    defaults = dict(
            offline=False,
            develop=False,
            clean=False,
            dump=False,
            no_exec=False,
            storage_resolve_only=False,
            downloads_root=str( downloads ),
            dependencies_root=str( dependencies ),
            sconstruct_dir=str( tmp_path ),
            toolchain=toolchain,
            variant=variant,
            target_arch='x86_64',
            abi='cxx2c',
    )
    defaults.update( kwargs )
    return FakeEnv( **defaults ), downloads, dependencies


def _linux( monkeypatch ):
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.freedesktop_os_release',
            lambda: { 'ID': 'debian' },
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.system',
            lambda: 'Linux',
    )


def test_identity_from_headers_prefers_checksum():
    assert identity_from_headers( {
            'x-checksum-sha256': 'AbC',
            'last-modified': 'Mon, 01 Jan 2026 00:00:00 GMT',
            'content-length': '12',
    } ) == 'sha256:abc'


def test_identity_from_headers_falls_back_to_meta():
    assert identity_from_headers( {
            'last-modified': 'Mon, 01 Jan 2026 00:00:00 GMT',
            'content-length': '12',
    } ) == 'meta:Mon, 01 Jan 2026 00:00:00 GMT|12'


def test_identity_from_headers_none_without_usable_fields():
    assert identity_from_headers( {} ) is None
    assert identity_from_headers( None ) is None


def test_sidecar_round_trip( tmp_path ):
    archive = tmp_path / 'widget.tar.gz'
    archive.write_bytes( b'data' )
    assert read_archive_freshness( str( archive ) ) is None
    write_archive_freshness( str( archive ), 'sha256:deadbeef' )
    assert read_archive_freshness( str( archive ) ) == 'sha256:deadbeef'


def test_url_for_cached_archive_matches_basename():
    candidates = [
            ( 'stem', 'a.tar.gz', 'https://example/a.tar.gz', None ),
            ( 'stem', 'b.tar.gz', 'https://example/b.tar.gz', None ),
    ]
    assert url_for_cached_archive(
            candidates, '/cache/b.tar.gz'
    ) == 'https://example/b.tar.gz'
    assert url_for_cached_archive( candidates, '/cache/missing.tar.gz' ) is None


def test_check_match_stale_unverified( tmp_path ):
    archive = tmp_path / 'widget.tar.gz'
    archive.write_bytes( b'data' )
    write_archive_freshness( str( archive ), 'sha256:aaa' )

    def head_match( url, headers=None ):
        return 200, { 'x-checksum-sha256': 'aaa' }

    def head_stale( url, headers=None ):
        return 200, { 'x-checksum-sha256': 'bbb' }

    def head_404( url, headers=None ):
        return 404, {}

    def head_fail( url, headers=None ):
        raise DownloadError( 'network down' )

    assert check_cached_archive_freshness(
            'https://example/widget.tar.gz',
            str( archive ),
            head=head_match,
            auth_headers={},
    )[0] == MATCH

    assert check_cached_archive_freshness(
            'https://example/widget.tar.gz',
            str( archive ),
            head=head_stale,
            auth_headers={},
    )[0] == STALE

    assert check_cached_archive_freshness(
            'https://example/widget.tar.gz',
            str( archive ),
            head=head_404,
            auth_headers={},
    )[0] == STALE

    outcome, _identity, detail = check_cached_archive_freshness(
            'https://example/widget.tar.gz',
            str( archive ),
            head=head_fail,
            auth_headers={},
    )
    assert outcome == UNVERIFIED
    assert 'network' in detail

    # Missing sidecar → stale once.
    other = tmp_path / 'other.tar.gz'
    other.write_bytes( b'x' )
    assert check_cached_archive_freshness(
            'https://example/other.tar.gz',
            str( other ),
            head=head_match,
            auth_headers={},
    )[0] == STALE


def test_record_archive_freshness_from_head( tmp_path ):
    archive = tmp_path / 'widget.tar.gz'
    archive.write_bytes( b'data' )

    def head_ok( url, headers=None ):
        return 200, { 'x-checksum-sha256': 'abc123' }

    identity = record_archive_freshness_from_head(
            'https://example/widget.tar.gz',
            str( archive ),
            head=head_ok,
            auth_headers={},
    )
    assert identity == 'sha256:abc123'
    assert read_archive_freshness( str( archive ) ) == 'sha256:abc123'


def test_dependency_reuses_when_fresh( tmp_path, monkeypatch ):
    _linux( monkeypatch )
    env, downloads, dependencies = _env( tmp_path )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    archive = cache / archive_name
    archive.write_bytes( b'cached' )
    write_archive_freshness( str( archive ), 'sha256:same' )
    extract = dependencies / 'gcc15_rel_x86_64_cxx2c' / 'widget' / '1.0'
    ( extract / 'include' ).mkdir( parents=True )
    ( extract / 'include' / 'widget.hpp' ).write_text( 'ok' )

    fetched = []

    def fake_download( *args, **kwargs ):
        fetched.append( True )
        raise AssertionError( 'should not download' )

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.download_first_available_package',
            fake_download,
    )
    monkeypatch.setattr(
            'cuppa.utility.download.http_head',
            lambda url, headers=None: ( 200, { 'x-checksum-sha256': 'same' } ),
    )

    GitlabPackageDependency(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='1.0',
            variant='rel',
            dependency_name='widget',
    )
    assert not fetched
    assert archive.read_bytes() == b'cached'
    assert ( extract / 'include' / 'widget.hpp' ).read_text() == 'ok'


def test_dependency_refetches_when_stale( tmp_path, monkeypatch ):
    _linux( monkeypatch )
    env, downloads, dependencies = _env( tmp_path )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    archive = cache / archive_name
    archive.write_bytes( b'stale' )
    write_archive_freshness( str( archive ), 'sha256:old' )
    extract = dependencies / 'gcc15_rel_x86_64_cxx2c' / 'widget' / '1.0'
    ( extract / 'include' ).mkdir( parents=True )
    ( extract / 'include' / 'widget.hpp' ).write_text( 'old' )

    import os as os_mod

    def fake_download( candidates, cache_dir, custom_token=None, log_id=None ):
        dest = os_mod.path.join( cache_dir, archive_name )
        with open( dest, 'wb' ) as handle:
            handle.write( b'fresh' )
        return dest, archive_name, 'stem'

    def fake_extract( archive_path, extraction_dir ):
        include = os_mod.path.join(
                extraction_dir, 'widget', '1.0', 'include'
        )
        os_mod.makedirs( include, exist_ok=True )
        with open( os_mod.path.join( include, 'widget.hpp' ), 'w' ) as handle:
            handle.write( 'new' )
        return 0

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.download_first_available_package',
            fake_download,
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.extract_package_archive',
            fake_extract,
    )
    monkeypatch.setattr(
            'cuppa.utility.download.http_head',
            lambda url, headers=None: ( 200, { 'x-checksum-sha256': 'new' } ),
    )

    GitlabPackageDependency(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='1.0',
            variant='rel',
            dependency_name='widget',
    )
    assert archive.read_bytes() == b'fresh'
    assert ( extract / 'include' / 'widget.hpp' ).read_text() == 'new'
    assert read_archive_freshness( str( archive ) ) == 'sha256:new'


def test_dependency_unverified_reuses_cache( tmp_path, monkeypatch ):
    _linux( monkeypatch )
    env, downloads, dependencies = _env( tmp_path )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    archive = cache / archive_name
    archive.write_bytes( b'cached' )
    write_archive_freshness( str( archive ), 'sha256:same' )
    extract = dependencies / 'gcc15_rel_x86_64_cxx2c' / 'widget' / '1.0'
    ( extract / 'include' ).mkdir( parents=True )
    ( extract / 'include' / 'widget.hpp' ).write_text( 'ok' )

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.download_first_available_package',
            lambda *a, **k: ( _ for _ in () ).throw( AssertionError( 'no download' ) ),
    )
    monkeypatch.setattr(
            'cuppa.utility.download.http_head',
            lambda url, headers=None: ( _ for _ in () ).throw(
                    DownloadError( '401 unauthorized' )
            ),
    )

    GitlabPackageDependency(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='1.0',
            variant='rel',
            dependency_name='widget',
    )
    assert archive.read_bytes() == b'cached'
    assert ( extract / 'include' / 'widget.hpp' ).read_text() == 'ok'


def test_dependency_offline_skips_head( tmp_path, monkeypatch ):
    _linux( monkeypatch )
    env, downloads, dependencies = _env( tmp_path, offline=True )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    archive = cache / archive_name
    archive.write_bytes( b'cached' )
    extract = dependencies / 'gcc15_rel_x86_64_cxx2c' / 'widget' / '1.0'
    ( extract / 'include' ).mkdir( parents=True )
    ( extract / 'include' / 'widget.hpp' ).write_text( 'ok' )

    heads = []

    def tracking_head( url, headers=None ):
        heads.append( url )
        return 200, { 'x-checksum-sha256': 'x' }

    monkeypatch.setattr( 'cuppa.utility.download.http_head', tracking_head )

    GitlabPackageDependency(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='1.0',
            variant='rel',
            dependency_name='widget',
    )
    assert heads == []
    assert archive.read_bytes() == b'cached'


def test_dependency_dry_run_stale_does_not_refetch( tmp_path, monkeypatch ):
    _linux( monkeypatch )
    env, downloads, dependencies = _env( tmp_path, no_exec=True )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    archive = cache / archive_name
    archive.write_bytes( b'stale' )
    write_archive_freshness( str( archive ), 'sha256:old' )
    extract = dependencies / 'gcc15_rel_x86_64_cxx2c' / 'widget' / '1.0'
    ( extract / 'include' ).mkdir( parents=True )
    ( extract / 'include' / 'widget.hpp' ).write_text( 'old' )

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.download_first_available_package',
            lambda *a, **k: ( _ for _ in () ).throw( AssertionError( 'no download' ) ),
    )
    monkeypatch.setattr(
            'cuppa.utility.download.http_head',
            lambda url, headers=None: ( 200, { 'x-checksum-sha256': 'new' } ),
    )

    GitlabPackageDependency(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='1.0',
            variant='rel',
            dependency_name='widget',
    )
    assert archive.read_bytes() == b'stale'
    assert ( extract / 'include' / 'widget.hpp' ).read_text() == 'old'
