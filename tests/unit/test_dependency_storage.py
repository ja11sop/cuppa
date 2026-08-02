"""Unit tests for dependency storage_paths and resolve-only helpers."""

import os

import pytest

from cuppa.core import dependency_storage
from cuppa.utility import storage as storage_util


pytestmark = pytest.mark.unit


def test_normalise_storage_paths_fills_missing_keys():
    normalised = dependency_storage.normalise_storage_paths( {
        'dependencies': '/tmp/dep',
        'downloads': [ '/tmp/dl' ],
    } )
    assert normalised['dependencies'] == [ '/tmp/dep' ]
    assert normalised['downloads'] == [ '/tmp/dl' ]
    assert normalised['build'] == []
    assert normalised['develop'] == []


def test_normalise_storage_paths_handles_none():
    assert dependency_storage.normalise_storage_paths( None ) == dependency_storage.empty_storage_paths()


def test_location_storage_paths_under_dependencies_root( tmp_path ):
    from cuppa.location import Location

    dependencies_root = tmp_path / 'dependencies'
    downloads_root = tmp_path / 'downloads'
    dependencies_root.mkdir()
    downloads_root.mkdir()
    tree = dependencies_root / 'widget@master'
    tree.mkdir()

    env = {
        'dependencies_root': str( dependencies_root ),
        'downloads_root': str( downloads_root ),
        'abs_build_root': str( tmp_path / '_build' ),
        'offline': True,
        'clean': False,
        'dump': False,
        'storage_resolve_only': True,
        'sconstruct_dir': str( tmp_path ),
    }

    location = Location.__new__( Location )
    location._cuppa_env = env
    location._offline = True
    location._base_local_directory = str( tree )
    location._local_folder = 'widget@master'
    location._local_directory = str( tree )

    paths = location.storage_paths()
    assert paths['dependencies'] == [ str( tree ) ]
    assert paths['develop'] == []
    assert storage_util.is_contained( paths['dependencies'][0], str( dependencies_root ) )


def test_location_storage_paths_marks_develop_outside_root( tmp_path ):
    from cuppa.location import Location

    dependencies_root = tmp_path / 'dependencies'
    dependencies_root.mkdir()
    develop = tmp_path / 'src' / 'widget'
    develop.mkdir( parents=True )

    env = {
        'dependencies_root': str( dependencies_root ),
        'downloads_root': str( tmp_path / 'downloads' ),
        'abs_build_root': str( tmp_path / '_build' ),
        'offline': True,
        'clean': False,
        'dump': False,
        'storage_resolve_only': True,
        'sconstruct_dir': str( tmp_path ),
    }

    location = Location.__new__( Location )
    location._cuppa_env = env
    location._offline = True
    location._base_local_directory = str( develop )
    location._local_folder = 'widget'
    location._local_directory = str( develop )

    paths = location.storage_paths()
    assert paths['dependencies'] == []
    assert paths['develop'] == [ str( develop ) ]


def test_retrieval_disabled_reason_includes_storage_resolve_only():
    from cuppa.location import Location

    location = Location.__new__( Location )
    location._offline = False
    location._cuppa_env = { 'clean': False, 'storage_resolve_only': True }
    assert location.retrieval_disabled_reason() == 'storage action'


def test_gitlab_storage_paths_package_and_download( tmp_path ):
    from cuppa.package_managers.gitlab import GitlabPackageDependency

    dependencies_root = tmp_path / 'dependencies'
    downloads_root = tmp_path / 'downloads'
    package_dir = dependencies_root / 'gcc_dbg_x86_64_cxx2c' / 'gadget' / '1.0.0'
    download = downloads_root / 'packages' / 'gadget' / '1.0.0' / 'gadget_pkg.tar.gz'
    package_dir.mkdir( parents=True )
    download.parent.mkdir( parents=True )
    download.write_bytes( b'x' )

    package = GitlabPackageDependency.__new__( GitlabPackageDependency )
    package._using_develop = False
    package._package_dir = str( package_dir )
    package._download_target = str( download )
    package._tool_variant = 'gcc_dbg_x86_64_cxx2c'
    package._version = '1.0.0'

    paths = package.storage_paths()
    assert paths['dependencies'] == [ str( package_dir ) ]
    assert paths['downloads'] == [ str( download ) ]
    assert package.storage_tool_variant() == 'gcc_dbg_x86_64_cxx2c'
    assert package.storage_qualifier() == '1.0.0'


def test_gitlab_storage_paths_develop_is_not_removable( tmp_path ):
    from cuppa.package_managers.gitlab import GitlabPackageDependency

    develop = tmp_path / 'develop' / 'gadget'
    develop.mkdir( parents=True )

    package = GitlabPackageDependency.__new__( GitlabPackageDependency )
    package._using_develop = True
    package._package_dir = str( develop )
    package._download_target = str( tmp_path / 'ignored.tar.gz' )

    paths = package.storage_paths()
    assert paths['dependencies'] == []
    assert paths['develop'] == [ str( develop ) ]
    assert paths['downloads'] == []


def test_default_dependency_names():
    assert dependency_storage.default_dependency_names( {
        'default_dependencies': [ 'widget', 'gadget' ],
    } ) == [ 'widget', 'gadget' ]
    assert dependency_storage.default_dependency_names( {} ) == []
