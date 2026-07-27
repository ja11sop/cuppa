import pytest

from cuppa.path import lazy_create_path, split_common, unique_short_filename


pytestmark = pytest.mark.unit


def test_split_common_shared_prefix():
    common, left, right = split_common("/a/b/c", "/a/b/d")
    normalized = common.replace("\\", "/").strip("/")
    assert normalized.endswith("a/b") or normalized == "a/b"
    assert "c" in left.replace("\\", "/")
    assert "d" in right.replace("\\", "/")


def test_split_common_identical():
    common, left, right = split_common("/x/y", "/x/y")
    assert left in ("", "/")
    assert right in ("", "/")
    assert "x" in common.replace("\\", "/")


def test_unique_short_filename_truncates_and_hashes():
    long_name = "a" * 80
    short = unique_short_filename(long_name, max_length=48)
    assert len(short) <= 48
    assert short.startswith("a")
    assert "~" in short
    assert unique_short_filename(long_name, max_length=48) == short


def test_lazy_create_path(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    lazy_create_path(str(nested))
    assert nested.is_dir()
    lazy_create_path(str(nested))
    assert nested.is_dir()
