#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for --list-scope filtering (dependencies and downloads)."""

import pytest

from cuppa.core import dependency_actions, dependency_downloads


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
