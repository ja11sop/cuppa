import pytest

from cuppa.core import storage_options


pytestmark = pytest.mark.unit


class FakeEnv(dict):
    def get_option(self, name, default=None):
        return self.get(name, default)


def test_process_storage_options_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    env = FakeEnv()
    storage_options.process_storage_options(env)
    assert env["build_root"] == "_build"
    assert env["download_root"] == "_cuppa"
    assert "cache" in env["cache_root"] or env["cache_root"].endswith("_cache")
