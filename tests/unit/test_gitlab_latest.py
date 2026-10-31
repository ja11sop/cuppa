#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os
import re

import pytest
import SCons.Errors

from cuppa.build_with_package import package_dependency
from cuppa.package_managers import gitlab_latest as gl
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_project_packages_api_base_strips_generic_suffix():
    assert gl.project_packages_api_base(
            'https://gitlab.example/api/v4/projects/123/packages/generic'
    ) == 'https://gitlab.example/api/v4/projects/123/packages'


def test_project_packages_api_base_accepts_project_root():
    assert gl.project_packages_api_base(
            'https://gitlab.example/api/v4/projects/dependencies%2Fregistry'
    ) == 'https://gitlab.example/api/v4/projects/dependencies%2Fregistry/packages'


def test_select_latest_version_numeric():
    assert gl.select_latest_version( [ '1.2', '1.10', '1.9' ] ) == '1.10'


def test_select_latest_version_empty():
    assert gl.select_latest_version( [] ) is None


def test_list_generic_package_versions_filters_exact_name():
    def opener( url, headers ):
        assert 'package_type=generic' in url
        assert 'package_name=widget' in url
        return [
                { 'name': 'widget', 'version': '1.0' },
                { 'name': 'widget-extra', 'version': '9.9' },
                { 'name': 'widget', 'version': '1.1' },
        ]

    versions = gl.list_generic_package_versions(
            'https://gitlab.example/api/v4/projects/1',
            'widget',
            opener=opener,
    )
    assert versions == [ '1.0', '1.1' ]


def test_list_generic_package_versions_paginates():
    seen = []

    def opener( url, headers ):
        # Avoid substring traps like ``page=1`` inside ``per_page=100``.
        match = re.search( r'[?&]page=(\d+)', url )
        page = int( match.group( 1 ) ) if match else 0
        seen.append( page )
        if page == 1:
            return [
                    { 'name': 'widget', 'version': 'v{}'.format( i ) }
                    for i in range( 100 )
            ]
        if page == 2:
            return [ { 'name': 'widget', 'version': 'v100' } ]
        return []

    versions = gl.list_generic_package_versions(
            'https://gitlab.example/api/v4/projects/1',
            'widget',
            opener=opener,
    )
    assert seen == [ 1, 2 ]
    assert len( versions ) == 101
    assert versions[ -1 ] == 'v100'


def test_resolve_latest_online_remembers( tmp_path, monkeypatch ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )

    def opener( url, headers ):
        return [
                { 'name': 'widget', 'version': '1.2' },
                { 'name': 'widget', 'version': '1.10' },
        ]

    env = FakeEnv( offline=False )
    latest = gl.resolve_latest_package_version(
            env,
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            opener=opener,
    )
    assert latest == '1.10'
    key = gl.registry_latest_conf_key(
            'https://gitlab.example/api/v4/projects/1', 'widget'
    )
    assert gl.read_setting( conf, key ) == '1.10'


def test_registry_latest_conf_path_project_when_downloads_under_sconstruct( tmp_path ):
    project = tmp_path / 'proj'
    downloads = project / 'downloads'
    downloads.mkdir( parents=True )
    env = FakeEnv(
            downloads_root=str( downloads ),
            sconstruct_dir=str( project ),
            abs_sconstruct_dir=str( project ),
    )
    assert gl.registry_latest_conf_path( env ) == os.path.join(
            str( project ), 'configure.conf'
    )


def test_registry_latest_conf_path_global_when_downloads_outside_project( tmp_path, monkeypatch ):
    project = tmp_path / 'proj'
    project.mkdir()
    downloads = tmp_path / 'shared_downloads'
    downloads.mkdir()
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setenv( 'HOME', str( fake_home ) )
    env = FakeEnv(
            downloads_root=str( downloads ),
            sconstruct_dir=str( project ),
            abs_sconstruct_dir=str( project ),
    )
    assert gl.registry_latest_conf_path( env ) == os.path.join(
            str( fake_home ), '.cuppaconfig'
    )


def test_resolve_latest_offline_uses_remembered( tmp_path, monkeypatch ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'widget' )
    gl.upsert_setting( conf, key, repr( '3.1' ) )

    env = FakeEnv( offline=True )
    assert gl.resolve_latest_package_version(
            env, registry=registry, package='widget'
    ) == '3.1'


def test_resolve_latest_offline_without_memory_fails():
    env = FakeEnv( offline=True )
    with pytest.raises( gl.GitlabLatestError ):
        gl.resolve_latest_package_version(
                env,
                registry='https://gitlab.example/api/v4/projects/1',
                package='missing',
        )


