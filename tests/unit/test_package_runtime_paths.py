#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.package_managers.gitlab import GitlabPackageDependency
from cuppa.package_managers.runtime_paths import apply_package_runtime_paths


pytestmark = pytest.mark.unit


class RecordingEnv(dict):
    def __init__( self, **kwargs ):
        super().__init__( **kwargs )
        self.env_paths = {}
        self.appended = {}
        self.setdefault( 'ENV', {} )

    def PrependENVPath( self, key, path ):
        self.env_paths.setdefault( key, [] ).insert( 0, path )

    def AppendUnique( self, **kwargs ):
        for key, value in kwargs.items():
            self.appended.setdefault( key, [] ).append( value )


def test_apply_package_runtime_paths_linux( monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Linux' )
    env = RecordingEnv()
    apply_package_runtime_paths(
            env,
            lib_dirs=[ '/pkg/lib', '', None ],
            bin_dirs=[ '/pkg/bin' ],
    )
    assert env.env_paths['PATH'] == [ '/pkg/bin' ]
    assert env.env_paths['LD_LIBRARY_PATH'] == [ '/pkg/lib' ]
    assert 'DYLD_LIBRARY_PATH' not in env.env_paths


def test_apply_package_runtime_paths_darwin( monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Darwin' )
    env = RecordingEnv()
    apply_package_runtime_paths( env, lib_dirs=[ '/pkg/lib' ], bin_dirs=[ '/pkg/bin' ] )
    assert env.env_paths['PATH'] == [ '/pkg/bin' ]
    assert env.env_paths['DYLD_LIBRARY_PATH'] == [ '/pkg/lib' ]
    assert 'LD_LIBRARY_PATH' not in env.env_paths


def test_apply_package_runtime_paths_windows( monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Windows' )
    env = RecordingEnv()
    apply_package_runtime_paths( env, lib_dirs=[ '/pkg/lib' ], bin_dirs=[ '/pkg/bin' ] )
    assert env.env_paths['PATH'] == [ '/pkg/lib', '/pkg/bin' ]


def test_gitlab_initialise_build_variant_applies_runtime_paths( tmp_path, monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Linux' )
    pkg = tmp_path / 'widget' / '1.0.0'
    include = pkg / 'include'
    lib = pkg / 'lib'
    bin_dir = pkg / 'bin'
    include.mkdir( parents=True )
    lib.mkdir()
    bin_dir.mkdir()

    transitive = []
    monkeypatch.setattr(
            'cuppa.package_managers.cuppa_dependency_apply.apply_transitive_build_with',
            lambda *args, **kwargs: transitive.append( args ),
    )

    dep = object.__new__( GitlabPackageDependency )
    dep._package_id = 'widget/1.0.0'
    dep._package = 'widget'
    dep._package_dir = str( pkg )
    dep._include_dir = str( include )
    dep._lib_dir = str( lib )
    dep._registry = 'https://gitlab.example/api/v4/projects/1'

    class _Toolchain(object):
        def name( self ):
            return 'gcc15'

    env = RecordingEnv()
    dep.initialise_build_variant( env, _Toolchain(), 'rel' )

    assert env.appended['SYSINCPATH'] == [ str( include ) ]
    assert env.env_paths['LD_LIBRARY_PATH'] == [ str( lib ) ]
    assert env.env_paths['PATH'] == [ str( bin_dir ) ]
    assert transitive


def test_gitlab_initialise_skips_missing_bin( tmp_path, monkeypatch ):
    monkeypatch.setattr( 'cuppa.build_platform.name', lambda: 'Linux' )
    pkg = tmp_path / 'widget' / '1.0.0'
    include = pkg / 'include'
    lib = pkg / 'lib'
    include.mkdir( parents=True )
    lib.mkdir()

    monkeypatch.setattr(
            'cuppa.package_managers.cuppa_dependency_apply.apply_transitive_build_with',
            lambda *args, **kwargs: None,
    )

    dep = object.__new__( GitlabPackageDependency )
    dep._package_id = 'widget/1.0.0'
    dep._package = 'widget'
    dep._package_dir = str( pkg )
    dep._include_dir = str( include )
    dep._lib_dir = str( lib )
    dep._registry = None

    class _Toolchain(object):
        def name( self ):
            return 'gcc15'

    env = RecordingEnv()
    dep.initialise_build_variant( env, _Toolchain(), 'rel' )
    assert env.env_paths['LD_LIBRARY_PATH'] == [ str( lib ) ]
    assert 'PATH' not in env.env_paths
