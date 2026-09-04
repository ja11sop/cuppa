#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest
import re
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


def test_package_dependency_default_version_latest( monkeypatch ):
    Dep = package_dependency(
            'widget',
            package_manager='gitlab',
            registry='https://gitlab.example/api/v4/projects/1',
            package='widget',
            version='latest',
    )

    def fake_resolve( env, registry, package, custom_token=None, opener=None ):
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
