#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.coverage_workflow import (
    PARALLEL_COVERAGE_COLLECTION_WARNING,
    maybe_warn_parallel_coverage_collection,
    parallel_coverage_collection_warning_text,
    should_warn_parallel_coverage_collection,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ( dict( job_count=8, cov=True, test=True ), True ),
        ( dict( job_count=8, cov=True, force_test=True ), True ),
        ( dict( job_count=8, cov=True, benchmark=True ), True ),
        ( dict( job_count=8, cov=True, force_benchmark=True ), True ),
        ( dict( job_count=1, cov=True, test=True ), False ),
        ( dict( job_count=8, cov=True, test=False ), False ),
        ( dict( job_count=8, cov=False, test=True ), False ),
        ( dict( job_count=0, cov=True, test=True ), False ),
    ],
)
def test_should_warn_parallel_coverage_collection( kwargs, expected ):
    assert should_warn_parallel_coverage_collection( **kwargs ) is expected


def test_warning_text_keeps_stable_token():
    text = parallel_coverage_collection_warning_text()
    assert PARALLEL_COVERAGE_COLLECTION_WARNING in text
    assert "--cov --parallel" in text
    assert "--cov --test" in text


def test_maybe_warn_emits_once_when_collecting( caplog ):
    caplog.set_level( "WARNING", logger="cuppa" )
    asserted = maybe_warn_parallel_coverage_collection( job_count=4, cov=True, test=True )
    silent = maybe_warn_parallel_coverage_collection( job_count=4, cov=True )
    assert asserted is True
    assert silent is False
    assert PARALLEL_COVERAGE_COLLECTION_WARNING in caplog.text
