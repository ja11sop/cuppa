import pytest

from cuppa.colourise import (
    BRIGHT_BLACK,
    GREY_256,
    GREY_256_ON_DARK,
    WHITE,
    colour_items,
    colouriser,
    console_background,
    start_subdued,
)


pytestmark = pytest.mark.unit


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
    """Background detection stays honest when the terminal will not say."""
    assert console_background() == 'unknown'


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


def test_subdued_prefers_mid_grey_when_256_colours_are_available( plain_environment ):
    """256-colour subdued: mid grey on light glass, slightly lighter on dark glass."""
    plain_environment.setenv( 'TERM', "xterm-256color" )

    plain_environment.setenv( 'CUPPA_CONSOLE_BACKGROUND', "light" )
    assert start_subdued() == GREY_256

    plain_environment.setenv( 'CUPPA_CONSOLE_BACKGROUND', "dark" )
    assert start_subdued() == GREY_256_ON_DARK

    plain_environment.delenv( 'CUPPA_CONSOLE_BACKGROUND', raising=False )
    assert start_subdued() == GREY_256_ON_DARK


def test_subdued_without_256_colours_picks_ink_toward_the_background( plain_environment ):
    """No mid-grey rung: dark ink on light glass, light ink on dark (or unknown) glass."""
    plain_environment.delenv( 'TERM', raising=False )
    plain_environment.delenv( 'COLORTERM', raising=False )

    plain_environment.setenv( 'CUPPA_CONSOLE_BACKGROUND', "light" )
    assert start_subdued() == BRIGHT_BLACK

    plain_environment.setenv( 'CUPPA_CONSOLE_BACKGROUND', "dark" )
    assert start_subdued() == WHITE

    plain_environment.delenv( 'CUPPA_CONSOLE_BACKGROUND', raising=False )
    assert console_background() == 'unknown'
    assert start_subdued() == WHITE


def test_remove_notice_and_remove_error_meanings( plain_environment ):
    from cuppa.colourise import as_remove_error, as_remove_notice, as_error, as_warning
    assert as_remove_notice( 'x' ) == as_warning( 'x' )
    assert as_remove_error( 'x' ) == as_error( 'x' )
