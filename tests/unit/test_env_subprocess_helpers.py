import os

import pytest

from cuppa.utility.env import (
    build_subprocess_env,
    export_for_subprocess,
    merge_callable_exports,
    resolve_inherit_process_env,
)


class FakeEnv(dict):

    def get(self, key, default=None):
        return super().get(key, default)


@pytest.mark.unit
def test_export_for_subprocess_writes_env():
    env = FakeEnv({"ENV": {}})
    export_for_subprocess(env, CUPPA_TEST_VAR="value")
    assert env["ENV"]["CUPPA_TEST_VAR"] == "value"


@pytest.mark.unit
def test_export_for_subprocess_skips_none():
    env = FakeEnv({"ENV": {"KEEP": "yes"}})
    export_for_subprocess(env, DROP=None, SET="ok")
    assert "DROP" not in env["ENV"]
    assert env["ENV"]["SET"] == "ok"


@pytest.mark.unit
def test_merge_callable_exports_dict_only():
    env = FakeEnv({"ENV": {}})
    merge_callable_exports(env, {"A": "1"})
    assert env["ENV"]["A"] == "1"
    merge_callable_exports(env, 0)
    merge_callable_exports(env, None)
    assert env["ENV"] == {"A": "1"}


@pytest.mark.unit
def test_resolve_inherit_process_env_per_run_wins():
    env = FakeEnv({"inherit_process_env": True})
    assert resolve_inherit_process_env(env, per_run=False) is False
    assert resolve_inherit_process_env(env, per_run=True) is True
    assert resolve_inherit_process_env(env, per_run=None) is True


@pytest.mark.unit
def test_build_subprocess_env_default_isolated(monkeypatch):
    monkeypatch.setenv("CUPPA_HOST_ONLY", "from_os")
    env = FakeEnv({"ENV": {"CUPPA_EXPORTED": "from_env"}})
    result = build_subprocess_env(env["ENV"], env, inherit_process_env=False)
    assert result == {"CUPPA_EXPORTED": "from_env"}
    assert "CUPPA_HOST_ONLY" not in result


@pytest.mark.unit
def test_build_subprocess_env_inherit_overlays_env(monkeypatch):
    monkeypatch.setenv("CUPPA_SHARED", "from_os")
    monkeypatch.setenv("CUPPA_HOST_ONLY", "from_os")
    scons_env = FakeEnv(
        {
            "inherit_process_env": True,
            "ENV": {"CUPPA_SHARED": "from_env", "CUPPA_EXPORTED": "from_env"},
        }
    )
    result = build_subprocess_env(scons_env["ENV"], scons_env, inherit_process_env=None)
    assert result["CUPPA_HOST_ONLY"] == "from_os"
    assert result["CUPPA_SHARED"] == "from_env"
    assert result["CUPPA_EXPORTED"] == "from_env"
