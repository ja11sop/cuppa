import pytest

from cuppa.core import storage_options
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_process_storage_options_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    env = FakeEnv()
    storage_options.process_storage_options(env)
    assert env["build_root"] == "_build"
    assert env["download_root"] == "_cuppa"
    assert "cache" in env["cache_root"] or env["cache_root"].endswith("_cache")
