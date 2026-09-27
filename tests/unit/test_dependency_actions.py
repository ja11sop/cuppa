"""Unit tests for dependency listing helpers."""

from io import StringIO

import pytest

from cuppa.core import dependency_actions, dependency_storage, dependency_tree
from cuppa.core.dependency_removal import UnknownDependencyNames


pytestmark = pytest.mark.unit


def test_render_skip_tree_uses_glyph_tuple():
    skips = [
        dependency_storage.Skip( dependency='widget', reason='not on disk' ),
        dependency_storage.Skip( dependency='gadget', reason='layout not declared' ),
    ]
    lines = dependency_actions._render_skip_tree( skips )
    assert lines[0] == "Skipped dependencies:"
    assert len( lines ) == 3
    assert "[widget]" in lines[1]
    assert "not on disk" in lines[1]
    assert "[gadget]" in lines[2]
    assert "layout not declared" in lines[2]


def test_render_skip_tree_empty():
    assert dependency_actions._render_skip_tree( [] ) == []


def test_write_ruled_tree_rejects_header_only():
    out = StringIO()
    assert dependency_actions._write_ruled_tree( out, { 'sections': [] } ) is False
    assert out.getvalue() == ''


def test_unknown_remove_names_error_shows_used_section( monkeypatch ):
    """Default build_tree emits used/unused; the hint must keep the used section."""
    rows = [
            {
                'type': 'vcs',
                'short_name': 'widget',
                'stem': 'widget',
                'dependency': 'widget',
                'qualifier': '@master',
                'tool_variant': '',
                'state': 'referenced',
                'size_bytes': 1024,
                'last_used_epoch': 1_700_000_000,
                'path': '/tmp/widget',
                'source_url': 'git+https://example.com/org/widget.git@master',
                'location': '',
            },
    ]

    def fake_collect( construct, cuppa_env, names=None, out=None ):
        return { 'rows': rows }

    monkeypatch.setattr( dependency_actions, '_collect_rows', fake_collect )
    monkeypatch.setattr(
            dependency_actions, 'emit_location_unqualified_duplicate_hints',
            lambda **kwargs: None,
    )

    out = StringIO()
    dependency_actions.write_unknown_remove_names_error(
            construct=None,
            cuppa_env={},
            error=UnknownDependencyNames(
                    unknown=( 'conan', ),
                    project_used=( 'widget', ),
            ),
            out=out,
    )
    text = out.getvalue()
    assert 'is not a used dependency' in text
    assert 'Known dependencies which can be removed' in text
    assert 'DEPENDENCY' in text
    assert 'widget' in text
    assert 'used' in text


def test_unknown_remove_hint_keeps_used_not_only_referenced():
    """Regression: filtering only label==referenced drops the default used section."""
    rows = [
            {
                'type': 'vcs',
                'short_name': 'widget',
                'stem': 'widget',
                'dependency': 'widget',
                'qualifier': '@master',
                'tool_variant': '',
                'state': 'referenced',
                'size_bytes': 1024,
                'last_used_epoch': 1_700_000_000,
                'path': '/tmp/widget',
                'source_url': 'git+https://example.com/org/widget.git@master',
                'location': '',
            },
    ]
    tree = dependency_tree.build_tree( rows )
    labels = { section.get( 'label' ) for section in tree.get( 'sections' ) or [] }
    assert 'used' in labels
    assert 'referenced' not in labels
    kept = [
            section for section in tree.get( 'sections' ) or []
            if section.get( 'label' ) in ( 'used', 'referenced' )
            and section.get( 'children' )
    ]
    assert len( kept ) == 1
    assert kept[0]['label'] == 'used'
