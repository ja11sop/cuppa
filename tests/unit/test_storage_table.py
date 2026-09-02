"""Unit tests for storage table padding with coloured cells."""

import pytest

from cuppa.colourise import as_info, as_subdued, colouriser
from cuppa.utility import storage
from cuppa.utility.preprocess import AnsiEscape


pytestmark = pytest.mark.unit


COLUMNS = [
    ( 'size', 'SIZE' ),
    ( 'type', 'TYPE' ),
    ( 'dependency', 'DEPENDENCY' ),
    ( 'state', 'STATE' ),
]


@pytest.fixture
def colour():
    """Colour is off by default in tests; enable it for ANSI-aware padding checks."""
    was = colouriser.use_colour
    colouriser.enable()
    yield
    colouriser.use_colour = was


def test_visible_len_ignores_html_colouriser_tokens():
    from cuppa.colourise import using_colouriser
    from cuppa.colourise_html import HtmlColouriser

    backend = HtmlColouriser()
    with using_colouriser( backend ):
        coloured = as_info( 'boost' )
    assert len( coloured ) > len( 'boost' )
    assert storage.visible_len( coloured ) == len( 'boost' )


def test_visible_len_ignores_ansi( colour ):
    plain = 'boost'
    coloured = as_info( plain )
    assert len( coloured ) > len( plain )
    assert storage.visible_len( coloured ) == len( plain )
    assert storage.visible_len( as_subdued( plain ) ) == len( plain )


def test_render_table_aligns_coloured_and_plain_cells( colour ):
    rows = [
        {
            'size': as_subdued( '~288.6M' ),
            'type': as_subdued( 'gitlab' ),
            'dependency': as_subdued( 'boost' ),
            'state': as_subdued( 'unreferenced' ),
        },
        {
            'size': '299.3M',
            'type': as_info( 'gitlab' ),
            'dependency': as_info( 'boost_package' ),
            'state': as_info( 'referenced' ),
        },
    ]
    lines = storage.render_table( COLUMNS, rows )
    assert len( lines ) == 3  # header + 2 rows

    plain_lines = [ AnsiEscape.strip( line ) for line in lines ]
    header_offsets = _column_offsets( plain_lines[0] )
    for line in plain_lines[1:]:
        assert _column_offsets( line ) == header_offsets

    # ANSI must not stretch the rule beyond the visible table.
    assert max( storage.visible_len( line ) for line in lines ) < max( len( line ) for line in lines )


def _column_offsets( plain_line ):
    """Start index of each whitespace-separated field (approximate column starts)."""
    offsets = []
    in_field = False
    for index, char in enumerate( plain_line ):
        if char != ' ' and not in_field:
            offsets.append( index )
            in_field = True
        elif char == ' ':
            in_field = False
    return offsets


def test_pad_visible_appends_spaces_after_ansi( colour ):
    coloured = as_info( 'gitlab' )
    padded = storage.pad_visible( coloured, 12 )
    assert storage.visible_len( padded ) == 12
    assert padded.startswith( coloured )
    assert padded.endswith( ' ' * ( 12 - len( 'gitlab' ) ) )
