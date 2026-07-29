#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.utility.depends import with_depends


pytestmark = pytest.mark.unit


def test_with_depends_no_extras_returns_source():
    assert with_depends("prog") == "prog"
    assert with_depends("prog", None, None) == "prog"


def test_with_depends_merges_groups():
    merged = with_depends(["prog"], "a.txt", ["b.txt"])
    assert list(merged) == ["prog", "a.txt", "b.txt"]


def test_with_depends_without_source():
    assert list(with_depends(None, "a.txt")) == ["a.txt"]
    assert list(with_depends([], "a.txt", None)) == ["a.txt"]


def test_merge_depends():
    from cuppa.utility.depends import merge_depends

    assert merge_depends(None, None) is None
    assert list(merge_depends("a.txt", ["b.txt"])) == ["a.txt", "b.txt"]
