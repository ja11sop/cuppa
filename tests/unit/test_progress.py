#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

import cuppa.progress as progress_module
from cuppa.progress import NotifyProgress, VariantCompletionTracker


pytestmark = pytest.mark.unit


class _FakeEnv(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requires_calls = []
        self.depends_calls = []
        self.command_calls = []

    def Requires(self, target, dependency):
        self.requires_calls.append((target, dependency))
        return target

    def Depends(self, target, dependencies):
        self.depends_calls.append((target, dependencies))
        return target

    def Command(self, target, source, action):
        self.command_calls.append((target, source, action))
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
    NotifyProgress._sconscript_env_hooks = set()
    NotifyProgress._sconstruct_begin = None
    NotifyProgress._sconstruct_end = None
    NotifyProgress._begin = {}
    NotifyProgress._end = {}
    NotifyProgress._started = {}
    NotifyProgress._finished = {}
    NotifyProgress.set_inventory_report_mode( False )

    def _fake_progress(label, event, sconscript, variant, env):
        return "progress:{}:{}:{}".format(event, sconscript, variant)

    monkeypatch.setattr(progress_module, "progress", _fake_progress)


def test_variant_is_parent_of_build_dir():
    env = _make_env("test/sconscript", "_build/test/gcc15/dbg/x86_64/c++20/working")
    assert NotifyProgress.variant(env) == "_build/test/gcc15/dbg/x86_64/c++20"


def test_key_joins_sconscript_and_variant():
    env = _make_env("test/sconscript", "_build/test/gcc15/dbg/x86_64/c++20/working")
    assert NotifyProgress.key(env) == "test/sconscript/_build/test/gcc15/dbg/x86_64/c++20"


def test_add_skips_in_pre_sconscript_phase():
    env = _make_env("a/sconscript", "_build/a/dbg/working")
    env["_pre_sconscript_phase_"] = True

    NotifyProgress.add(env, ["node"])

    assert env.requires_calls == []
    assert env.depends_calls == []
    assert NotifyProgress._started == {}
    assert NotifyProgress._finished == {}


def test_add_keys_started_and_finished_by_variant_path():
    # Existing behaviour: _started/_finished are keyed by variant() only
    # (parent of build_dir), not by NotifyProgress.key().
    env = _make_env("test/sconscript", "_build/test/gcc15/dbg/x86_64/c++20/working")

    NotifyProgress.add(env, ["node"])

    variant = "_build/test/gcc15/dbg/x86_64/c++20"
    assert list(NotifyProgress._started.keys()) == [variant]
    assert list(NotifyProgress._finished.keys()) == [variant]


def test_add_reuses_started_finished_for_same_variant_path():
    # Two targets that share the same build_dir parent share Starting/Finished.
    env = _make_env("test/sconscript", "_build/test/dbg/working")

    NotifyProgress.add(env, ["node_a"])
    NotifyProgress.add(env, ["node_b"])

    assert len(NotifyProgress._started) == 1
    assert len(NotifyProgress._finished) == 1
    assert "_build/test/dbg" in NotifyProgress._started


def test_add_inventory_mode_depends_on_targets_and_sconscript_files():
    env = _make_env("test/sconscript", "_build/test/dbg/working")
    NotifyProgress.set_inventory_report_mode(True)

    NotifyProgress.add(env, ["node"])

    finished = NotifyProgress._finished["_build/test/dbg"]
    assert env.depends_calls == [
        ( finished, [ "#test/sconscript", "#sconstruct" ] ),
        ( finished, [ "node" ] ),
    ]
    assert not any(
        call[0] == finished and call[1] == [ "node" ]
        for call in env.requires_calls
    ), "Finished variant must depend on targets via Depends, not Requires"


def test_cuppa_layout_gives_distinct_variant_keys_per_sconscript():
    # In real cuppa layouts, build_dir includes the sconscript path segment, so
    # different sconscripts naturally get different variant() keys without
    # needing sconscript+variant composite keys for _started/_finished.
    env_a = _make_env("a/sconscript", "_build/a/gcc15/dbg/x86_64/c++20/working")
    env_b = _make_env("b/sconscript", "_build/b/gcc15/dbg/x86_64/c++20/working")

    NotifyProgress.add(env_a, ["node_a"])
    NotifyProgress.add(env_b, ["node_b"])

    assert set(NotifyProgress._started.keys()) == {
        "_build/a/gcc15/dbg/x86_64/c++20",
        "_build/b/gcc15/dbg/x86_64/c++20",
    }
    assert set(NotifyProgress._begin.keys()) == {"a/sconscript", "b/sconscript"}
    assert set(NotifyProgress._end.keys()) == {"a/sconscript", "b/sconscript"}


def test_begin_and_end_are_keyed_by_sconscript():
    events = []
    env = _make_env("a/sconscript", "_build/a/dbg/working")

    def _local(event, sconscript, variant, callback_env, target, source):
        events.append(("local", event, sconscript, variant, callback_env))

    def _global(event, sconscript, variant, callback_env, target, source):
        events.append(("global", event, sconscript, variant, callback_env))

    NotifyProgress.register_callback(env, _local)
    NotifyProgress.register_callback(None, _global)

    NotifyProgress.call_callbacks("finished", "a/sconscript", "_build/a/dbg", env, [], [])

    assert ("local", "finished", "a/sconscript", "_build/a/dbg", env) in events
    assert ("global", "finished", "a/sconscript", "_build/a/dbg", env) in events


def test_scope_from_env_matches_variant_and_sconscript():
    env = _make_env("test/sconscript", "_build/test/gcc15/dbg/x86_64/c++20/working")
    assert NotifyProgress.scope_from_env(env) == (
        "test/sconscript",
        "_build/test/gcc15/dbg/x86_64/c++20",
    )


def test_scope_from_env_returns_none_when_fields_missing():
    assert NotifyProgress.scope_from_env({}) is None
    assert NotifyProgress.scope_from_env({"build_dir": "_build/x/working"}) is None


def test_notify_sconscript_env_ready_invokes_registered_hooks():
    calls = []
    env = _make_env("a/sconscript", "_build/a/dbg/working")

    NotifyProgress.register_sconscript_env_hook(lambda e: calls.append(e))

    NotifyProgress.notify_sconscript_env_ready(env)

    assert calls == [env]


def test_variant_completion_tracker_notes_started_and_finished():
    tracker = VariantCompletionTracker()
    variant = "_build/test/dbg/x86_64/c++20"

    tracker.note_progress("started", variant)
    assert tracker.incomplete_variants() == {variant}

    tracker.note_progress("finished", variant)
    assert tracker.incomplete_variants() == set()
