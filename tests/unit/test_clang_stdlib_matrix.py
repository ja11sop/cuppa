#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from tests.helpers.cuppa_runner import merge_cuppa_args
from tests.helpers.toolchains import (
    CLANG_STDLIB_LIBCXX,
    CLANG_STDLIB_LIBSTDCXX,
    active_clang_stdlib,
    clang_stdlib_flag,
    clang_stdlib_matrix_params,
)


pytestmark = pytest.mark.unit


def test_merge_cuppa_args_later_stdlib_wins():
    merged = merge_cuppa_args(
        ["--toolchains=clang", "--clang-stdlib=libstdc++"],
        ["--dbg", "--clang-stdlib=libc++"],
    )
    assert merged == ["--toolchains=clang", "--clang-stdlib=libc++", "--dbg"]


def test_merge_cuppa_args_preserves_non_options():
    merged = merge_cuppa_args(["--dbg"], ["path/with-dashes"])
    assert merged == ["--dbg", "path/with-dashes"]


def test_clang_stdlib_matrix_params_respects_env(monkeypatch):
    import tests.helpers.toolchains as toolchains

    monkeypatch.delenv("CUPPA_TEST_ARGS", raising=False)
    toolchains._clang_stdlib_usable_cache.clear()
    monkeypatch.setattr(
        toolchains,
        "clang_stdlib_usable",
        lambda stdlib: True,
    )
    assert clang_stdlib_matrix_params() == [
        CLANG_STDLIB_LIBSTDCXX,
        CLANG_STDLIB_LIBCXX,
    ]

    monkeypatch.setenv("CUPPA_TEST_ARGS", "--clang-stdlib=libc++")
    assert active_clang_stdlib() == CLANG_STDLIB_LIBCXX
    assert clang_stdlib_matrix_params() == [CLANG_STDLIB_LIBCXX]
    assert clang_stdlib_flag(CLANG_STDLIB_LIBCXX) == "--clang-stdlib=libc++"

    monkeypatch.setenv("CUPPA_TEST_ARGS", "--offline --clang-stdlib=libstdc++")
    assert clang_stdlib_matrix_params() == [CLANG_STDLIB_LIBSTDCXX]


def test_clang_stdlib_matrix_params_omits_unusable_libcxx(monkeypatch):
    import tests.helpers.toolchains as toolchains

    monkeypatch.delenv("CUPPA_TEST_ARGS", raising=False)
    toolchains._clang_stdlib_usable_cache.clear()
    monkeypatch.setattr(
        toolchains,
        "clang_stdlib_usable",
        lambda stdlib: stdlib == CLANG_STDLIB_LIBSTDCXX,
    )
    assert clang_stdlib_matrix_params() == [CLANG_STDLIB_LIBSTDCXX]
