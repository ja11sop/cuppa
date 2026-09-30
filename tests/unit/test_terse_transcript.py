#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os
import sys
from types import SimpleNamespace

import pytest
import SCons.Action

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
    assert line == "[ok] test/orders · gcc16_dbg_x86_64_cxx2c · compile · test/orders/src/hello.cpp"


def test_action_spelling_separates_archive_index_and_link():
    env = _variant_env()
    assert progress.spell_terse_action("ar rc libquince.a a.o", ["libquince.a"]) == "archive"
    assert progress.spell_terse_action("ranlib libquince.a", ["libquince.a"]) == "index"
    assert progress.spell_terse_action("/usr/bin/gcc-ar-16 rc libfmt.a a.o", ["libfmt.a"]) == "archive"
    assert progress.spell_terse_action("/usr/bin/gcc-ranlib-16 libfmt.a", ["libfmt.a"]) == "index"
    assert progress.spell_terse_action("llvm-ranlib libquince.a", ["libquince.a"]) == "index"
    assert progress.spell_terse_action("g++ -o buy_sell_ladder buy_sell_ladder.o", ["buy_sell_ladder"]) == "link"
    assert progress.spell_terse_action("/usr/bin/g++-16 -o buy_sell_ladder buy_sell_ladder.o", ["buy_sell_ladder"]) == "link"
    assert progress.spell_terse_action("g++ -shared -o libfoo.so a.o", ["libfoo.so"]) == "link-shared"
    assert progress.spell_terse_action("pysassc theme.scss theme.css", ["theme.css"]) == "run"
    assert progress.format_terse_line(
            "error", "g++ -o buy_sell_ladder buy_sell_ladder.o", ["buy_sell_ladder"], ["buy_sell_ladder.o"], env,
    ) == "[error] test/orders · gcc16_dbg_x86_64_cxx2c · link · buy_sell_ladder"


def test_an_explicit_label_wins_over_the_command():
    class _Attributes:
        cuppa_terse_action = "compile-scss"

    class _Node:
        def __init__( self ):
            self.attributes = _Attributes()
            self.path = "theme.css"

    assert progress.spell_terse_action( "pysassc theme.scss theme.css", [ _Node() ] ) == "compile-scss"


def test_the_toolchain_speller_is_asked_before_the_generic_fallback():
    class _Toolchain:
        def name( self ):
            return "gcc16"

        def spell_terse_action( self, command, target ):
            return "index"

    env = _variant_env()
    env["toolchain"] = _Toolchain()
    assert progress.spell_terse_action( "g++ -c hello.cpp", ["hello.o"], env ) == "index"


class _LabelledNode:
    def __init__( self, label, path ):
        self.path = path
        self.attributes = SimpleNamespace( cuppa_terse_action=label )


def _terse_env():
    env = _variant_env()
    env["terse_output"] = True
    return env


def test_install_file_is_copy():
    assert progress.spell_terse_action(
            'Install file: "_build/guide.html" as "_artifacts/guide.html"',
            ["_artifacts/guide.html"],
    ) == "copy"
    assert progress.spell_terse_action(
            'Install directory: "images" as "_artifacts/images"',
            ["_artifacts/images"],
    ) == "copy"


def _layout_env():
    env = _variant_env()
    env["base_path"] = "/proj"
    env["sconscript_file"] = "./reference_guide/sconscript"
    variant = "/proj/_build/reference_guide/gcc16/dbg/x86_64/cxx2c"
    env["abs_final_dir"] = variant + "/final"
    env["abs_build_dir"] = variant + "/working"
    env["abs_artefacts_root"] = "/proj/_artifacts"
    env["flat_build_base"] = "reference_guide_gcc16_dbg_x86_64_cxx2c"
    env["_variant"] = variant
    return env


