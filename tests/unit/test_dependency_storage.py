"""Unit tests for dependency storage_paths and resolve-only helpers."""

import os

import pytest

from cuppa.core import dependency_storage
from cuppa.utility import storage as storage_util


pytestmark = pytest.mark.unit


class _FakeEnv( dict ):
    """Minimal stand-in for a SCons env with ``get_option``."""

    def get_option( self, option, default=None ):
        return self.get( option, default )


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


def test_looks_like_tool_variant_dir():
    assert dependency_storage.looks_like_tool_variant_dir( 'gcc153_rel_x86_64_cxx2c' )
    assert dependency_storage.looks_like_tool_variant_dir( 'clang211_dbg_x86_64_cxx2c' )
    assert not dependency_storage.looks_like_tool_variant_dir(
            'git_https_github.com__fmtlib_fmt.git'
    )
    assert not dependency_storage.looks_like_tool_variant_dir( 'conan' )


def test_describe_tree_path_package_layout( tmp_path ):
    root = tmp_path / 'dependencies'
    path = root / 'gcc153_rel_x86_64_cxx2c' / 'boost' / '1.91'
    path.mkdir( parents=True )
    described = dependency_storage.describe_tree_path( str( path ), str( root ) )
    assert described['dependency'] == 'boost'
    assert described['qualifier'] == '1.91'
    assert described['tool_variant'] == 'gcc153_rel_x86_64_cxx2c'
    assert described['kind'] == 'package'


def test_describe_tree_path_vcs_with_branch( tmp_path ):
    root = tmp_path / 'dependencies'
    path = root / 'git_ssh_git@host__org_widget@master'
    path.mkdir( parents=True )
    described = dependency_storage.describe_tree_path( str( path ), str( root ) )
    assert described['dependency'] == 'git_ssh_git@host__org_widget'
    assert described['qualifier'] == '@master'
    assert described['kind'] == 'location'


def test_describe_tree_path_keeps_git_at_in_name( tmp_path ):
    root = tmp_path / 'dependencies'
    path = root / 'git_ssh_git@git.example.com__org_widget'
    path.mkdir( parents=True )
    described = dependency_storage.describe_tree_path( str( path ), str( root ) )
    assert described['dependency'] == 'git_ssh_git@git.example.com__org_widget'
    assert described['qualifier'] is None


def test_describe_tree_path_https_branch_qualifier( tmp_path ):
    root = tmp_path / 'dependencies'
    path = root / 'git_https_github.com__fmtlib_fmt.git@11.1.1'
    path.mkdir( parents=True )
    described = dependency_storage.describe_tree_path( str( path ), str( root ) )
    assert described['dependency'] == 'git_https_github.com__fmtlib_fmt.git'
    assert described['qualifier'] == '@11.1.1'


def test_resolve_named_dependencies_passes_nested_scons_env( tmp_path ):
    """create_build_envs returns dicts; factories must receive selection['env']."""
    seen = []

    class Factory( object ):
        @staticmethod
        def create( env ):
            seen.append( env )
            assert hasattr( env, 'get_option' ), type( env )
            instance = type( 'Dep', (), {} )()
            instance.storage_paths = lambda: {
                'dependencies': [ str( tmp_path / 'dep' ) ],
                'downloads': [],
                'build': [],
                'develop': [],
            }
            instance.storage_qualifier = lambda: '1.0'
            instance.storage_tool_variant = lambda: 'gcc_dbg_x86_64_cxx2c'
            return instance

    ( tmp_path / 'dep' ).mkdir()
    fake_env = _FakeEnv( {
        'tool_variant_dir': 'gcc/dbg/x86_64/cxx2c',
        'dependencies_root': str( tmp_path ),
        'storage_resolve_only': True,
    } )
    cuppa_env = {
        'dependencies': { 'widget': Factory.create },
        'default_dependencies': [ 'widget' ],
        'active_toolchains': [ object() ],
        'storage_resolve_only': False,
    }
    selections = [ {
        'env': fake_env,
        'variant': 'dbg',
        'target_arch': 'x86_64',
        'abi': 'cxx2c',
        'toolchain': type( 'T', (), { 'name': lambda self: 'gcc' } )(),
    } ]

    owned, skips = dependency_storage.resolve_named_dependencies(
            construct=None,
            cuppa_env=cuppa_env,
            names=[ 'widget' ],
            selections=selections,
    )
    assert not skips
    assert seen and hasattr( seen[0], 'get_option' )
    assert len( owned ) == 1
    assert owned[0].dependency == 'widget'
