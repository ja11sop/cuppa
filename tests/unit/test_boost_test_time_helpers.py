import pytest

from cuppa.cpp.run_patched_boost_test import duration_from_elapsed, nanosecs_from_time


pytestmark = pytest.mark.unit


def test_nanosecs_from_time():
    assert nanosecs_from_time("1.5") == 1_500_000_000
    assert nanosecs_from_time("0.0") == 0


def test_duration_from_elapsed():
    assert duration_from_elapsed(0) == "00:00:00.000,000,000"
    assert duration_from_elapsed(1_000_000_000) == "00:00:01.000,000,000"