def test_copy_uses_virtual_roots_and_an_arrow():
    env = _layout_env()
    variant = env.pop( "_variant" )
    moved = progress.format_terse_line(
            "ok",
            'Install file: "a" as "b"',
            [ variant + "/final/cplx.css" ],
            [ variant + "/final/scss/cplx.css" ],
            env,
    )
    assert moved == (
            "[ok] reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
            "<final>/scss/cplx.css → <final>/cplx.css"
    )
    published = progress.format_terse_line(
            "ok",
            'Install file: "a" as "b"',
            [ "/proj/_artifacts/reference_guide_gcc16_dbg_x86_64_cxx2c/reference_guide.html" ],
            [ variant + "/final/reference_guide.html" ],
            env,
    )
    assert published == (
            "[ok] reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
            "<final>/reference_guide.html → <artifacts>/reference_guide.html"
    )
    staged = progress.format_terse_line(
            "ok",
            'Install file: "a" as "b"',
            [ variant + "/working/generated.hpp" ],
            [ "/proj/include/widget.hpp" ],
            env,
    )
    assert staged == (
            "[ok] reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
            "include/widget.hpp → <working>/generated.hpp"
    )
    published_elsewhere = progress.format_terse_line(
            "ok",
            'Install file: "a" as "b"',
            [ "/proj/_artifacts/documentation/platform_guide/platform_guide.html" ],
            [ "/proj/_artifacts/reference_guide_gcc16_dbg_x86_64_cxx2c/platform_guide.html" ],
            env,
    )
    assert published_elsewhere == (
            "[ok] reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
            "<artifacts>/platform_guide.html → "
            "_artifacts/documentation/platform_guide/platform_guide.html"
    )


def test_copy_colours_the_destination_leaf_and_mutes_the_source( monkeypatch ):
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    monkeypatch.setattr( progress, "as_info", lambda text: "<i>" + text + "</i>" )
    monkeypatch.setattr( progress, "as_emphasised", lambda text: "<e>" + text + "</e>" )
    monkeypatch.setattr( progress, "as_colour", lambda meaning, text: text )
    env = _layout_env()
    variant = env.pop( "_variant" )
    line = progress.format_terse_line(
            "ok",
            'Install file: "a" as "b"',
            [ "/proj/_artifacts/reference_guide_gcc16_dbg_x86_64_cxx2c/cplx.css" ],
            [ variant + "/final/scss/cplx.css" ],
            env,
    )
    assert "<s><final>/scss/cplx.css</s> <s>→</s> <s><artifacts>/</s><e><i>cplx.css</i></e>" in line


def test_expand_render_and_redirect_use_the_same_arrow():
    expanded = progress.format_terse_line(
            "ok",
            "expand",
            [ _LabelledNode( "expand", "version.hpp" ) ],
            [ "version.hpp.in" ],
            _variant_env(),
    )
    assert expanded.endswith( "· expand · version.hpp.in → version.hpp" )
    rendered = progress.format_terse_line(
            "ok",
            "render",
            [ _LabelledNode( "render", "page.html" ) ],
            [ "page.html.j2" ],
            _variant_env(),
    )
    assert rendered.endswith( "· render · page.html.j2 → page.html" )
    target = SimpleNamespace(
            path="tool.out",
            attributes=SimpleNamespace( cuppa_terse_action="run", cuppa_terse_paths="transfer" ),
    )
    redirected = progress.format_terse_line(
            "ok", "run tool", [ target ], [ "tool" ], _variant_env(),
    )
    assert redirected.endswith( "· run · tool → tool.out" )


def test_a_program_run_stays_a_single_name():
    line = progress.format_terse_line(
            "ok",
            "buy_sell_ladder",
            [ _LabelledNode( "run", "buy_sell_ladder" ) ],
            [ "buy_sell_ladder" ],
            _variant_env(),
    )
    assert line.endswith( "· run · buy_sell_ladder" )
    assert "→" not in line


def test_markdown_and_asciidoc_show_the_source_path():
    markdown = progress.format_terse_line(
            "ok",
            "markdown",
            [ _LabelledNode( "markdown", "intro.html" ) ],
            [ "user_guides/intro.md" ],
            _variant_env(),
    )
    assert markdown.endswith( "· markdown · user_guides/intro.md" )
    assert "→" not in markdown


def test_an_unlabelled_asciidoctor_command_is_asciidoc():
    assert progress.spell_terse_action( "asciidoctor -o guide.html in.adoc", ["guide.html"] ) == "asciidoc"


def test_a_label_on_a_later_target_is_used():
    plain = SimpleNamespace( path="rendered.adoc", attributes=SimpleNamespace() )
    labelled = _LabelledNode( "asciidoc", "guide.html" )
    assert progress.spell_terse_action( "AsciidocToHtmlRunner()", [ plain, labelled ] ) == "asciidoc"


def test_python_action_success_is_only_the_status_line( capsys ):
    seen = []

    def _action( target, source, env ):
        seen.append( source )
        return 0

    node = _LabelledNode( "compile-scss", "theme.css" )
    env = _terse_env()
    progress.stash_terse_command( "CompileScssAction(theme.css)", [node], ["theme.scss"], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[node], source=["theme.scss"], env=env ) == 0
    assert seen == [["theme.scss"]]
    out = capsys.readouterr().out
    assert out.strip() == (
            "[ok] test/orders · gcc16_dbg_x86_64_cxx2c · compile-scss · theme.scss"
    )
    assert "CompileScssAction" not in out
    assert progress.take_terse_command()[0] is None