def _plant_extract( root, package, version ):
    path = root / 'gcc15_rel_x86_64_cxx2c' / package / version
    path.mkdir( parents=True )
    ( path / 'payload.hpp' ).write_text( 'ok', encoding='utf-8' )
    return path


def test_package_pin_tree_ignores_download_cache( tmp_path ):
    deps = tmp_path / 'dependencies'
    archive = deps / 'packages' / 'boost' / '1.92'
    archive.mkdir( parents=True )
    ( archive / 'boost.tar.gz' ).write_bytes( b'x' )
    env = FakeEnv( dependencies_root=str( deps ), downloads_root=str( deps ) )
    assert gl.package_pin_tree_exists( env, 'boost', '1.92' ) is False


def test_resolve_latest_network_failure_uses_remembered( tmp_path, monkeypatch, caplog ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'widget' )
    gl.upsert_setting( conf, key, repr( '1.10' ) )
    deps = tmp_path / 'dependencies'
    _plant_extract( deps, 'widget', '1.10' )
    remembered = []
    monkeypatch.setattr(
            gl, 'remember_registry_latest',
            lambda *args, **kwargs: remembered.append( args ),
    )

    def opener( url, headers ):
        raise gl.URLError( 'Temporary failure in name resolution' )

    env = FakeEnv( offline=False, dependencies_root=str( deps ) )
    with caplog.at_level( 'WARNING', logger='cuppa' ):
        assert gl.resolve_latest_package_version(
                env, registry=registry, package='widget',
                opener=opener, dependency_name='widget_package',
        ) == '1.10'
        assert remembered == []
        assert 'widget_package' in caplog.text
        assert 'registry unreachable' in caplog.text
        assert '1.10' in caplog.text
        assert 'might not be the latest' in caplog.text


def test_resolve_latest_network_failure_without_extract_fails( tmp_path, monkeypatch ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'widget' )
    gl.upsert_setting( conf, key, repr( '1.10' ) )
    deps = tmp_path / 'dependencies'
    empty = deps / 'gcc15_rel_x86_64_cxx2c' / 'widget' / '1.10'
    empty.mkdir( parents=True )

    def opener( url, headers ):
        raise gl.URLError( 'Temporary failure in name resolution' )

    env = FakeEnv( offline=False, dependencies_root=str( deps ) )
    with pytest.raises( gl.GitlabLatestNetworkError ):
        gl.resolve_latest_package_version(
                env, registry=registry, package='widget', opener=opener,
        )


def _http_opener( code, msg='nope' ):
    def opener( url, headers ):
        raise gl.HTTPError( url, code, msg, {}, None )
    return opener


def test_resolve_latest_auth_failure_uses_remembered_extract( tmp_path, monkeypatch, caplog ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'boost' )
    gl.upsert_setting( conf, key, repr( '1.92' ) )
    deps = tmp_path / 'dependencies'
    _plant_extract( deps, 'boost', '1.92' )
    remembered = []
    monkeypatch.setattr(
            gl, 'remember_registry_latest',
            lambda *args, **kwargs: remembered.append( args ),
    )
    env = FakeEnv( offline=False, dependencies_root=str( deps ) )
    with caplog.at_level( 'WARNING', logger='cuppa' ):
        assert gl.resolve_latest_package_version(
                env, registry=registry, package='boost',
                opener=_http_opener( 401, 'Unauthorized' ),
                dependency_name='boost_package',
        ) == '1.92'
        assert remembered == []
        assert 'boost_package' in caplog.text
        assert 'HTTP 401 - unauthorized' in caplog.text
        assert '1.92' in caplog.text


def test_resolve_latest_unverified_terse_does_not_also_warn(
        tmp_path, monkeypatch, caplog,
):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'boost' )
    gl.upsert_setting( conf, key, repr( '1.92' ) )
    deps = tmp_path / 'dependencies'
    _plant_extract( deps, 'boost', '1.92' )
    seen = {}

    def row( env, token, remark, status="ok", fields=() ):
        seen["remark"] = remark
        seen["status"] = status
        seen["fields"] = fields
        return True

    monkeypatch.setattr( gl, '_terse_version_row', row )
    # CI has no registry token. Listing still logs that before the opener runs.
    # The contract is that the terse row is not followed by the logger warning.
    monkeypatch.delenv( 'GITLAB_REGISTRY_TOKEN', raising=False )
    monkeypatch.delenv( 'CI_JOB_TOKEN', raising=False )
    env = FakeEnv( offline=False, dependencies_root=str( deps ) )
    with caplog.at_level( 'WARNING', logger='cuppa' ):
        assert gl.resolve_latest_package_version(
                env, registry=registry, package='boost',
                opener=_http_opener( 401, 'Unauthorized' ),
        ) == '1.92'
        assert 'was not verified' not in caplog.text
        assert 'using the remembered version' not in caplog.text
    assert seen["status"] == "warn"
    assert seen["remark"] == ""
    assert seen["fields"] == (
            gl._unverified_label(),
            gl.as_warning( "using remembered 1.92" ),
    )


