from types import SimpleNamespace

import pytest

from cuppa.construct import ParseToolchainsOption
from cuppa.core.options import list_parser


pytestmark = pytest.mark.unit


def test_list_parser_splits_commas():
    parser = SimpleNamespace(values=SimpleNamespace())
    list_parser("projects")(None, "--scripts", "a,b,c", parser)
    assert parser.values.projects == ["a", "b", "c"]


def test_parse_toolchains_option_wildcards():
    parser = SimpleNamespace(values=SimpleNamespace())
    callback = ParseToolchainsOption(
        supported_toolchains=["gcc", "gcc15", "clang", "clang21"],
        available_toolchains=["gcc15", "clang21"],
    )
    callback(None, "--toolchains", "gcc*", parser)
    assert set(parser.values.toolchains) == {"gcc15"}

    callback(None, "--toolchains", "clang21,gcc15", parser)
    assert set(parser.values.toolchains) == {"clang21", "gcc15"}
