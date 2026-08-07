#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for --list-scope filtering (dependencies and downloads)."""

import pytest

from cuppa.core import dependency_actions, dependency_downloads, dependency_identity


pytestmark = pytest.mark.unit


def _row( dependency, state, size_bytes=100 ):
    return {
        'size': '{}'.format( size_bytes ),
        'size_bytes': size_bytes,
        'dependency': dependency,
        'qualifier': '@master',
        'tool_variant': None,
        'last_used': '-',
        'last_used_epoch': 1.0,
        'state': state,
        'path': '/tmp/{}'.format( dependency ),
        'type': 'repository',
        'kind': 'repository',
        'short_name': dependency,
        'stem': dependency,
        'source_url': None,
        'remote_location': 'https://example.com/{}'.format( dependency ),
        'location': '',
        'has_download': False,
        'download_path': None,
    }


def _data( rows ):
    return {
        'dependencies_root': '/tmp/deps',
        'downloads_root': '/tmp/downloads',
        'rows': rows,
        'tree': None,
        'total_bytes': sum( r['size_bytes'] for r in rows ),
        'unreferenced_bytes': sum(
                r['size_bytes'] for r in rows if r['state'] == 'unreferenced'
        ),
        'missing_count': sum( 1 for r in rows if r['state'] == 'missing' ),
        'estimated': False,
        'has_download_marks': False,
        'skips': [],
    }


def _download_row( label, state, size_bytes=100, role='archive' ):
    return {
        'role': role,
        'type': 'archive',
        'dependency': label,
        'short_name': label,
        'qualifier': None,
        'tool_variant': None,
        'state': state,
        'size_bytes': size_bytes,
        'label': label,
        'path': '/dl/{}'.format( label ),
        'location': '/dl/{}'.format( label ),
        'last_used_epoch': 1.0 if state == 'referenced' else None,
        'remote_location': None,
    }


def _download_data( rows ):
    return {
        'dependencies_root': '/tmp/deps',
        'downloads_root': '/tmp/downloads',
        'rows': rows,
        'tree': None,
        'archive_count': sum( 1 for row in rows if row['role'] == 'archive' ),
        'total_bytes': sum(
                row['size_bytes'] for row in rows if row['role'] == 'archive'
        ),
        'unreferenced_bytes': sum(
                row['size_bytes'] for row in rows
                if row['role'] == 'archive' and row['state'] == 'unreferenced'
        ),
        'skips': [],
    }


def test_scope_all_keeps_every_row():
    rows = [
            _row( 'widget', 'referenced', 50 ),
            _row( 'orphan', 'unreferenced', 20 ),
            _row( 'absent', 'missing', 0 ),
    ]
    filtered = dependency_actions.apply_list_scope( _data( rows ), 'all' )
    assert filtered['scope'] == 'all'
    assert len( filtered['rows'] ) == 3
    labels = { section['label'] for section in filtered['tree']['sections'] }
    assert labels == { 'referenced', 'unreferenced' }


def test_scope_referenced_drops_unreferenced_section():
    rows = [
            _row( 'widget', 'referenced', 50 ),
            _row( 'orphan', 'unreferenced', 20 ),
            _row( 'absent', 'missing', 0 ),
    ]
    filtered = dependency_actions.apply_list_scope( _data( rows ), 'referenced' )
    assert filtered['scope'] == 'referenced'
    assert { row['dependency'] for row in filtered['rows'] } == { 'widget', 'absent' }
    assert filtered['unreferenced_bytes'] == 0
    assert filtered['missing_count'] == 1
    labels = [
            section['label']
            for section in filtered['tree']['sections']
            if section.get( 'children' )
    ]
    assert labels == [ 'referenced' ]


