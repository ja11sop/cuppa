#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

import cuppa.progress as progress_module
from cuppa.progress import NotifyProgress


pytestmark = pytest.mark.unit


class _FakeEnv(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requires_calls = []
        self.depends_calls = []

    def Requires(self, target, dependency):
        self.requires_calls.append((target, dependency))
        return target

    def Depends(self, target, dependencies):
        self.depends_calls.append((target, dependencies))
        return target


def _make_env(sconscript_file, build_dir):
    empty_env = _FakeEnv()
    sconscript_env = _FakeEnv(
        sconscript_file=sconscript_file,
        build_dir=build_dir,
    )
    env = _FakeEnv(
        build_dir=build_dir,
        sconscript_file=sconscript_file,
        sconstruct_file="sconstruct",
        empty_env=empty_env,
        sconscript_env=sconscript_env,
    )
    return env


@pytest.fixture(autouse=True)
def _reset_notifyprogress_state(monkeypatch):
    NotifyProgress._callbacks = set()
    NotifyProgress._sconstruct_begin = None
    NotifyProgress._sconstruct_end = None
    NotifyProgress._begin = {}
    NotifyProgress._end = {}
    NotifyProgress._started = {}
    NotifyProgress._finished = {}

    def _fake_progress(label, event, sconscript, variant, env):
        return "progress:{}:{}:{}".format(event, sconscript, variant)

    monkeypatch.setattr(progress_module, "progress", _fake_progress)


def test_add_skips_in_pre_sconscript_phase():
    env = _make_env("a/sconscript", "/repo/a/dbg/working")
    env["_pre_sconscript_phase_"] = True

    NotifyProgress.add(env, ["node"])

    assert env.requires_calls == []
    assert env.depends_calls == []
    assert NotifyProgress._started == {}
    assert NotifyProgress._finished == {}


def test_add_uses_sconscript_and_variant_key_for_started_finished_nodes():
    # Same variant path, different sconscript files: must not share started/finished.
    env_a = _make_env("a/sconscript", "/repo/dbg/working")
    env_b = _make_env("b/sconscript", "/repo/dbg/working")

    NotifyProgress.add(env_a, ["node_a"])
    NotifyProgress.add(env_b, ["node_b"])

    assert len(NotifyProgress._started) == 2
    assert len(NotifyProgress._finished) == 2
    assert "a/sconscript//repo/dbg" in NotifyProgress._started
    assert "b/sconscript//repo/dbg" in NotifyProgress._started


def test_register_callback_routes_env_specific_and_global_callbacks():
    events = []
    env = _make_env("a/sconscript", "/repo/a/dbg/working")

    def _local(event, sconscript, variant, callback_env, target, source):
        events.append(("local", event, sconscript, variant, callback_env))

    def _global(event, sconscript, variant, callback_env, target, source):
        events.append(("global", event, sconscript, variant, callback_env))

    NotifyProgress.register_callback(env, _local)
    NotifyProgress.register_callback(None, _global)

    NotifyProgress.call_callbacks("finished", "a/sconscript", "/repo/a/dbg", env, [], [])

    assert ("local", "finished", "a/sconscript", "/repo/a/dbg", env) in events
    assert ("global", "finished", "a/sconscript", "/repo/a/dbg", env) in events

