#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from types import SimpleNamespace

import pytest

from cuppa.construct import Construct
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_normalise_with_defaults_list_merge():
    values, defaults, warning = Construct._normalise_with_defaults(
        ["custom"], ["dbg", "rel"], "variants"
    )
    assert warning is None
    assert defaults == ["dbg", "rel"]
    assert values == ["custom"]


def test_normalise_with_defaults_deprecated_dict():
    class Named:
        def name(self):
            return "from_obj"

    obj = Named()
    values, defaults, warning = Construct._normalise_with_defaults(
        {"x": "cli"}, [obj], "dependencies"
    )
    assert "deprecated" in warning
    assert "cli" in values
    assert obj in values
    assert defaults == ["from_obj"]


def test_command_line_from_settings_formats_flags():
    construct = Construct.__new__(Construct)
    line = construct._command_line_from_settings(
        {"dbg": True, "toolchains": ["gcc", "clang"], "jobs": 4}
    )
    assert "--dbg" in line
    assert "--toolchains=" in line
    assert "gcc,clang" in line
    assert "--jobs=4" in line


def test_get_active_actions_matrix():
    construct = Construct.__new__(Construct)
    construct.variants_key = "variants"
    construct.actions_key = "actions"

    dbg = SimpleNamespace(name=lambda: "dbg")
    test_action = SimpleNamespace(name=lambda: "test")
    run_action = SimpleNamespace(name=lambda: "run")

    env = FakeEnv(
        {
            "variants": {"dbg": dbg},
            "actions": {"dbg": dbg, "test": test_action, "run": run_action},
            "test": True,
            "run": False,
            "dbg": False,
        }
    )

    active = construct.get_active_actions(env, dbg, [], [])
    assert "test" in active
    assert "run" not in active
    assert "dbg" not in active  # not current variant option and not requested

    env["dbg"] = True
    active_with_variant = construct.get_active_actions(env, dbg, [], [])
    assert "dbg" in active_with_variant
    assert "test" in active_with_variant


def test_get_sub_sconscripts_discovers_tree(tmp_path):
    construct = Construct.__new__(Construct)
    root = tmp_path / "proj"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "sconscript").write_text("", encoding="utf-8")
    (root / "app").mkdir()
    (root / "app" / "foo.sconscript").write_text("", encoding="utf-8")
    skip = root / "_build" / "nested"
    skip.mkdir(parents=True)
    (skip / "sconscript").write_text("", encoding="utf-8")
    nested_project = root / "vendor" / "other"
    nested_project.mkdir(parents=True)
    (nested_project / "sconstruct").write_text("", encoding="utf-8")
    (nested_project / "sconscript").write_text("", encoding="utf-8")

    found = construct.get_sub_sconscripts(str(root), ["_build", "_cuppa"])
    found_str = [str(p).replace("\\", "/") for p in found]
    assert any(p.endswith("lib/sconscript") for p in found_str)
    assert any(p.endswith("app/foo.sconscript") for p in found_str)
    assert not any("_build" in p for p in found_str)
    assert not any("vendor/other" in p for p in found_str)
