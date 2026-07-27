import pytest

from cuppa.timer import CpuTimes, as_duration_string, as_wall_cpu_percent_string


pytestmark = pytest.mark.unit


def test_cpu_times_add_sub():
    a = CpuTimes(100, 50, 10, 40)
    b = CpuTimes(20, 10, 2, 8)
    summed = a + b
    assert summed.wall == 120
    assert summed.process == 60
    diff = a - b
    assert diff.wall == 80
    assert diff.user == 32


def test_cpu_times_add_rejects_other_types():
    with pytest.raises(TypeError):
        CpuTimes(1, 1, 1, 1) + 5


def test_as_duration_string_zero():
    assert as_duration_string(0) == "00:00:00.000,000,000"


def test_as_duration_string_one_second():
    assert as_duration_string(1_000_000_000) == "00:00:01.000,000,000"


def test_as_wall_cpu_percent_string():
    times = CpuTimes(wall=200, process=100, system=0, user=100)
    assert "50.00%" in as_wall_cpu_percent_string(times).replace(" ", "")
    assert as_wall_cpu_percent_string(CpuTimes(0, 0, 0, 0)) == "n/a"