def test_unverified_label_uses_warn_background_and_normal_foreground():
    import colorama

    was = gl.colouriser.use_colour
    gl.colouriser.enable()
    try:
        label = gl._unverified_label()
    finally:
        gl.colouriser.use_colour = was
    assert label.startswith( colorama.Back.MAGENTA )
    assert label.endswith( colorama.Style.RESET_ALL )
    assert "unverified" in label
    assert colorama.Style.BRIGHT not in label
    assert colorama.Fore.WHITE not in label


def test_resolve_latest_server_error_uses_remembered_extract( tmp_path, monkeypatch ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'boost' )
    gl.upsert_setting( conf, key, repr( '1.92' ) )
    deps = tmp_path / 'dependencies'
    _plant_extract( deps, 'boost', '1.92' )
    env = FakeEnv( offline=False, dependencies_root=str( deps ) )
    assert gl.resolve_latest_package_version(
            env, registry=registry, package='boost', opener=_http_opener( 503 ),
    ) == '1.92'


def test_resolve_latest_not_found_does_not_reuse_extract( tmp_path, monkeypatch ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'boost' )
    gl.upsert_setting( conf, key, repr( '1.92' ) )
    deps = tmp_path / 'dependencies'
    _plant_extract( deps, 'boost', '1.92' )
    env = FakeEnv( offline=False, dependencies_root=str( deps ) )
    with pytest.raises( gl.GitlabLatestError ) as caught:
        gl.resolve_latest_package_version(
                env, registry=registry, package='boost', opener=_http_opener( 404 ),
        )
    assert caught.value.status == 404


def test_resolve_latest_auth_failure_without_extract_fails( tmp_path, monkeypatch ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'boost' )
    gl.upsert_setting( conf, key, repr( '1.92' ) )
    env = FakeEnv( offline=False, dependencies_root=str( tmp_path / 'dependencies' ) )
    with pytest.raises( gl.GitlabLatestError ) as caught:
        gl.resolve_latest_package_version(
                env, registry=registry, package='boost', opener=_http_opener( 401 ),
        )
    assert caught.value.status == 401


def test_resolve_latest_auth_failure_does_not_recover_for_publish( tmp_path, monkeypatch ):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'boost' )
    gl.upsert_setting( conf, key, repr( '1.92' ) )
    deps = tmp_path / 'dependencies'
    _plant_extract( deps, 'boost', '1.92' )
    env = FakeEnv( offline=False, dependencies_root=str( deps ) )
    with pytest.raises( gl.GitlabLatestError ):
        gl.resolve_latest_package_version(
                env,
                registry=registry,
                package='boost',
                opener=_http_opener( 401 ),
                allow_remembered_on_network_error=False,
        )


def test_resolve_latest_network_failure_without_memory_fails():
    def opener( url, headers ):
        raise gl.URLError( 'Temporary failure in name resolution' )

    env = FakeEnv( offline=False )
    with pytest.raises( gl.GitlabLatestNetworkError ):
        gl.resolve_latest_package_version(
                env,
                registry='https://gitlab.example/api/v4/projects/1',
                package='widget',
                opener=opener,
        )


def test_resolve_latest_network_failure_does_not_recover_for_publish(
        tmp_path, monkeypatch
):
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'widget' )
    gl.upsert_setting( conf, key, repr( '1.10' ) )

    def opener( url, headers ):
        raise gl.URLError( 'Temporary failure in name resolution' )

    env = FakeEnv( offline=False )
    with pytest.raises( gl.GitlabLatestNetworkError ):
        gl.resolve_latest_package_version(
                env,
                registry=registry,
                package='widget',
                opener=opener,
                allow_remembered_on_network_error=False,
        )


def test_offline_resolve_keeps_remembered_pin_despite_older_on_disk(
        tmp_path, monkeypatch
):
    """Offline latest replays the remembered pin; it does not scan downloads for older."""
    conf = str( tmp_path / 'configure.conf' )
    monkeypatch.setattr( gl, 'registry_latest_conf_path', lambda env: conf )
    registry = 'https://gitlab.example/api/v4/projects/1'
    key = gl.registry_latest_conf_key( registry, 'widget' )
    gl.upsert_setting( conf, key, repr( '1.10' ) )

    older = tmp_path / 'downloads' / 'packages' / 'widget' / '1.9'
    older.mkdir( parents=True )
    ( older / 'widget_dummy.tar.gz' ).write_bytes( b'old' )

    env = FakeEnv( offline=True, downloads_root=str( tmp_path / 'downloads' ) )
    assert gl.resolve_latest_package_version(
            env, registry=registry, package='widget'
    ) == '1.10'


