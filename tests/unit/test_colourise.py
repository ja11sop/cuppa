import pytest

from cuppa.colourise import colour_items


pytestmark = pytest.mark.unit


def test_colour_items_joins_values():
    text = colour_items(["a", "b", "c"])
    assert "a" in text
    assert "b" in text
    assert "c" in text
