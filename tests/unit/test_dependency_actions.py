"""Unit tests for dependency listing helpers."""

import pytest

from cuppa.core import dependency_actions, dependency_storage


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
