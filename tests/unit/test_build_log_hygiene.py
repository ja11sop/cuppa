#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Configure-time log hygiene — demotions and readable default-variant messages."""

import inspect

import pytest

from cuppa.construct import Construct
from cuppa.toolchains import toolchain_archive as ta


pytestmark = pytest.mark.unit


class _NamedTask:
    def __str__( self ):
        return "<Dbg object at 0xdeadbeef>"


def test_format_active_task_names_uses_sorted_keys_not_objects():
    text = Construct._format_active_task_names( {
        "rel": _NamedTask(),
        "dbg": _NamedTask(),
    } )
    assert "dbg" in text
    assert "rel" in text
    assert "Dbg object" not in text
    # Sorted keys → dbg before rel
    assert text.index( "dbg" ) < text.index( "rel" )


def test_available_toolchains_line_is_debug():
    source = inspect.getsource( Construct.add_toolchains )
    assert 'logger.debug( "available toolchains are [{}]"' in source
    assert 'logger.info( "available toolchains are [{}]"' not in source


def test_registered_toolchain_lines_are_debug():
    clang_src = inspect.getsource( ta._register_clang_entries )
    gcc_src = inspect.getsource( ta._register_gcc_entries )
    for source in ( clang_src, gcc_src ):
        assert "Registered toolchain" in source
        assert "logger.debug" in source
        assert 'logger.info(\n            "Registered toolchain' not in source


def test_format_active_task_names_empty():
    # colour_items([]) formats as an empty quoted join → "''"
    assert Construct._format_active_task_names( {} ) == "''"
