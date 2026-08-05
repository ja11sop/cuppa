"""Unit tests for hierarchical --list-downloads collection and tree."""

import pytest

from cuppa.core import dependency_downloads
from cuppa.core.dependency_storage import OwnedPath


pytestmark = pytest.mark.unit


def test_walk_download_files_top_level_and_packages( tmp_path ):
    downloads = tmp_path / 'downloads'
    ( downloads / 'packages' / 'boost' / '1.91' ).mkdir( parents=True )
    top = downloads / 'boost.tar.gz'
    top.write_bytes( b'abc' )
    pkg = downloads / 'packages' / 'boost' / '1.91' / 'boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz'
    pkg.write_bytes( b'defg' )
    ( downloads / '.hidden' ).write_bytes( b'x' )
    ( downloads / 'packages' / 'boost' / '1.91' / 'notes.txt' ).write_text( 'n\n', encoding='utf-8' )

    walked = list( dependency_downloads.walk_download_files( str( downloads ) ) )
    assert str( top ) in walked
    assert str( pkg ) in walked
    assert not any( path.endswith( '.hidden' ) for path in walked )


def test_describe_download_file_gitlab_and_archive( tmp_path ):
    downloads = tmp_path / 'downloads'
    archive = downloads / 'packages' / 'boost' / '1.91' / 'boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz'
    archive.parent.mkdir( parents=True )
    archive.write_bytes( b'x' )
    meta = dependency_downloads.describe_download_file( str( archive ), str( downloads ) )
    assert meta['type'] == 'gitlab'
    assert meta['package_folder'] == 'boost'
    assert meta['qualifier'] == '1.91'
    assert meta['tool_variant'] == 'gcc153_rel_x86_64_cxx2c'
    assert meta['archive'] == archive.name

    boost = downloads / 'https_archives.boost.io__release_1.91.0_source_boost_1_91_0.tar.gz'
    boost.write_bytes( b'y' )
    archive_meta = dependency_downloads.describe_download_file( str( boost ), str( downloads ) )
    assert archive_meta['type'] == 'archive'
    assert archive_meta['short_name'] == 'boost'
    assert archive_meta['qualifier'] in ( '1.91.0', None ) or '1.91' in str( archive_meta['qualifier'] )


def test_build_downloads_tree_splits_referenced_and_orphan():
    rows = [
        {
            'role': 'archive',
            'type': 'archive',
            'dependency': 'boost',
            'short_name': 'boost',
            'qualifier': '1.91.0',
            'tool_variant': None,
            'state': 'referenced',
            'size_bytes': 100,
            'label': 'boost_1_91_0.tar.gz',
            'path': '/dl/boost_1_91_0.tar.gz',
            'location': '/dl/boost_1_91_0.tar.gz',
            'last_used_epoch': 1.0,
            'remote_location': None,
        },
        {
            'role': 'product',
            'type': 'archive',
            'dependency': 'boost',
            'short_name': 'boost',
            'qualifier': '1.91.0',
            'tool_variant': None,
            'state': 'referenced',
            'size_bytes': 2000,
            'label': '[E] boost/1.91.0',
            'path': '/deps/boost_1_91_0.tar.gz',
            'location': '/deps/boost_1_91_0.tar.gz',
            'last_used_epoch': 1.0,
            'remote_location': None,
        },
        {
            'role': 'archive',
            'type': 'archive',
            'dependency': 'orphan.tar.gz',
            'short_name': 'orphan.tar.gz',
            'qualifier': None,
            'tool_variant': None,
            'state': 'unreferenced',
            'size_bytes': 50,
            'label': 'orphan.tar.gz',
            'path': '/dl/orphan.tar.gz',
            'location': '/dl/orphan.tar.gz',
            'last_used_epoch': None,
            'remote_location': None,
        },
    ]
    tree = dependency_downloads.build_downloads_tree( rows )
    sections = { section['label']: section for section in tree['sections'] }
    assert sections['referenced']['size_bytes'] == 100
    assert sections['unreferenced']['size_bytes'] == 50
    assert sections['referenced']['display_label'] == 'referenced from downloads'
    assert sections['unreferenced']['display_label'] == 'unreferenced downloads'

    def leaves( node, found=None ):
        found = found if found is not None else []
        if node.get( 'kind' ) == 'leaf':
            found.append( node )
        for child in node.get( 'children' ) or []:
            leaves( child, found )
        return found

    ref_leaves = leaves( sections['referenced'] )
    assert [ leaf['label'] for leaf in ref_leaves ] == [
            'boost_1_91_0.tar.gz', '[E] boost/1.91.0',
    ]
    assert ref_leaves[0]['role'] == 'archive'
    assert [ child.get( 'label' ) for child in ref_leaves[0].get( 'children' ) or [] ] == [
            '[E] boost/1.91.0',
    ]

    type_labels = [
            child.get( 'label' )
            for child in sections['referenced'].get( 'children' ) or []
            if child.get( 'kind' ) == 'type'
    ]
    assert 'source archives' in type_labels

    unref_leaves = leaves( sections['unreferenced'] )
    assert [ leaf['label'] for leaf in unref_leaves ] == [ 'orphan.tar.gz' ]
    assert unref_leaves[0].get( 'children' ) == []