def test_scope_referenced_keeps_unused_siblings_under_identity():
    """referenced = whole identities that resolve, including unused sibling leaves."""
    rows = [
            {
                **_row( 'boost', 'referenced', 100 ),
                'qualifier': '1.91.0',
                'type': 'archive',
                'kind': 'archive',
                'short_name': 'boost',
                'path': '/tmp/boost_1_91_0',
            },
            {
                **_row( 'boost', 'unreferenced', 80 ),
                'qualifier': '1.90.0',
                'type': 'archive',
                'kind': 'archive',
                'short_name': 'boost',
                'path': '/tmp/boost_1_90_0',
            },
            _row( 'orphan', 'unreferenced', 20 ),
    ]
    filtered = dependency_actions.apply_list_scope( _data( rows ), 'referenced' )
    assert filtered['scope'] == 'referenced'
    assert len( filtered['rows'] ) == 2
    assert { row['path'] for row in filtered['rows'] } == {
            '/tmp/boost_1_91_0', '/tmp/boost_1_90_0',
    }
    assert filtered['total_bytes'] == 180
    assert filtered['unreferenced_bytes'] == 0


def test_scope_referenced_keeps_gitlab_siblings_despite_registry_alias():
    """Registry name boost_package and folder boost share one gitlab identity."""
    rows = [
            {
                **_row( 'boost_package', 'referenced', 100 ),
                'qualifier': '1.91',
                'type': 'gitlab',
                'kind': 'gitlab',
                'short_name': 'boost_package',
                'tool_variant': 'gcc153_rel_x86_64_cxx2c',
                'path': '/deps/gcc153_rel_x86_64_cxx2c/boost/1.91',
                'remote_location': 'https://gitlab.example/api/v4/projects/1/boost/1.91',
            },
            {
                **_row( 'boost', 'unreferenced', 80 ),
                'qualifier': '1.90',
                'type': 'gitlab',
                'kind': 'gitlab',
                'short_name': 'boost',
                'tool_variant': 'gcc153_rel_x86_64_cxx2c',
                'path': '/deps/gcc153_rel_x86_64_cxx2c/boost/1.90',
            },
            _row( 'orphan', 'unreferenced', 20 ),
    ]
    filtered = dependency_actions.apply_list_scope( _data( rows ), 'referenced' )
    assert filtered['scope'] == 'referenced'
    assert { row['qualifier'] for row in filtered['rows'] } == { '1.91', '1.90' }
    compact = dependency_actions.apply_list_scope( _data( rows ), 'compact' )
    assert { row['qualifier'] for row in compact['rows'] } == { '1.91' }
    tree = filtered['tree']
    ref = next( section for section in tree['sections'] if section['label'] == 'referenced' )
    labels = []
    for type_node in ref.get( 'children' ) or []:
        for child in type_node.get( 'children' ) or []:
            if child.get( 'kind' ) == 'identity':
                labels.append( child.get( 'label' ) )
    assert any( 'boost_package' in ( label or '' ) for label in labels )


def test_scope_compact_keeps_only_selected_leaves():
    rows = [
            {
                **_row( 'boost', 'referenced', 100 ),
                'qualifier': '1.91.0',
                'type': 'archive',
                'kind': 'archive',
                'short_name': 'boost',
                'path': '/tmp/boost_1_91_0',
            },
            {
                **_row( 'boost', 'unreferenced', 80 ),
                'qualifier': '1.90.0',
                'type': 'archive',
                'kind': 'archive',
                'short_name': 'boost',
                'path': '/tmp/boost_1_90_0',
            },
            _row( 'orphan', 'unreferenced', 20 ),
    ]
    filtered = dependency_actions.apply_list_scope( _data( rows ), 'compact' )
    assert filtered['scope'] == 'compact'
    assert len( filtered['rows'] ) == 1
    assert filtered['rows'][0]['path'] == '/tmp/boost_1_91_0'
    assert filtered['total_bytes'] == 100
    assert filtered['unreferenced_bytes'] == 0
    # compact ⊆ referenced: tree stays on the referenced section label.
    labels = [
            section['label']
            for section in filtered['tree']['sections']
            if section.get( 'children' )
    ]
    assert labels == [ 'referenced' ]
    assert all( row['state'] != 'unreferenced' for row in filtered['rows'] )


