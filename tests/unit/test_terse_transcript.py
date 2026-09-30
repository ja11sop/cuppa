#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from types import SimpleNamespace

import pytest

import cuppa.progress as progress
from cuppa.output_processor import SpawnedProcessor


pytestmark = pytest.mark.unit


def _variant_env():
    return {
        "variant": SimpleNamespace(name=lambda: "dbg"),
        "toolchain": SimpleNamespace(name=lambda: "gcc16"),
        "target_arch": "x86_64",
        "abi": "cxx2c",
        "sconscript_file": "./test/orders/sconscript",
    }


def _spawned(terse):
    env = {
        "toolchain": SimpleNamespace(output_interpretors=lambda: []),
        "minimal_output": False,
        "ignore_duplicates": False,
        "terse_output": terse,
    }
    return SpawnedProcessor(env)


def test_progress_lines_stay_hidden_unless_notify_progress_is_set(capsys):
    progress.terse_print_cmd_line("Progress( Begin )", [], [], {})
    assert capsys.readouterr().out == ""
    assert progress.take_terse_command()[0] is None

    progress.terse_print_cmd_line(
            "Progress( Begin )", [], [], {"terse_output_notify_progress": True},
    )
    assert capsys.readouterr().out == "Progress( Begin )\n"
    assert progress.take_terse_command()[0] is None


def test_a_command_that_never_spawns_is_reprinted_before_the_next_line(capsys):
    notify = {"terse_output_notify_progress": True}
    progress.terse_print_cmd_line("Removing empty directories", ["stamp"], [], {})
    assert capsys.readouterr().out == ""
    progress.terse_print_cmd_line("Progress( End )", [], [], notify)
    assert capsys.readouterr().out == "Removing empty directories\nProgress( End )\n"
    assert progress.take_terse_command()[0] is None


def test_tool_commands_are_stashed_instead_of_printed(capsys):
    target = ["build/hello.o"]
    env = _variant_env()
    progress.terse_print_cmd_line("g++ -c hello.cpp", target, [], env)
    assert capsys.readouterr().out == ""
    command, stashed_target, _source, stashed_env = progress.take_terse_command()
    assert command == "g++ -c hello.cpp"
    assert stashed_target == target
    assert stashed_env is env
    assert progress.take_terse_command() == (None, None, None, None)


def test_success_line_names_sconscript_variant_action_and_source():
    assert progress.terse_counts_prefix() == ""
    line = progress.format_terse_success(
            "g++ -c test/orders/src/hello.cpp",
            ["_build/hello.o"],
            ["test/orders/src/hello.cpp"],
            _variant_env(),
    )
    assert line == "[ok] test/orders · gcc16_dbg_x86_64_cxx2c · compile src/hello.cpp"


def test_action_spelling_separates_archive_index_and_link():
    env = _variant_env()
    assert progress.spell_terse_action("ar rc libquince.a a.o", ["libquince.a"]) == "archive"
    assert progress.spell_terse_action("ranlib libquince.a", ["libquince.a"]) == "index"
    assert progress.spell_terse_action("g++ -o buy_sell_ladder buy_sell_ladder.o", ["buy_sell_ladder"]) == "link"
    assert progress.spell_terse_action("/usr/bin/g++-16 -o buy_sell_ladder buy_sell_ladder.o", ["buy_sell_ladder"]) == "link"
    assert progress.spell_terse_action("g++ -shared -o libfoo.so a.o", ["libfoo.so"]) == "link-shared"
    assert progress.format_terse_line(
            "error", "g++ -o buy_sell_ladder buy_sell_ladder.o", ["buy_sell_ladder"], ["buy_sell_ladder.o"], env,
    ) == "[error] test/orders · gcc16_dbg_x86_64_cxx2c · link buy_sell_ladder"


def test_clean_run_is_one_line_and_a_warning_reprints_the_command():
    env = _variant_env()
    source = ["test/orders/hello.cpp"]
    ok = progress.render_terse_spawn(
            0, 0, 0, ["note\n"], "g++ -c test/orders/hello.cpp", ["hello.o"], source, env, "",
    )
    assert ok == ["[ok] test/orders · gcc16_dbg_x86_64_cxx2c · compile hello.cpp"]

    warned = progress.render_terse_spawn(
            0, 0, 1, ["warn line\n"], "g++ -c test/orders/hello.cpp", ["hello.o"], source, env,
            " === Warnings 1 === ",
    )
    assert warned[0] == "[warn] test/orders · gcc16_dbg_x86_64_cxx2c · compile hello.cpp"
    assert warned[1] == "g++ -c test/orders/hello.cpp"
    assert "warn line" in warned
    assert "[ok]" not in "\n".join(warned)


def test_failed_run_prints_an_error_line_before_the_command():
    failed = progress.render_terse_spawn(
            1, 1, 0, ["bad\n"], "g++ -c hello.cpp", ["hello.o"], ["hello.cpp"], {}, "summary\n",
    )
    assert failed[0] == "[error] compile hello.cpp"
    assert failed[1] == "g++ -c hello.cpp"
    assert "bad" in failed
    assert "summary" in failed


def test_spawn_folds_a_clean_run_and_discards_the_stash(capsys):
    progress.stash_terse_command(
            "g++ -c test/orders/hello.cpp", ["hello.o"], ["test/orders/hello.cpp"], _variant_env(),
    )
    spawned = _spawned(True)
    assert spawned("noise the compiler wrote") is None
    spawned.finish(0)
    out = capsys.readouterr().out
    assert out.strip() == "[ok] test/orders · gcc16_dbg_x86_64_cxx2c · compile hello.cpp"
    assert "noise" not in out
    assert progress.take_terse_command()[0] is None


def test_spawn_reprints_the_command_when_the_tool_fails(capsys):
    progress.stash_terse_command("g++ -c hello.cpp", ["hello.o"], ["hello.cpp"], {})
    spawned = _spawned(True)
    spawned._processor.errors = 1
    spawned._buffered.append("bad.cpp: error\n")
    spawned.finish(1)
    out = capsys.readouterr().out
    assert out.startswith("[error] compile hello.cpp\n")
    assert "g++ -c hello.cpp" in out
    assert "bad.cpp: error" in out
    assert "[ok]" not in out


def test_spawn_without_terse_returns_lines_for_immediate_printing(capsys):
    spawned = _spawned(False)
    assert spawned("hello from the tool") == "hello from the tool"
    spawned.finish(0)
    assert capsys.readouterr().out == ""
