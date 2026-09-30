#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from types import SimpleNamespace

import pytest
import SCons.Errors

from cuppa.construct import Construct
from cuppa.core.run_list_names import coalesce_aliased_run_list
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_normalise_with_defaults_list_merge():
    values, defaults, warning = Construct._normalise_with_defaults(
        ["custom"], ["dbg", "rel"], "variants"
    )
    assert warning is None
    assert defaults == ["dbg", "rel"]
    assert values == ["custom"]


def test_coalesce_aliased_run_list_prefers_new_name():
    assert coalesce_aliased_run_list(
            ["a"], None, "import_dependencies", "dependencies"
    ) == ["a"]


def test_coalesce_aliased_run_list_legacy_when_preferred_omitted():
    assert coalesce_aliased_run_list(
            None, ["b"], "import_dependencies", "dependencies"
    ) == ["b"]


def test_coalesce_aliased_run_list_both_equal_ok():
    assert coalesce_aliased_run_list(
            ["x"], ["x"], "import_dependencies", "dependencies"
    ) == ["x"]


def test_coalesce_aliased_run_list_both_unequal_fails():
    with pytest.raises(SCons.Errors.StopError) as caught:
        coalesce_aliased_run_list(
                ["a"], ["b"], "import_dependencies", "dependencies"
        )
    assert "import_dependencies" in str( caught.value )
    assert "dependencies" in str( caught.value )


def test_coalesce_aliased_run_list_neither_is_empty():
    assert coalesce_aliased_run_list(
            None, None, "import_dependencies", "dependencies"
    ) == []


def test_normalise_with_defaults_object_in_defaults_only():
    class Named:
        @classmethod
        def name( cls ):
            return "widget"

    values, defaults, warning = Construct._normalise_with_defaults(
        [], [Named], "dependencies"
    )
    assert warning is None
    assert defaults == ["widget"]
    assert values == [Named]


def test_normalise_with_defaults_object_in_both_lists_dedupes_registration():
    class Named:
        @classmethod
        def name( cls ):
            return "widget"

    values, defaults, warning = Construct._normalise_with_defaults(
        [Named], [Named], "dependencies"
    )
    assert warning is None
    assert defaults == ["widget"]
    assert values == [Named]


def test_normalise_with_defaults_mix_string_and_object():
    class Named:
        @classmethod
        def name( cls ):
            return "widget"

    values, defaults, warning = Construct._normalise_with_defaults(
        [Named], [Named, "boost"], "dependencies"
    )
    assert defaults == ["widget", "boost"]
    assert values == [Named]


def test_normalise_with_defaults_rejects_nameless_object():
    class Nameless:
        pass

    with pytest.raises(SCons.Errors.StopError) as caught:
        Construct._normalise_with_defaults( [], [Nameless], "dependencies" )
    assert "no name()" in str( caught.value )


def test_normalise_with_defaults_rejects_empty_name():
    class Bad:
        @classmethod
        def name( cls ):
            return ""

    with pytest.raises(SCons.Errors.StopError):
        Construct._normalise_with_defaults( [], [Bad], "dependencies" )


def test_normalise_with_defaults_package_dependency_factory():
    from cuppa.build_with_package import package_dependency

    Widget = package_dependency(
            "widget",
            package_manager="gitlab",
            registry="https://gitlab.example/api/v4/projects/1",
            package="widget",
            version="1.0",
    )
    values, defaults, warning = Construct._normalise_with_defaults(
        [Widget], [Widget], "dependencies"
    )
    assert warning is None
    assert defaults == ["widget"]
    assert values == [Widget]


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


def _make_variant(name):
    return SimpleNamespace(name=lambda n=name: n)


def _create_build_envs_fixture(default_variants, option_flags):
    construct = Construct.__new__(Construct)
    construct.variants_key = "variants"
    construct.actions_key = "actions"

    dbg = _make_variant("dbg")
    rel = _make_variant("rel")
    test_action = SimpleNamespace(name=lambda: "test")

    options = {
        "dbg": False,
        "rel": False,
        "cov": False,
        "test": False,
        "benchmark": False,
        "run": False,
    }
    options.update(option_flags)

    cuppa_env = FakeEnv(
        {
            "variants": {"dbg": dbg, "rel": rel},
            "actions": {"dbg": dbg, "rel": rel, "test": test_action},
            "default_variants": set(default_variants),
            "target_architectures": [None],
            "propagate_env": False,
            "propagate_path": False,
            "merge_path": False,
            "raw_output": True,
        }
    )
    cuppa_env.update(options)

    built = []

    def make_env(cuppa_env_arg, variant, target_arch):
        built.append(variant.name())
        return FakeEnv({"ENV": {}}), target_arch

    toolchain = SimpleNamespace(
        default_variants=lambda: ["dbg", "rel"],
        make_env=make_env,
        abi=lambda env: "abi",
        package_name=lambda: "gcc15",
    )
    return construct, toolchain, cuppa_env, built


def test_create_build_envs_honours_project_defaults_with_test_action():
    construct, toolchain, cuppa_env, built = _create_build_envs_fixture(
        default_variants=["dbg"],
        option_flags={"test": True},
    )
    envs = construct.create_build_envs(toolchain, cuppa_env)
    assert [e["variant"] for e in envs] == ["dbg"]
    assert built == ["dbg"]


def test_create_build_envs_uses_toolchain_defaults_without_project_defaults():
    construct, toolchain, cuppa_env, built = _create_build_envs_fixture(
        default_variants=[],
        option_flags={"test": True},
    )
    envs = construct.create_build_envs(toolchain, cuppa_env)
    assert set(e["variant"] for e in envs) == {"dbg", "rel"}
    assert set(built) == {"dbg", "rel"}