def test_install_file_success_hides_the_sentence( capsys ):
    def _action( target, source, env ):
        return 0

    node = SimpleNamespace( path="_artifacts/reference_guide.html", attributes=SimpleNamespace() )
    env = _terse_env()
    command = 'Install file: "_build/reference_guide.html" as "_artifacts/reference_guide.html"'
    progress.stash_terse_command( command, [node], ["_build/reference_guide.html"], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[node], source=["_build/reference_guide.html"], env=env ) == 0
    out = capsys.readouterr().out
    assert out.strip() == (
            "[ok] test/orders · gcc16_dbg_x86_64_cxx2c · copy · "
            "_build/reference_guide.html → _artifacts/reference_guide.html"
    )
    assert "Install file" not in out


def test_a_clean_child_tool_is_hidden( capsys ):
    def _action( target, source, env ):
        progress.note_terse_child( "asciidoctor -o guide.html in.adoc", [ "Writing guide.html" ] )
        return None

    node = _LabelledNode( "asciidoc", "accounts_template.asciidoc" )
    env = _terse_env()
    progress.stash_terse_command( "AsciidocToHtmlRunner()", [node], ["accounts.adoc"], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[node], source=["accounts.adoc"], env=env ) is None
    out = capsys.readouterr().out
    assert out.strip() == (
            "[ok] test/orders · gcc16_dbg_x86_64_cxx2c · asciidoc · accounts.adoc"
    )
    assert "asciidoctor" not in out
    assert "Writing" not in out


def test_a_child_warning_is_printed_before_the_summary( capsys ):
    def _action( target, source, env ):
        progress.note_terse_child(
                "asciidoctor -o guide.html in.adoc",
                [ "asciidoctor: WARNING: optional gem 'pygments.rb' is not available" ],
        )
        return None

    node = _LabelledNode( "asciidoc", "accounts_template.asciidoc" )
    env = _terse_env()
    progress.stash_terse_command( "AsciidocToHtmlRunner()", [node], ["accounts.adoc"], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[node], source=["accounts.adoc"], env=env ) is None
    out = capsys.readouterr().out
    assert out.startswith( "asciidoctor -o guide.html in.adoc\n" )
    assert "WARNING:" in out
    assert "AsciidocToHtmlRunner" not in out
    assert out.rstrip().endswith(
            "[warn] test/orders · gcc16_dbg_x86_64_cxx2c · asciidoc · accounts.adoc"
    )


def test_a_child_error_line_is_summarised_without_failing_the_action( capsys ):
    def _action( target, source, env ):
        progress.note_terse_child(
                "asciidoctor -o guide.html in.adoc",
                [ "asciidoctor: ERROR: accounts.asciidoc: line 37: Failed to generate image" ],
        )
        return None

    node = _LabelledNode( "asciidoc", "accounts_template.asciidoc" )
    env = _terse_env()
    progress.stash_terse_command( "AsciidocToHtmlRunner()", [node], ["accounts.adoc"], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[node], source=["accounts.adoc"], env=env ) is None
    out = capsys.readouterr().out
    assert "ERROR:" in out
    assert out.rstrip().endswith(
            "[error] test/orders · gcc16_dbg_x86_64_cxx2c · asciidoc · accounts.adoc"
    )


def test_install_methods_wrap_the_action_on_the_returned_node():
    action = SCons.Action.Action( lambda target, source, env: 0, 'Install file: "a" as "b"' )
    node = SimpleNamespace(
            executor=SimpleNamespace( get_action_list=lambda: [ action ] ),
            attributes=SimpleNamespace(),
            path="dest.html",
    )

    class Env( dict ):
        def Install( self, target, source ):
            return [ node ]

    env = Env( terse_output=True )
    progress.enable_terse_python_actions( env )
    assert env.Install( "dest.html", "src.html" ) == [ node ]
    assert isinstance( action.execfunction, progress._TersePythonCallable )