def test_downloads_scope_compact_drops_unused_sibling_archives():
    rows = [
            {
                **_download_row( 'boost_1_91.tar.gz', 'referenced', 100 ),
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.91.0',
            },
            {
                **_download_row( 'boost_1_90.tar.gz', 'unreferenced', 80 ),
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.90.0',
            },
            _download_row( 'orphan.tar.gz', 'unreferenced', 50 ),
    ]
    filtered = dependency_actions.apply_list_scope(
            _download_data( rows ), 'compact',
            tree_builder=dependency_downloads.build_downloads_tree,
    )
    assert filtered['scope'] == 'compact'
    assert [ row['label'] for row in filtered['rows'] ] == [ 'boost_1_91.tar.gz' ]
    assert filtered['archive_count'] == 1
    assert filtered['total_bytes'] == 100
    assert filtered['unreferenced_bytes'] == 0


def test_downloads_scope_referenced_keeps_unused_sibling_archives():
    rows = [
            {
                **_download_row( 'boost_1_91.tar.gz', 'referenced', 100 ),
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.91.0',
            },
            {
                **_download_row( 'boost_1_90.tar.gz', 'unreferenced', 80 ),
                'short_name': 'boost',
                'dependency': 'boost',
                'qualifier': '1.90.0',
            },
            _download_row( 'orphan.tar.gz', 'unreferenced', 50 ),
    ]
    filtered = dependency_actions.apply_list_scope(
            _download_data( rows ), 'referenced',
            tree_builder=dependency_downloads.build_downloads_tree,
    )
    assert { row['label'] for row in filtered['rows'] } == {
            'boost_1_91.tar.gz', 'boost_1_90.tar.gz',
    }
    assert filtered['archive_count'] == 2
    assert filtered['total_bytes'] == 180
    assert filtered['unreferenced_bytes'] == 0


def test_scope_unreferenced_keeps_only_orphans():
    rows = [
            _row( 'widget', 'referenced', 50 ),
            _row( 'orphan', 'unreferenced', 20 ),
    ]
    filtered = dependency_actions.apply_list_scope( _data( rows ), 'unreferenced' )
    assert filtered['scope'] == 'unreferenced'
    assert [ row['dependency'] for row in filtered['rows'] ] == [ 'orphan' ]
    assert filtered['total_bytes'] == 20
    assert filtered['unreferenced_bytes'] == 20
    labels = [
            section['label']
            for section in filtered['tree']['sections']
            if section.get( 'children' )
    ]
    assert labels == [ 'unreferenced' ]


def test_scope_unknown_falls_back_to_all():
    rows = [ _row( 'widget', 'referenced' ), _row( 'orphan', 'unreferenced' ) ]
    filtered = dependency_actions.apply_list_scope( _data( rows ), 'nope' )
    assert filtered['scope'] == 'all'
    assert len( filtered['rows'] ) == 2


def test_legacy_apply_list_dependencies_scope_still_works():
    rows = [ _row( 'widget', 'referenced' ), _row( 'orphan', 'unreferenced' ) ]
    filtered = dependency_actions.apply_list_dependencies_scope(
            _data( rows ), 'referenced'
    )
    assert filtered['scope'] == 'referenced'
    assert [ row['dependency'] for row in filtered['rows'] ] == [ 'widget' ]


def test_downloads_scope_referenced_keeps_archive_totals():
    rows = [
            _download_row( 'boost.tar.gz', 'referenced', 100 ),
            _download_row( '[E] boost', 'referenced', 2000, role='product' ),
            _download_row( 'orphan.tar.gz', 'unreferenced', 50 ),
    ]
    filtered = dependency_actions.apply_list_scope(
            _download_data( rows ), 'referenced',
            tree_builder=dependency_downloads.build_downloads_tree,
    )
    assert filtered['scope'] == 'referenced'
    assert filtered['archive_count'] == 1
    assert filtered['total_bytes'] == 100
    assert filtered['unreferenced_bytes'] == 0
    labels = [
            section['label']
            for section in filtered['tree']['sections']
            if section.get( 'children' )
    ]
    assert labels == [ 'referenced' ]