def test_create_build_envs_cli_variant_not_overridden_by_defaults():
    construct, toolchain, cuppa_env, built = _create_build_envs_fixture(
        default_variants=["dbg"],
        option_flags={"rel": True},
    )
    envs = construct.create_build_envs(toolchain, cuppa_env)
    assert [e["variant"] for e in envs] == ["rel"]
    assert built == ["rel"]


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


def test_get_sub_sconscripts_with_only_absolute_excludes_still_finds_scripts(tmp_path):
    """Absolute roots are skipped from the exclude pattern; that must not discard the tree.

    Dependencies now default outside the project, so the exclude list can be empty after
    absolute paths are filtered out. An empty alternation would match every folder.
    """
    construct = Construct.__new__(Construct)
    root = tmp_path / "proj"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "sconscript").write_text("", encoding="utf-8")

    found = construct.get_sub_sconscripts(str(root), [str(tmp_path / "elsewhere"), "_build"])
    found_str = [str(p).replace("\\", "/") for p in found]
    assert any(p.endswith("lib/sconscript") for p in found_str)

    found = construct.get_sub_sconscripts(str(root), [str(tmp_path / "elsewhere")])
    found_str = [str(p).replace("\\", "/") for p in found]
    assert any(p.endswith("lib/sconscript") for p in found_str)


class _ColourEnv(FakeEnv):
    def __init__(self, **flags):
        super().__init__(flags)
        self.colour_enabled = False

    def colouriser(self):
        return self

    def enable(self):
        self.colour_enabled = True


def test_scons_output_keeps_colour_and_skips_only_the_processor():
    env = _ColourEnv(scons_output=True)
    Construct._set_output_format(env)
    assert env["scons_output"] is True
    assert env["raw_output"] is False
    assert env.colour_enabled is True
    assert Construct._skips_spawn_processor(env) is True


def test_raw_output_disables_colour_and_skips_the_processor():
    env = _ColourEnv(raw_output=True)
    Construct._set_output_format(env)
    assert env.colour_enabled is False
    assert Construct._skips_spawn_processor(env) is True


def test_scons_output_with_standard_output_matches_raw_colour_off():
    env = _ColourEnv(scons_output=True, standard_output=True)
    Construct._set_output_format(env)
    assert env.colour_enabled is False
    assert Construct._skips_spawn_processor(env) is True


def test_minimal_output_refuses_scons_or_raw_spawn_skip():
    for flags in ( {"minimal_output": True, "scons_output": True},
                   {"minimal_output": True, "raw_output": True} ):
        env = _ColourEnv(**flags)
        with pytest.raises(SCons.Errors.StopError) as caught:
            Construct._set_output_format(env)
        assert "--minimal-output" in str(caught.value)


def test_terse_output_refuses_scons_or_raw_spawn_skip():
    for flags in ( {"terse_output": True, "scons_output": True},
                   {"terse_output": True, "raw_output": True} ):
        env = _ColourEnv(**flags)
        with pytest.raises(SCons.Errors.StopError) as caught:
            Construct._set_output_format(env)
        assert "--terse-output" in str(caught.value)


def test_notify_progress_requires_terse_output():
    env = _ColourEnv(terse_output_notify_progress=True)
    with pytest.raises(SCons.Errors.StopError) as caught:
        Construct._set_output_format(env)
    assert "--terse-output-notify-progress requires --terse-output" in str(caught.value)


def test_terse_and_minimal_together_keep_the_processor():
    env = _ColourEnv(terse_output=True, minimal_output=True)
    Construct._set_output_format(env)
    assert env["terse_output"] is True
    assert env["minimal_output"] is True
    assert Construct._skips_spawn_processor(env) is False


def test_create_build_envs_skips_processor_for_scons_output(monkeypatch):
    calls = []
    monkeypatch.setattr(
            "cuppa.output_processor.Processor.install",
            lambda env: calls.append(env),
    )
    construct, toolchain, cuppa_env, built = _create_build_envs_fixture(
            default_variants=["dbg"],
            option_flags={"dbg": True},
    )
    cuppa_env["raw_output"] = False
    cuppa_env["scons_output"] = True
    construct.create_build_envs(toolchain, cuppa_env)
    assert calls == []
    assert built == ["dbg"]


def test_create_build_envs_installs_processor_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(
            "cuppa.output_processor.Processor.install",
            lambda env: calls.append(env),
    )
    construct, toolchain, cuppa_env, built = _create_build_envs_fixture(
            default_variants=["dbg"],
            option_flags={"dbg": True},
    )
    cuppa_env["raw_output"] = False
    cuppa_env["scons_output"] = False
    construct.create_build_envs(toolchain, cuppa_env)
    assert len(calls) == 1
    assert built == ["dbg"]


def test_create_build_envs_installs_terse_command_printer(monkeypatch):
    from cuppa.progress import terse_print_cmd_line

    monkeypatch.setattr(
            "cuppa.output_processor.Processor.install",
            lambda env: None,
    )
    construct, toolchain, cuppa_env, built = _create_build_envs_fixture(
            default_variants=["dbg"],
            option_flags={"dbg": True},
    )
    cuppa_env["raw_output"] = False
    cuppa_env["scons_output"] = False
    cuppa_env["terse_output"] = True
    cuppa_env["terse_output_notify_progress"] = True
    envs = construct.create_build_envs(toolchain, cuppa_env)
    assert envs[0]["env"]["PRINT_CMD_LINE_FUNC"] is terse_print_cmd_line
    assert envs[0]["env"]["terse_output"] is True
    assert envs[0]["env"]["terse_output_notify_progress"] is True
    assert built == ["dbg"]
