#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest
import SCons.Errors

from cuppa.core import output_options
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


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
    output_options.process_output_options(env)
    assert env["scons_output"] is True
    assert env["raw_output"] is False
    assert env.colour_enabled is True
    assert output_options.skips_spawn_processor(env) is True


def test_raw_output_disables_colour_and_skips_the_processor():
    env = _ColourEnv(raw_output=True)
    output_options.process_output_options(env)
    assert env.colour_enabled is False
    assert output_options.skips_spawn_processor(env) is True


def test_scons_output_with_standard_output_matches_raw_colour_off():
    env = _ColourEnv(scons_output=True, standard_output=True)
    output_options.process_output_options(env)
    assert env.colour_enabled is False
    assert output_options.skips_spawn_processor(env) is True


def test_minimal_output_refuses_scons_or_raw_spawn_skip():
    for flags in ( {"minimal_output": True, "scons_output": True},
                   {"minimal_output": True, "raw_output": True} ):
        env = _ColourEnv(**flags)
        with pytest.raises(SCons.Errors.StopError) as caught:
            output_options.process_output_options(env)
        assert "--minimal-output" in str(caught.value)


def test_terse_output_refuses_scons_or_raw_spawn_skip():
    for flags in ( {"terse_output": True, "scons_output": True},
                   {"terse_output": True, "raw_output": True} ):
        env = _ColourEnv(**flags)
        with pytest.raises(SCons.Errors.StopError) as caught:
            output_options.process_output_options(env)
        assert "--terse-output" in str(caught.value)


def test_normal_output_is_the_false_terse_choice():
    env = _ColourEnv(terse_output=False)
    output_options.process_output_options(env)
    assert env["terse_output"] is False


def test_terse_output_is_the_true_terse_choice():
    env = _ColourEnv(terse_output=True)
    output_options.process_output_options(env)
    assert env["terse_output"] is True


def test_normal_and_terse_on_the_same_command_line_are_refused(monkeypatch):
    monkeypatch.setattr(
            "cuppa.core.options.command_line_option",
            lambda name: True if name in ("normal_output", "terse_output") else None,
    )
    with pytest.raises(SCons.Errors.StopError) as caught:
        output_options.process_output_options(_ColourEnv())
    assert "--normal-output and --terse-output" in str(caught.value)


def test_a_saved_terse_only_flag_is_ignored_on_a_normal_run(monkeypatch):
    monkeypatch.setattr("cuppa.core.options.command_line_option", lambda name: None)
    env = _ColourEnv(
            terse_output=False,
            show_test_cases=True,
            terse_output_show_actions=True,
    )
    output_options.process_output_options(env)
    assert env["terse_output"] is False
    assert env["show_test_cases"] is False
    assert env["terse_output_show_actions"] is False


def test_a_command_line_terse_only_flag_is_refused_on_a_normal_run(monkeypatch):
    monkeypatch.setattr(
            "cuppa.core.options.command_line_option",
            lambda name: True if name == "show_test_cases" else None,
    )
    env = _ColourEnv(
            terse_output=False,
            show_test_cases=True,
    )
    with pytest.raises(SCons.Errors.StopError) as caught:
        output_options.process_output_options(env)
    assert "--show-test-cases" in str(caught.value)


def test_terse_and_minimal_together_keep_the_processor():
    env = _ColourEnv(terse_output=True, minimal_output=True)
    output_options.process_output_options(env)
    assert env["terse_output"] is True
    assert env["minimal_output"] is True
    assert output_options.skips_spawn_processor(env) is False


def test_native_output_keeps_the_processor_and_colour():
    env = _ColourEnv(native_output=True)
    output_options.process_output_options(env)
    assert env["native_output"] is True
    assert env.colour_enabled is True
    assert output_options.skips_spawn_processor(env) is False


def test_native_output_refuses_scons_or_raw_spawn_skip():
    for flags in ( {"native_output": True, "scons_output": True},
                   {"native_output": True, "raw_output": True} ):
        env = _ColourEnv(**flags)
        with pytest.raises(SCons.Errors.StopError) as caught:
            output_options.process_output_options(env)
        assert "--native-output" in str(caught.value)


def test_native_output_ignores_minimal_with_a_warning(caplog):
    env = _ColourEnv(native_output=True, minimal_output=True)
    output_options.process_output_options(env)
    assert env["native_output"] is True
    assert env["minimal_output"] is False
    assert "--minimal-output is ignored with --native-output" in caplog.text


def test_native_and_terse_together_keep_the_processor():
    env = _ColourEnv(native_output=True, terse_output=True)
    output_options.process_output_options(env)
    assert env["native_output"] is True
    assert env["terse_output"] is True
    assert output_options.skips_spawn_processor(env) is False