def test_collect_pairs_owned_archive_with_extract_and_orphan( tmp_path, monkeypatch ):
    deps = tmp_path / 'dependencies'
    downloads = tmp_path / 'downloads'
    deps.mkdir()
    downloads.mkdir()
    archive_name = 'https_archives.boost.io__release_1.91.0_source_boost_1_91_0.tar.gz'
    extract = deps / archive_name
    extract.mkdir()
    ( extract / 'boost' ).mkdir()
    ( extract / 'boost' / 'version.hpp' ).write_text( '//\n', encoding='utf-8' )
    archive = downloads / archive_name
    archive.write_bytes( b'archive-bytes' )
    orphan = downloads / 'leftover.tar.gz'
    orphan.write_bytes( b'zz' )

    owned = [
        OwnedPath(
            dependency='boost',
            storage_type='archive',
            category='downloads',
            path=str( archive ),
            qualifier='1.91.0',
            tool_variant=None,
            develop=False,
            remote_location='https://archives.boost.io/release/1.91.0/source/boost_1_91_0.tar.gz',
        ),
        OwnedPath(
            dependency='boost',
            storage_type='archive',
            category='dependencies',
            path=str( extract ),
            qualifier='1.91.0',
            tool_variant=None,
            develop=False,
            remote_location='https://archives.boost.io/release/1.91.0/source/boost_1_91_0.tar.gz',
        ),
    ]
    monkeypatch.setattr(
            'cuppa.core.dependency_storage.default_dependency_names',
            lambda env: [ 'boost' ],
    )
    monkeypatch.setattr(
            'cuppa.core.dependency_storage.selection_build_envs',
            lambda construct, env: [],
    )
    monkeypatch.setattr(
            'cuppa.core.dependency_storage.resolve_named_dependencies',
            lambda *args, **kwargs: ( owned, [] ),
    )

    cuppa_env = {
        'dependencies_root': str( deps ),
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( tmp_path ),
        'default_dependencies': [ 'boost' ],
    }
    data = dependency_downloads.collect_download_rows( None, cuppa_env )
    assert data['archive_count'] == 2
    kinds = { ( row['role'], row['state'], row['label'] ) for row in data['rows'] }
    assert ( 'archive', 'referenced', archive_name ) in kinds
    assert any(
            row['role'] == 'product' and row['state'] == 'referenced'
            and row['label'].startswith( '[E]' )
            for row in data['rows']
    )
    assert ( 'archive', 'unreferenced', 'leftover.tar.gz' ) in kinds


def test_collect_gitlab_matches_package_folder_to_registry_name( tmp_path, monkeypatch ):
    deps = tmp_path / 'dependencies'
    downloads = tmp_path / 'downloads'
    tool = 'gcc153_rel_x86_64_cxx2c'
    product = deps / tool / 'boost' / '1.91'
    product.mkdir( parents=True )
    ( product / 'include' ).mkdir()
    archive_name = 'boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz'
    archive = downloads / 'packages' / 'boost' / '1.91' / archive_name
    archive.parent.mkdir( parents=True )
    archive.write_bytes( b'pkg' )
    leftover = downloads / 'packages' / 'boost' / '1.91' / 'boost_debian_clang211_rel_x86_64_cxx2c.tar.gz'
    leftover.write_bytes( b'other' )

    owned = [
        OwnedPath(
            dependency='boost_package',
            storage_type='gitlab',
            category='downloads',
            path=str( archive ),
            qualifier='1.91',
            tool_variant=tool,
            develop=False,
            remote_location='https://gitlab.example/api/v4/projects/1/boost/1.91',
        ),
        OwnedPath(
            dependency='boost_package',
            storage_type='gitlab',
            category='dependencies',
            path=str( product ),
            qualifier='1.91',
            tool_variant=tool,
            develop=False,
            remote_location='https://gitlab.example/api/v4/projects/1/boost/1.91',
        ),
    ]
    monkeypatch.setattr(
            'cuppa.core.dependency_storage.default_dependency_names',
            lambda env: [ 'boost_package' ],
    )
    monkeypatch.setattr(
            'cuppa.core.dependency_storage.selection_build_envs',
            lambda construct, env: [],
    )
    monkeypatch.setattr(
            'cuppa.core.dependency_storage.resolve_named_dependencies',
            lambda *args, **kwargs: ( owned, [] ),
    )

    data = dependency_downloads.collect_download_rows( None, {
        'dependencies_root': str( deps ),
        'downloads_root': str( downloads ),
        'sconstruct_dir': str( tmp_path ),
        'default_dependencies': [ 'boost_package' ],
    } )
    ref_archives = [
            row for row in data['rows']
            if row['role'] == 'archive' and row['state'] == 'referenced'
    ]
    unref_archives = [
            row for row in data['rows']
            if row['role'] == 'archive' and row['state'] == 'unreferenced'
    ]
    assert len( ref_archives ) == 1
    assert ref_archives[0]['dependency'] == 'boost_package'
    assert ref_archives[0]['label'] == archive_name
    products = [
            row for row in data['rows']
            if row['role'] == 'product' and row['state'] == 'referenced'
    ]
    assert len( products ) == 1
    assert products[0]['label'] == '[E] {}'.format( tool )
    assert len( unref_archives ) == 1
    assert unref_archives[0]['label'] == leftover.name
    assert unref_archives[0]['short_name'] == 'boost_package'

    tree = data['tree']
    ref = next( section for section in tree['sections'] if section['label'] == 'referenced' )

    def find_archive_leaf( node, name ):
        if node.get( 'kind' ) == 'leaf' and node.get( 'label' ) == name:
            return node
        for child in node.get( 'children' ) or []:
            found = find_archive_leaf( child, name )
            if found is not None:
                return found
        return None

    archive_leaf = find_archive_leaf( ref, archive_name )
    assert archive_leaf is not None
    child_labels = [ child.get( 'label' ) for child in archive_leaf.get( 'children' ) or [] ]
    assert child_labels == [ '[E] {}'.format( tool ) ]
