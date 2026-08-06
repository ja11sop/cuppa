"""Unit tests for shared dependency token parsing (§4.15)."""

import pytest

from cuppa.core import dependency_tokens


pytestmark = pytest.mark.unit


def test_resolve_selector_aliases():
    assert dependency_tokens.resolve_selector( 'source' ) == 'archive'
    assert dependency_tokens.resolve_selector( 'SA' ) == 'archive'
    assert dependency_tokens.resolve_selector( 'gl' ) == 'gitlab'
    assert dependency_tokens.resolve_selector( 'repo' ) == 'repository'
    assert dependency_tokens.resolve_selector( 'location' ) == 'repository'
    assert dependency_tokens.resolve_selector( 'cn' ) == 'conan'


def test_resolve_selector_rejects_single_letter_and_reserved():
    with pytest.raises( ValueError, match='unknown' ):
        dependency_tokens.resolve_selector( 'a' )
    with pytest.raises( ValueError, match='unknown' ):
        dependency_tokens.resolve_selector( 'g' )
    with pytest.raises( ValueError, match='reserved' ):
        dependency_tokens.resolve_selector( 'gh' )


def test_parse_dependency_token_forms():
    parsed, error = dependency_tokens.parse_dependency_token( 'boost' )
    assert error is None
    assert parsed == ( None, 'boost', None )

    parsed, error = dependency_tokens.parse_dependency_token( 'boost/1.8*' )
    assert error is None
    assert parsed == ( None, 'boost', '1.8*' )

    parsed, error = dependency_tokens.parse_dependency_token( '[source]boost/1.8*' )
    assert error is None
    assert parsed == ( 'archive', 'boost', '1.8*' )

    parsed, error = dependency_tokens.parse_dependency_token( '[gl]boost_package' )
    assert error is None
    assert parsed == ( 'gitlab', 'boost_package', None )


def test_parse_dependency_tokens_list():
    tokens, error = dependency_tokens.parse_dependency_tokens(
            '[source]boost/1.8*,[gl]boost_package/1.89'
    )
    assert error is None
    assert tokens == [
            ( 'archive', 'boost', '1.8*' ),
            ( 'gitlab', 'boost_package', '1.89' ),
    ]


def test_row_matches_token_respects_selector():
    row = {
        'short_name': 'boost',
        'dependency': 'boost',
        'qualifier': '1.86.0',
        'type': 'archive',
        'path': '/tmp/boost_1_86_0',
    }
    assert dependency_tokens.row_matches_token( row, 'archive', 'boost', '1.8*' )
    assert not dependency_tokens.row_matches_token( row, 'gitlab', 'boost', '1.8*' )
    assert dependency_tokens.row_matches_token( row, None, 'boost', '1.8*' )
