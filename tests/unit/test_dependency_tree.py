"""Unit tests for hierarchical dependency tree summaries."""

import pytest

from cuppa.core import dependency_tree


pytestmark = pytest.mark.unit


def _leaf( dependency, state, size_bytes=100, storage_type='location', qualifier='@master' ):
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
    # Second missing needs a tool_variant leaf shape for gitlab — keep location for simplicity.
    leaves[2]['type'] = 'location'
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
