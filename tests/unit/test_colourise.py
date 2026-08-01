import pytest

from cuppa.colourise import (
    BRIGHT_BLACK,
    GREY_256,
    colour_items,
    colouriser,
    console_background,
    start_subdued,
)


pytestmark = pytest.mark.unit


DIM = "\x1b[2m"


@pytest.fixture
def plain_environment( monkeypatch ):
    """A console that says nothing about itself, so each test states only what it is about."""
    for variable in ( 'CUPPA_CONSOLE_BACKGROUND', 'COLORFGBG', 'TERM', 'COLORTERM' ):
        monkeypatch.delenv( variable, raising=False )

    was = colouriser.use_colour
    colouriser.enable()
    yield monkeypatch
    colouriser.use_colour = was


def test_colour_items_joins_values():
    text = colour_items(["a", "b", "c"])
    assert "a" in text
    assert "b" in text
    assert "c" in text


def test_a_console_that_says_nothing_is_not_assumed_to_be_light( plain_environment ):
    """Dimming a dark console is safe; treating a dark console as light is not."""
    assert console_background() == 'unknown'
    assert start_subdued() == DIM


@pytest.mark.parametrize( "reported,background", [
    ( "15;0", 'dark' ),
    ( "0;15", 'light' ),
    ( "0;default;15", 'light' ),
    ( "default;7", 'light' ),
    ( "7;8", 'dark' ),
] )
def test_the_background_is_read_from_colorfgbg_where_a_terminal_sets_it(
        plain_environment, reported, background ):
    plain_environment.setenv( 'COLORFGBG', reported )
    assert console_background() == background


def test_the_background_can_be_declared_when_the_terminal_will_not_say( plain_environment ):
    """Most terminals report nothing, so the setting has to be available to say it outright."""
    plain_environment.setenv( 'COLORFGBG', "0;15" )
    plain_environment.setenv( 'CUPPA_CONSOLE_BACKGROUND', "dark" )
    assert console_background() == 'dark'


def test_a_light_console_recedes_by_going_grey_rather_than_by_dimming( plain_environment ):
    """Reduced intensity applied to black text on white can look untouched, so grey is used."""
    plain_environment.setenv( 'CUPPA_CONSOLE_BACKGROUND', "light" )

    plain_environment.setenv( 'TERM', "xterm-256color" )
    assert start_subdued() == GREY_256

    plain_environment.setenv( 'TERM', "xterm" )
    assert start_subdued() == BRIGHT_BLACK


def test_nothing_is_emitted_when_colour_is_off( plain_environment ):
    plain_environment.setenv( 'CUPPA_CONSOLE_BACKGROUND', "light" )
    colouriser.use_colour = False
    assert start_subdued() == ''