def test_offline_package_fails_when_pin_archive_missing_even_if_older_cached(
        tmp_path, monkeypatch
):
    """Remembered latest pin + missing archive fails; older cached version is unused."""
    from types import SimpleNamespace

    from cuppa.package_managers.gitlab import (
            GitlabPackageDependency,
            GitlabPackageDependencyException,
            package_file_name,
    )

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.freedesktop_os_release',
            lambda: { 'ID': 'debian' },
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.platform.system',
            lambda: 'Linux',
    )

    downloads = tmp_path / 'downloads'
    dependencies = tmp_path / 'dependencies'
    dependencies.mkdir()

    toolchain = SimpleNamespace( package_name=lambda: 'gcc15' )
    variant = SimpleNamespace( name=lambda: 'rel' )
    env = FakeEnv(
            offline=True,
            develop=False,
            clean=False,
            dump=False,
            storage_resolve_only=False,
            downloads_root=str( downloads ),
            dependencies_root=str( dependencies ),
            sconstruct_dir=str( tmp_path ),
            toolchain=toolchain,
            variant=variant,
            target_arch='x86_64',
            abi='cxx2c',
    )

    older_name = package_file_name( env, package='widget', variant='rel' )
    older_dir = downloads / 'packages' / 'widget' / '1.9'
    older_dir.mkdir( parents=True )
    ( older_dir / older_name ).write_bytes( b'old-archive' )

    with pytest.raises( GitlabPackageDependencyException ) as caught:
        GitlabPackageDependency(
                env,
                registry='https://gitlab.example/api/v4/projects/1',
                package='widget',
                version='1.10',
                variant='rel',
        )
    message = str( caught.value )
    assert 'OFFLINE' in message
    assert 'does not exist' in message
    assert '1.10' in message


def test_package_dependency_default_version_latest( monkeypatch ):
    Dep = package_dependency(
            'widget',
            package_manager='gitlab',
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='latest',
    )

    def fake_resolve( env, registry, package, custom_token=None, opener=None, **kwargs ):
        assert package == 'widget'
        return '4.5'

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab_latest.resolve_latest_package_version',
            fake_resolve,
    )
    env = FakeEnv( offline=False, develop=False )
    Dep.default_version( Dep._version, env )
    assert Dep._version == '4.5'


def test_package_dependency_default_version_none( monkeypatch ):
    Dep = package_dependency(
            'widget',
            package_manager='gitlab',
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version=None,
    )

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab_latest.resolve_latest_package_version',
            lambda *a, **k: '9.0',
    )
    Dep.default_version( Dep._version, FakeEnv() )
    assert Dep._version == '9.0'


def test_package_dependency_default_version_minimum( monkeypatch ):
    Dep = package_dependency(
            'widget',
            package_manager='gitlab',
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='>=1.28.0',
    )

    def fake_resolve( env, bound, **kwargs ):
        assert bound.display() == '>=1.28.0'
        assert kwargs.get( 'package' ) == 'widget'
        return '1.29.1'

    monkeypatch.setattr(
            'cuppa.package_managers.package_version_bound.resolve_bound_to_concrete',
            fake_resolve,
    )
    monkeypatch.setattr(
            'cuppa.package_managers.gitlab.refresh_downloads_applies',
            lambda *a, **k: False,
    )
    Dep.default_version( Dep._version, FakeEnv( offline=False ) )
    assert Dep._version == '1.29.1'


def test_package_dependency_default_version_failure_is_stop_error( monkeypatch ):
    Dep = package_dependency(
            'widget',
            package_manager='gitlab',
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='latest',
    )

    def boom( *a, **k ):
        raise gl.GitlabLatestError( 'empty registry' )

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab_latest.resolve_latest_package_version',
            boom,
    )
    with pytest.raises( SCons.Errors.StopError ):
        Dep.default_version( Dep._version, FakeEnv() )


def test_boost_package_uses_base_registry_latest( monkeypatch ):
    from cuppa.packages import boost_package

    Boost = boost_package.define(
            registry='https://gitlab.example/api/v4/projects/1',
            version='latest',
    )

    monkeypatch.setattr(
            'cuppa.package_managers.gitlab_latest.resolve_latest_package_version',
            lambda *a, **k: '1.91',
    )
    Boost.default_version( Boost._version, FakeEnv( offline=False ) )
    assert Boost._version == '1.91'


def test_boost_package_latest_release_callable( monkeypatch ):
    from cuppa.packages import boost_package

    monkeypatch.setattr(
            boost_package,
            'determine_latest_boost_version',
            lambda offline: '1.87.0',
    )
    assert boost_package.latest_release() == '1.87'