def test_python_action_failure_prints_the_description_then_the_summary( capsys ):
    def _action( target, source, env ):
        sys.stdout.write( "scss failed\n" )
        return 2

    node = _LabelledNode( "compile-scss", "theme.css" )
    env = _terse_env()
    progress.stash_terse_command( "compiling theme.scss", [node], ["theme.scss"], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[node], source=["theme.scss"], env=env ) == 2
    out = capsys.readouterr().out
    assert out.startswith( "scss failed\ncompiling theme.scss\n" )
    assert out.rstrip().endswith(
            "[error] test/orders · gcc16_dbg_x86_64_cxx2c · compile-scss · theme.scss"
    )


def test_python_action_exception_is_reported_and_reraised( capsys ):
    def _action( target, source, env ):
        raise RuntimeError( "boom" )

    node = _LabelledNode( "copy", "out.txt" )
    env = _terse_env()
    progress.stash_terse_command( "copy out.txt", [node], ["in.txt"], env )
    wrapped = progress._TersePythonCallable( _action )
    with pytest.raises( RuntimeError, match="boom" ):
        wrapped( target=[node], source=["in.txt"], env=env )
    out = capsys.readouterr().out
    assert "copy out.txt" in out
    assert "[error]" in out


def test_python_action_without_terse_output_is_the_original_callable( capsys ):
    def _action( target, source, env ):
        return 7

    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[], source=[], env={} ) == 7
    assert capsys.readouterr().out == ""


def test_wrapping_a_python_action_does_not_change_its_signature():
    def _action( target, source, env ):
        return 0

    action = SCons.Action.Action( _action, "copy theme.css" )
    before = action.get_presig( [], [], {} )
    progress._wrap_action( action )
    assert action.get_presig( [], [], {} ) == before
    progress._wrap_action( action )
    assert isinstance( action.execfunction, progress._TersePythonCallable )


def test_enable_terse_python_actions_does_nothing_unless_the_flag_is_set():
    builder = object()

    class _Env( dict ):
        pass

    env = _Env()
    env.Builder = builder
    progress.enable_terse_python_actions( env )
    assert env.Builder is builder


def test_clean_run_is_one_line_and_a_warning_reprints_the_command():
    env = _variant_env()
    source = ["test/orders/hello.cpp"]
    ok = progress.render_terse_spawn(
            0, 0, 0, ["note\n"], "g++ -c test/orders/hello.cpp", ["hello.o"], source, env, "",
    )
    assert ok == ["[ok] test/orders · gcc16_dbg_x86_64_cxx2c · compile · test/orders/hello.cpp"]

    warned = progress.render_terse_spawn(
            0, 0, 1, ["warn line\n"], "g++ -c test/orders/hello.cpp", ["hello.o"], source, env,
            " === Warnings 1 === ",
    )
    assert warned[0] == "g++ -c test/orders/hello.cpp"
    assert warned[-1] == "[warn] test/orders · gcc16_dbg_x86_64_cxx2c · compile · test/orders/hello.cpp"
    assert "warn line" in warned
    assert "[ok]" not in "\n".join(warned)


def test_failed_run_prints_the_command_before_the_error_summary():
    failed = progress.render_terse_spawn(
            1, 1, 0, ["bad\n"], "g++ -c hello.cpp", ["hello.o"], ["hello.cpp"], {}, "summary\n",
    )
    assert failed[0] == "g++ -c hello.cpp"
    assert "bad" in failed
    assert "summary" in failed
    assert failed[-1] == "[error] compile · hello.cpp"


def test_spawn_folds_a_clean_run_and_discards_the_stash(capsys):
    progress.stash_terse_command(
            "g++ -c test/orders/hello.cpp", ["hello.o"], ["test/orders/hello.cpp"], _variant_env(),
    )
    spawned = _spawned(True)
    assert spawned("noise the compiler wrote") is None
    spawned.finish(0)
    out = capsys.readouterr().out
    assert out.strip() == "[ok] test/orders · gcc16_dbg_x86_64_cxx2c · compile · test/orders/hello.cpp"
    assert "noise" not in out
    assert progress.take_terse_command()[0] is None


def test_spawn_reprints_the_command_when_the_tool_fails(capsys):
    progress.stash_terse_command("g++ -c hello.cpp", ["hello.o"], ["hello.cpp"], {})
    spawned = _spawned(True)
    spawned._processor.errors = 1
    spawned._buffered.append("bad.cpp: error\n")
    spawned.finish(1)
    out = capsys.readouterr().out
    assert out.startswith( "g++ -c hello.cpp\n" )
    assert "bad.cpp: error" in out
    assert out.rstrip().endswith( "[error] compile · hello.cpp" )
    assert "[ok]" not in out


class _Node:
    def __init__( self, path, origin=None ):
        self.path = path
        self._origin = origin

    def srcnode( self ):
        return self if self._origin is None else self._origin


