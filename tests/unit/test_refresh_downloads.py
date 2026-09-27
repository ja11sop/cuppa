#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for --refresh-downloads (package archive force re-fetch)."""

from types import SimpleNamespace

import pytest
import SCons.Errors

from cuppa.package_managers import gitlab as gitlab_mod
from cuppa.package_managers.gitlab import (
        GitlabPackageDependency,
        GitlabPackageDependencyException,
        audit_refresh_downloads,
        begin_refresh_downloads_session,
        package_file_name,
        reset_refresh_downloads_session_for_tests,
)
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


def test_refresh_downloads_offline_refuses( tmp_path, monkeypatch ):
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.freedesktop_os_release',
            lambda: { 'ID': 'debian' },
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.system',
            lambda: 'Linux',
    )
    env, downloads, _deps = _env( tmp_path, offline=True )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    ( cache / archive_name ).write_bytes( b'stale' )

    begin_refresh_downloads_session( '' )
    with pytest.raises( GitlabPackageDependencyException ) as caught:
        GitlabPackageDependency(
                env,
                registry='https://gitlab.example/api/v4/projects/1',
                package='widget',
                version='1.0',
                variant='rel',
                dependency_name='widget',
        )
    assert 'OFFLINE' in str( caught.value )
    assert 'refresh-downloads' in str( caught.value )


def test_refresh_downloads_clears_cache_and_refetches( tmp_path, monkeypatch ):
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.freedesktop_os_release',
            lambda: { 'ID': 'debian' },
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.system',
            lambda: 'Linux',
    )
    env, downloads, dependencies = _env( tmp_path )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    stale = cache / archive_name
    stale.write_bytes( b'stale-bytes' )
    extract = dependencies / 'gcc15_rel_x86_64_cxx2c' / 'widget' / '1.0'
    extract.mkdir( parents=True )
    ( extract / 'include' ).mkdir()
    ( extract / 'include' / 'widget.hpp' ).write_text( 'old' )

    fetched = {}

    def fake_download( candidates, cache_dir, custom_token=None, log_id=None ):
        dest = os_path_join( cache_dir, archive_name )
        with open( dest, 'wb' ) as handle:
            handle.write( b'fresh-bytes' )
        fetched['dest'] = dest
        return dest, archive_name, 'stem'

    def fake_extract( archive, extraction_dir ):
        include = os_path_join(
                extraction_dir, 'widget', '1.0', 'include'
        )
        os_makedirs( include, exist_ok=True )
        with open( os_path_join( include, 'widget.hpp' ), 'w' ) as handle:
            handle.write( 'new' )
        return 0

    import os as os_mod
    os_path_join = os_mod.path.join
    os_makedirs = os_mod.makedirs

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.download_first_available_package',
            fake_download,
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.extract_package_archive',
            fake_extract,
    )

    begin_refresh_downloads_session( '' )
    dep = GitlabPackageDependency(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='1.0',
            variant='rel',
            dependency_name='widget',
    )
    assert fetched.get( 'dest' )
    assert open( fetched['dest'], 'rb' ).read() == b'fresh-bytes'
    assert ( extract / 'include' / 'widget.hpp' ).read_text() == 'new'
    assert dep.package_dir().endswith( os_mod.path.join( 'widget', '1.0' ) )


def test_refresh_downloads_develop_skips_clear( tmp_path, monkeypatch ):
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.freedesktop_os_release',
            lambda: { 'ID': 'debian' },
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.system',
            lambda: 'Linux',
    )
    prefix = tmp_path / 'prefix'
    ( prefix / 'include' ).mkdir( parents=True )
    ( prefix / 'lib' ).mkdir()
    env, downloads, _deps = _env( tmp_path, develop=True )
    archive_name = package_file_name( env, package='widget', variant='rel' )
    cache = downloads / 'packages' / 'widget' / '1.0'
    cache.mkdir( parents=True )
    stale = cache / archive_name
    stale.write_bytes( b'stale' )

    begin_refresh_downloads_session( 'widget' )
    GitlabPackageDependency(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='1.0',
            variant='rel',
            develop=str( prefix ),
            dependency_name='widget',
    )
    assert stale.read_bytes() == b'stale'
    audit_refresh_downloads( env )


def test_audit_refresh_downloads_unknown_name():
    begin_refresh_downloads_session( 'missing_pkg' )
    with pytest.raises( SCons.Errors.StopError ) as caught:
        audit_refresh_downloads()
    assert 'missing_pkg' in str( caught.value )


def test_begin_refresh_downloads_session_selective_and_bare():
    begin_refresh_downloads_session( '' )
    assert gitlab_mod.refresh_downloads_applies( 'a', 'a' )
    begin_refresh_downloads_session( 'widget,gizmo' )
    assert gitlab_mod.refresh_downloads_applies( 'widget', 'widget' )
    assert gitlab_mod.refresh_downloads_applies( None, 'gizmo' )
    assert not gitlab_mod.refresh_downloads_applies( 'other', 'other' )
