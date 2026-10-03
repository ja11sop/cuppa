#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for --native-output passthrough and toolchain flags."""

import pytest

from cuppa.output_processor import SpawnedProcessor, ToolchainProcessor
from cuppa.toolchains.clang import Clang
from cuppa.toolchains.cl import Cl
from cuppa.toolchains.gcc import Gcc


pytestmark = pytest.mark.unit


_ERROR_LINE = "main.cpp:4:5: error: use of undeclared identifier 'Missing'"
_WARNING_LINE = "main.cpp:2:1: warning: unused variable 'x' [-Wunused-variable]"
_PLAIN_LINE = "compiling main.cpp"


class _FakeToolchain(object):
    @classmethod
    def output_interpretors( cls ):
        return Clang.output_interpretors()


def test_gcc_native_output_flags_force_colour_on_pipes():
    flags = Gcc.native_output_flags( object(), {} )
    assert flags == [ '-fdiagnostics-color=always' ]


def test_clang_native_output_flags_enable_diagnostics_colour():
    flags = Clang.native_output_flags( object(), {} )
    assert flags == [ '-fcolor-diagnostics' ]


def test_cl_native_output_flags_use_caret_diagnostics():
    flags = Cl.native_output_flags( object(), {} )
    assert flags == [ '/diagnostics:caret' ]


def test_native_passthrough_keeps_the_toolchain_line_and_counts():
    processor = ToolchainProcessor(
            _FakeToolchain,
            minimal_output=False,
            ignore_duplicates=False,
            native_output=True,
    )
    assert processor( _ERROR_LINE ) == _ERROR_LINE
    assert processor( _WARNING_LINE ) == _WARNING_LINE
    assert processor( _PLAIN_LINE ) == _PLAIN_LINE
    assert processor.errors == 1
    assert processor.warnings == 1
    assert "= Error " not in processor( _ERROR_LINE )


def test_default_processor_still_recolours_errors():
    processor = ToolchainProcessor(
            _FakeToolchain,
            minimal_output=False,
            ignore_duplicates=False,
            native_output=False,
    )
    out = processor( _ERROR_LINE )
    assert out is not None
    assert "= Error 1 =" in out
    assert processor.errors == 1


def test_spawned_processor_honours_native_env_flag():
    env = {
            "toolchain": _FakeToolchain,
            "minimal_output": False,
            "ignore_duplicates": False,
            "native_output": True,
            "terse_output": False,
            "sconscript_file": "./test/sconscript",
    }
    spawned = SpawnedProcessor( env )
    assert spawned( _ERROR_LINE ) == _ERROR_LINE
    assert spawned._processor.native_output is True
    assert spawned._processor.errors == 1