def test_compile_shows_the_source_tree_not_the_variant_working_copy( tmp_path ):
    source = tmp_path / "test" / "positions" / "deposit_and_withdrawal_simulator.cpp"
    source.parent.mkdir( parents=True )
    source.write_text( "int main() { return 0; }\n" )
    env = _variant_env()
    env["base_path"] = str( tmp_path )
    env["sconscript_file"] = "./test/positions/sconscript"
    env["tool_variant_dir"] = "gcc16/dbg/x86_64/cxx2c"
    mirrored = (
            "_build/test/positions/gcc16/dbg/x86_64/cxx2c/working/"
            "deposit_and_withdrawal_simulator.cpp"
    )
    expected = (
            "[ok] test/positions · gcc16_dbg_x86_64_cxx2c · compile · "
            "test/positions/deposit_and_withdrawal_simulator.cpp"
    )
    line = progress.format_terse_success(
            "g++ -c " + mirrored,
            ["deposit_and_withdrawal_simulator.o"],
            [mirrored],
            env,
    )
    assert line == expected

    origin = _Node( "test/positions/deposit_and_withdrawal_simulator.cpp" )
    via_srcnode = progress.format_terse_success(
            "g++ -c " + mirrored,
            ["deposit_and_withdrawal_simulator.o"],
            [_Node( mirrored, origin )],
            env,
    )
    assert via_srcnode == expected

    missing = progress.format_terse_success(
            "g++ -c generated.cpp",
            ["generated.o"],
            ["_build/test/positions/gcc16/dbg/x86_64/cxx2c/working/generated.cpp"],
            env,
    )
    assert "_build/test/positions/" in missing
    assert "· compile ·" in missing


def test_compile_outside_the_project_is_home_relative_not_a_dotdot_climb( monkeypatch, tmp_path ):
    home = tmp_path / "home"
    project = home / "coding" / "order_matcher"
    monkeypatch.setattr(
            os.path, "expanduser",
            lambda path: str( home ) if path == "~" else os.path.expanduser( path ),
    )
    env = _variant_env()
    env["base_path"] = str( project )
    download = (
            home / "_cuppa" / "_download"
            / "git_https_github.com__j0nnyw_quince.git@master"
            / "src" / "mappers" / "tuple_mapper.cpp"
    )
    line = progress.format_terse_success(
            "g++ -c " + str( download ),
            ["tuple_mapper.o"],
            [str( download )],
            env,
    )
    assert (
            "· compile · ~/_cuppa/_download/"
            "git_https_github.com__j0nnyw_quince.git@master/src/mappers/tuple_mapper.cpp"
    ) in line
    assert "../" not in line

    climbed = progress.format_terse_success(
            "g++ -c cell.cpp",
            ["cell.o"],
            ["../../_cuppa/_download/src/cell.cpp"],
            env,
    )
    assert "· compile · ~/_cuppa/_download/src/cell.cpp" in climbed
    assert "../" not in climbed


def test_status_line_colours_the_sconscript_leaf_and_leaves_the_variant_token_plain( monkeypatch ):
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    monkeypatch.setattr( progress, "as_info", lambda text: "<i>" + text + "</i>" )
    monkeypatch.setattr( progress, "as_emphasised", lambda text: "<e>" + text + "</e>" )
    monkeypatch.setattr( progress, "as_colour", lambda meaning, text: text )
    line = progress.format_terse_success(
            "g++ -c test/orders/src/hello.cpp",
            ["hello.o"],
            ["test/orders/src/hello.cpp"],
            _variant_env(),
    )
    assert line == (
            "[ok] <s>test/</s><i>orders</i> <s>·</s> <s>gcc16_</s>dbg<s>_x86_64_cxx2c</s> "
            "<s>·</s> compile <s>·</s> <s>test/orders/src/</s><e>hello.cpp</e>"
    )

    env = _variant_env()
    env["sconscript_file"] = "./order_matcher/sconscript"
    leaf_only = progress.format_terse_success(
            "g++ -c order_matcher/main.cpp",
            ["main.o"],
            ["order_matcher/main.cpp"],
            env,
    )
    assert leaf_only.startswith( "[ok] <i>order_matcher</i> " )


def test_spawn_without_terse_returns_lines_for_immediate_printing(capsys):
    spawned = _spawned(False)
    assert spawned("hello from the tool") == "hello from the tool"
    spawned.finish(0)
    assert capsys.readouterr().out == ""