def test_downloads_scope_unreferenced_drops_referenced_archives():
    rows = [
            _download_row( 'boost.tar.gz', 'referenced', 100 ),
            _download_row( 'orphan.tar.gz', 'unreferenced', 50 ),
    ]
    filtered = dependency_actions.apply_list_scope(
            _download_data( rows ), 'unreferenced',
            tree_builder=dependency_downloads.build_downloads_tree,
    )
    assert [ row['label'] for row in filtered['rows'] ] == [ 'orphan.tar.gz' ]
    assert filtered['archive_count'] == 1
    assert filtered['total_bytes'] == 50
    assert filtered['unreferenced_bytes'] == 50
    labels = [
            section['label']
            for section in filtered['tree']['sections']
            if section.get( 'children' )
    ]
    assert labels == [ 'unreferenced' ]


def test_normalise_list_scope_prefers_known_values():
    assert dependency_actions.normalise_list_scope( None ) == 'all'
    assert dependency_actions.normalise_list_scope( [ 'referenced' ] ) == 'referenced'
    assert dependency_actions.normalise_list_scope( 'UNREFERENCED' ) == 'unreferenced'
    assert dependency_actions.normalise_list_scope( 'compact' ) == 'compact'


def test_mark_unqualified_duplicate_rows_only_unused_siblings():
    rows = [
            {
                **_row( 'widget', 'referenced', 100 ),
                'qualifier': '@master',
                'path': '/tmp/git_https_example.com__org_widget.git@master',
                'type': 'repository',
                'kind': 'repository',
                'short_name': 'github.com/org/widget',
            },
            {
                **_row( 'widget', 'unreferenced', 80 ),
                'qualifier': '@master (unqualified)',
                'path': '/tmp/git_https_example.com__org_widget.git',
                'type': 'repository',
                'kind': 'repository',
                'short_name': 'github.com/org/widget',
            },
            {
                **_row( 'solo', 'referenced', 50 ),
                'qualifier': '@master (unqualified)',
                'path': '/tmp/git_https_example.com__org_solo.git',
                'type': 'repository',
                'kind': 'repository',
                'short_name': 'github.com/org/solo',
            },
    ]
    tokens = dependency_actions.mark_unqualified_duplicate_rows( rows )
    assert tokens == [ 'widget/@' ]
    assert rows[1].get( 'removal_candidate' ) == 'unqualified_duplicate'
    assert 'removal_candidate' not in rows[0]
    assert 'removal_candidate' not in rows[2]


def test_mark_unqualified_duplicate_rows_groups_by_folder_stem():
    """Resolve may label the selected leaf ``widget`` while the stem stays encoded."""
    rows = [
            {
                **_row( 'widget', 'referenced', 100 ),
                'qualifier': '@master',
                'path': r'C:\deps\git_https_example.com__org_widget.git@master',
                'type': 'repository',
                'kind': 'repository',
                'short_name': 'widget',
                'dependency': 'widget',
            },
            {
                **_row( 'git_https_example.com__org_widget.git', 'unreferenced', 80 ),
                'qualifier': '@master (unqualified)',
                'path': r'C:\deps\git_https_example.com__org_widget.git',
                'type': 'repository',
                'kind': 'repository',
                'short_name': 'git_https_example.com__org_widget.git',
                'dependency': 'git_https_example.com__org_widget.git',
            },
    ]
    assert dependency_identity.list_identity_key( rows[0] ) != \
            dependency_identity.list_identity_key( rows[1] )
    tokens = dependency_actions.mark_unqualified_duplicate_rows( rows )
    assert tokens == [ 'widget/@' ]
    assert rows[1].get( 'removal_candidate' ) == 'unqualified_duplicate'


def test_apply_list_scope_preserves_unqualified_duplicate_tokens():
    rows = [
            {
                **_row( 'widget', 'referenced', 100 ),
                'qualifier': '@master',
            },
            {
                **_row( 'widget', 'unreferenced', 80 ),
                'qualifier': '@master (unqualified)',
                'removal_candidate': 'unqualified_duplicate',
            },
    ]
    data = _data( rows )
    data['unqualified_duplicate_tokens'] = [ 'widget/@' ]
    compact = dependency_actions.apply_list_scope( data, 'compact' )
    assert compact['unqualified_duplicate_tokens'] == [ 'widget/@' ]
    assert len( compact['rows'] ) == 1
