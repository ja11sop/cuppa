"""Unit tests for hierarchical dependency tree summaries."""

import pytest

from cuppa.core import dependency_tree


pytestmark = pytest.mark.unit


def _leaf( dependency, state, size_bytes=100, storage_type='repository', qualifier='@master' ):
    return {
        'type': storage_type,
        'short_name': dependency,
        'stem': dependency,
        'dependency': dependency,
        'qualifier': qualifier,
        'tool_variant': None,
        'state': state,
        'size_bytes': size_bytes if state != 'missing' else None,
        'last_used_epoch': 1.0 if state != 'missing' else None,
        'path': '/tmp/{}'.format( dependency ),
        'source_url': None,
        'remote_location': 'https://example.com/{}'.format( dependency ),
        'location': '',
    }


def _referenced_summaries( tree ):
    sections = tree.get( 'sections' ) or []
    referenced = next( ( s for s in sections if s.get( 'label' ) == 'referenced' ), None )
    assert referenced is not None
    return [
            child for child in referenced.get( 'children' ) or []
            if child.get( 'kind' ) == 'summary'
    ]


def test_referenced_summary_splits_missing_from_stale():
    leaves = [
            _leaf( 'widget', 'referenced' ),
            _leaf( 'absent', 'missing' ),
            _leaf( 'also_absent', 'missing', storage_type='gitlab', qualifier='1.0' ),
    ]
    # Second missing needs a tool_variant leaf shape for gitlab — keep repository for simplicity.
    leaves[2]['type'] = 'repository'
    leaves[2]['qualifier'] = '@master'

    tree = dependency_tree.build_tree( leaves )
    summaries = { row['label']: row for row in _referenced_summaries( tree ) }

    assert 'dependencies in use' in summaries
    assert summaries['dependencies in use']['remark'] == '1 used'
    assert 'missing dependencies' in summaries
    assert summaries['missing dependencies']['remark'] == '2 missing'
    assert summaries['missing dependencies'].get( 'state' ) == 'missing'
    assert 'potentially stale dependencies' not in summaries


def test_referenced_summary_keeps_stale_for_non_missing_unused():
    leaves = [
            _leaf( 'widget', 'referenced' ),
            _leaf( 'cached_stem', 'cached' ),
    ]
    tree = dependency_tree.build_tree( leaves )
    summaries = { row['label']: row for row in _referenced_summaries( tree ) }

    assert summaries['dependencies in use']['remark'] == '1 used'
    assert 'missing dependencies' not in summaries
    assert 'potentially stale dependencies' in summaries
    assert summaries['potentially stale dependencies']['remark'] == '1 unused'


def _gitlab_leaf( name, version, tool_variant, path, state='unreferenced', requires=None ):
    leaf = {
        'type': 'gitlab',
        'short_name': name,
        'stem': name,
        'dependency': name,
        'qualifier': version,
        'tool_variant': tool_variant,
        'state': state,
        'size_bytes': 10,
        'last_used_epoch': 1.0,
        'path': path,
        'source_url': None,
        'remote_location': 'https://gitlab.example/api/v4/projects/1/{}/{}'.format(
                name, version
        ),
        'location': '',
        'package_archive': '{}_{}.tar.gz'.format( name, tool_variant ),
        'has_download': False,
    }
    if requires is not None:
        leaf['requires'] = requires
    return leaf


def _find_kind( node, kind ):
    if node.get( 'kind' ) == kind:
        return node
    for child in node.get( 'children' ) or []:
        found = _find_kind( child, kind )
        if found is not None:
            return found
    return None


def test_gitlab_tree_shows_requires_from_manifest( tmp_path ):
    package_dir = tmp_path / "gcc15_rel_x86_64_cxx2c" / "alpha" / "1.0.0"
    package_dir.mkdir( parents=True )
    ( package_dir / "include" ).mkdir()
    from cuppa.package_managers.cuppa_dependency_manifest import write_manifest
    write_manifest( str( package_dir ), [
            {
                    "name": "beta",
                    "package": "beta",
                    "version": "2.0.0",
                    "use_libs": ["beta_core"],
            },
    ] )

    tree = dependency_tree.build_tree( [
            _gitlab_leaf(
                    'alpha', '1.0.0', 'gcc15_rel_x86_64_cxx2c',
                    str( package_dir ), state='referenced',
            ),
    ] )
    referenced = next( s for s in tree['sections'] if s['label'] == 'referenced' )
    requires = _find_kind( referenced, 'requires' )
    assert requires is not None
    assert requires['label'] == 'requires'
    edge = requires['children'][0]
    assert edge['kind'] == 'requires_edge'
    assert edge['requires_name'] == 'beta'
    assert edge['requires_version'] == '2.0.0'
    assert edge['remark'] == 'libs: beta_core'


def test_gitlab_tree_shows_requires_from_preloaded_entries():
    tree = dependency_tree.build_tree( [
            _gitlab_leaf(
                    'alpha', '1.0.0', 'gcc15_rel', '/missing/path',
                    state='referenced',
                    requires=[
                            {
                                    'name': 'beta',
                                    'package': 'beta',
                                    'version': '2.0.0',
                            },
                    ],
            ),
    ] )
    referenced = next( s for s in tree['sections'] if s['label'] == 'referenced' )
    requires = _find_kind( referenced, 'requires' )
    assert requires is not None
    assert requires['children'][0]['label'] == 'beta 2.0.0'


def test_requires_group_from_package_dir_none_when_absent( tmp_path ):
    assert dependency_tree.requires_group_from_package_dir( str( tmp_path ) ) is None
