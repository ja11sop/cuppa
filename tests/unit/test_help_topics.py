#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Structured ``cuppa help`` / ``--help-topic=`` (no project tree)."""

import io

import pytest

from cuppa.core import help_topics


pytestmark = pytest.mark.unit


@pytest.fixture( autouse=True )
def _reset_help_catalog():
    help_topics.reset_help_catalog_state()
    yield
    help_topics.reset_help_catalog_state()


def test_parse_help_subcommand_index():
    assert help_topics.parse_help_argv( [ "help" ] ) == ( "index", None )


def test_parse_help_subcommand_topic():
    assert help_topics.parse_help_argv( [ "help", "configure" ] ) == ( "topic", "configure" )


def test_parse_help_subcommand_option():
    assert help_topics.parse_help_argv( [ "help", "--offline" ] ) == ( "option", "--offline" )


def test_parse_help_topic_flag():
    assert help_topics.parse_help_argv( [ "--help-topic=output" ] ) == ( "topic", "output" )
    assert help_topics.parse_help_argv( [ "--dbg", "--help-topic", "storage" ] ) == (
            "topic", "storage",
    )


def test_parse_ignores_bare_scons_help():
    assert help_topics.parse_help_argv( [ "--help" ] ) is None
    assert help_topics.parse_help_argv( [ "-h" ] ) is None
    assert help_topics.parse_help_argv( [ "-D", "--dbg" ] ) is None


def test_format_configure_topic_includes_show_conf():
    text = help_topics.format_topic_help( "configure" )
    assert "--show-conf" in text
    assert "--show-global-conf" in text
    assert "dest=show_conf" in text


def test_format_option_help_related_twins():
    text = help_topics.format_option_help( "--save-conf" )
    assert "--save-conf" in text
    assert "Related:" in text
    assert "--save-global-conf" in text


def test_render_unknown_option_exits_2():
    out = io.StringIO()
    code = help_topics.render_help_request( "option", "--not-a-real-cuppa-flag", out=out )
    assert code == 2
    assert "Unknown" in out.getvalue()


def test_topic_index_lists_bootstrap_topics():
    text = help_topics.format_topic_index()
    assert "configure" in text
    assert "storage" in text
    assert "output" in text
