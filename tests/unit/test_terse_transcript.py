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


@pytest.fixture( autouse=True )
def _reset_progress_ledger():
    progress.reset_progress_ledger()
    progress.reset_build_interrupted()
    progress.take_terse_status_emitted()
    yield
    progress.reset_progress_ledger()
    progress.reset_build_interrupted()
    progress.take_terse_status_emitted()


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


def test_common_statuses_share_a_column_and_error_runs_past_it():
    env = _variant_env()
    ok = progress.format_terse_line( "ok", "g++ -c a.cpp", [ "a.o" ], [ "a.cpp" ], env )
    warned = progress.format_terse_line( "warn", "g++ -c a.cpp", [ "a.o" ], [ "a.cpp" ], env )
    error = progress.format_terse_line( "error", "g++ -c a.cpp", [ "a.o" ], [ "a.cpp" ], env )
    passed = progress.format_terse_result_line( "pass", env, "test", "binary" )
    failed = progress.format_terse_result_line( "fail", env, "test", "binary" )
    skipped = progress.format_terse_result_line( "skip", env, "test", "test-case" )
    xfail = progress.format_terse_result_line( "xfail", env, "test", "binary" )
    assert ok.index( "test/" ) == warned.index( "test/" ) == passed.index( "test/" )
    assert failed.index( "test/" ) == skipped.index( "test/" ) == ok.index( "test/" )
    assert error.index( "test/" ) == xfail.index( "test/" ) == ok.index( "test/" ) + 1


def test_success_line_names_sconscript_variant_action_and_source():
    assert progress.terse_counts_prefix() == ""
    line = progress.format_terse_success(
            "g++ -c test/orders/src/hello.cpp",
            ["_build/hello.o"],
            ["test/orders/src/hello.cpp"],
            _variant_env(),
    )
    assert line == "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile · test/orders/src/hello.cpp"


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


def test_scons_builders_are_named_and_tar_is_not_a_compile():
    assert progress.spell_terse_action( "tar -c -f pkg.tar a.txt", [ "pkg.tar" ] ) == "tar"
    assert progress.spell_terse_action( "/usr/bin/gtar -c -f pkg.tar a.txt", [ "pkg.tar" ] ) == "tar"
    assert progress.spell_terse_action( 'zip_builder(["pkg.zip"], ["a.txt"])', [ "pkg.zip" ] ) == "zip"
    assert progress.spell_terse_action( "Creating 'note.txt'", [ "note.txt" ] ) == "text"
    assert progress.spell_terse_action( 'Copy file(s): "a.txt" to "b.txt"', [ "b.txt" ] ) == "copy"
    assert progress.spell_terse_action( "cd /tmp && m4 -E < in.m4 > out", [ "out" ] ) == "m4"
    assert progress.spell_terse_action( "jar cf a.jar a.txt", [ "a.jar" ] ) == "jar"
    assert progress.spell_terse_action( "javac -d classes A.java", [ "A.class" ] ) == "javac"
    assert progress.spell_terse_action( "cd src && rpcgen -c -o out.c in.x", [ "out.c" ] ) == "rpcgen"
    assert progress.spell_terse_action( "LC_ALL=C rpmbuild -ta pkg.spec", [ "pkg.rpm" ] ) == "rpm"
    assert progress.spell_terse_action( "flex -t in.l > out.c", [ "out.c" ] ) == "lex"
    assert progress.spell_terse_action( "bison -o out.c in.y", [ "out.c" ] ) == "yacc"
    assert progress.spell_terse_action(
            "cd doc && pdflatex -interaction=nonstopmode guide.tex", [ "guide.pdf" ],
    ) == "pdflatex"
    assert progress.spell_terse_action( "g++ -c hello.cpp", [ "hello.o" ] ) == "compile"


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
            "[ok]   reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
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
            "[ok]   reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
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
            "[ok]   reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
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
            "[ok]   reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
            "<artifacts>/platform_guide.html → "
            "_artifacts/documentation/platform_guide/platform_guide.html"
    )


def test_a_nested_report_artifact_uses_the_variant_token():
    env = _layout_env()
    variant = env.pop( "_variant" )
    env["flat_tool_variant_dir_offset"] = "gcc16_dbg_x86_64_cxx2c/test/cycle_events"
    report = progress.format_terse_line(
            "ok",
            'Copy("dest", "src")',
            [ "/proj/_artifacts/test/gcc16_dbg_x86_64_cxx2c/test/cycle_events/cycle_ended.report.html" ],
            [ variant + "/final/cycle_ended.report.html" ],
            env,
    )
    assert report == (
            "[ok]   reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
            "<final>/cycle_ended.report.html → <artifacts>/cycle_ended.report.html"
    )
    elsewhere = progress.format_terse_line(
            "ok",
            'Copy("dest", "src")',
            [ "/proj/_artifacts/documentation/platform_guide/platform_guide.html" ],
            [ variant + "/final/platform_guide.html" ],
            env,
    )
    assert "_artifacts/documentation/platform_guide/platform_guide.html" in elsewhere
    assert "<artifacts>" not in elsewhere.split( "→", 1 )[1]


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
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile-scss · theme.scss"
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
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · copy · "
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
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · asciidoc · accounts.adoc"
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


def test_a_failed_test_names_the_program_and_hides_the_action_dump( capsys ):
    log = _LabelledNode( "test", "trading_limit_consumed.stdout.log" )
    env = _terse_env()
    progress.stash_terse_command(
            'RunBoostTest(["trading_limit_consumed.stdout.log"], ["trading_limit_consumed"])',
            [ log ],
            [ "trading_limit_consumed" ],
            env,
    )
    progress._report_python_action( [ log ], [ "trading_limit_consumed" ], env, failed=True )
    out = capsys.readouterr().out
    assert "RunBoostTest" not in out
    assert "stdout.log" not in out
    assert out.rstrip().endswith(
            "[error] test/orders · gcc16_dbg_x86_64_cxx2c · test · trading_limit_consumed"
    )


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
    assert ok == ["[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile · test/orders/hello.cpp"]

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
    assert out.strip() == "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile · test/orders/hello.cpp"
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
            "[ok]   test/positions · gcc16_dbg_x86_64_cxx2c · compile · "
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
            "[ok]   <s>test/</s><i>orders</i> <s>·</s> <s>gcc16_</s>dbg<s>_x86_64_cxx2c</s> "
            "<s>·</s> compile <s>·</s> <s>test/orders/src/</s><e><i>hello.cpp</i></e>"
    )

    env = _variant_env()
    env["sconscript_file"] = "./order_matcher/sconscript"
    leaf_only = progress.format_terse_success(
            "g++ -c order_matcher/main.cpp",
            ["main.o"],
            ["order_matcher/main.cpp"],
            env,
    )
    assert leaf_only.startswith( "[ok]   <i>order_matcher</i> " )


def test_ctrl_c_is_one_interrupted_line_not_a_job_list(capsys):
    progress.reset_build_interrupted()
    stream = progress._TerseInterruptStream( sys.stderr )
    stream.write( "scons: *** [_build/test/market_data/working/time.o] Error -2\n" )
    stream.write( "scons: *** [_build/test/market_data/working/protocol.o] Error -2\n" )
    stream.write( "scons: Build interrupted.\n" )
    stream.write( "scons: building terminated because of errors.\n" )
    stream.write( "scons: *** [_build/test/market_data/working/time.o] Error 1\n" )
    captured = capsys.readouterr()
    err = captured.err
    assert err.count( "interrupted" ) == 1
    assert "\ninterrupted — finishing in-flight actions...\n" in err
    assert captured.out == "finished in-flight actions\n[interrupted]\n"
    assert "Error -2" not in err
    assert "Build interrupted" not in err
    assert "building terminated because of errors" not in err
    assert "Error 1" in err

    draining = progress.format_terse_line(
            "ok", "g++ -c account_rule.cpp", [ "account_rule.o" ], [ "account_rule.cpp" ], _variant_env(),
    )
    assert draining.startswith( "... [ok]   " )
    progress.note_build_aborted()
    progress.note_build_aborted()
    stopped = progress.format_terse_line(
            "ok", "g++ -c account_rule.cpp", [ "account_rule.o" ], [ "account_rule.cpp" ], _variant_env(),
    )
    assert stopped.startswith( "[ok]   " )
    assert capsys.readouterr().err == "\naborted\n"

    spawned = _spawned( True )
    progress.stash_terse_command( "g++ -c time.cpp", [ "time.o" ], [ "time.cpp" ], _variant_env() )
    spawned.finish( -2 )
    again = capsys.readouterr()
    assert again.out == ""
    assert "interrupted" not in again.err
    assert "[error]" not in again.err


def test_spawn_without_terse_returns_lines_for_immediate_printing(capsys):
    spawned = _spawned(False)
    assert spawned("hello from the tool") == "hello from the tool"
    spawned.finish(0)
    assert capsys.readouterr().out == ""


def test_a_test_line_puts_the_duration_between_the_action_and_the_name( monkeypatch ):
    highlighted = []

    def _highlight( meaning, text ):
        highlighted.append( ( meaning, text ) )
        return text

    monkeypatch.setattr( progress, "as_badge", _highlight )
    line = progress.format_terse_result_line(
            "pass",
            _variant_env(),
            "test",
            "buy_sell_ladder",
            duration="207 ms",
            detail="11/12, 1 failed",
    )
    assert line == (
            "[pass] test/orders · gcc16_dbg_x86_64_cxx2c · test · 207 ms · "
            "buy_sell_ladder — 11/12, 1 failed"
    )
    assert highlighted == [ ( "success", "[pass]" ) ]
    assert progress.format_terse_result_line( "fail", _variant_env(), "test", "buy_sell_ladder" ).startswith( "[fail] " )
    assert progress.format_terse_result_line( "skip", _variant_env(), "test", "buy_sell_ladder" ).startswith( "[skip] " )
    assert progress.format_terse_result_line( "xfail", _variant_env(), "test", "buy_sell_ladder" ).startswith( "[xfail] " )
    assert progress.format_terse_result_line( "xpass", _variant_env(), "test", "buy_sell_ladder" ).startswith( "[xpass] " )
    assert highlighted == [
            ( "success", "[pass]" ),
            ( "error", "[fail]" ),
            ( "skipped", "[skip]" ),
            ( "expected_failure", "[xfail]" ),
            ( "unexpected_success", "[xpass]" ),
    ]
    case = progress.format_terse_result_line( "fail", _variant_env(), "test-case", "buy_sell_ladder/one" )
    assert case.startswith( "→ [fail] " )
    assert highlighted[-1] == ( "unexpected_success", "[xpass]" )
    assert progress.format_terse_duration( 4_000_000 ) == "4 ms"
    assert progress.format_terse_duration( 1_200_000_000 ) == "1.2 s"
    assert progress.format_terse_duration( 12_000_000_000 ) == "12 s"


def test_failing_cases_are_shown_and_passing_cases_wait_for_the_flag( capsys ):
    from cuppa.cpp.terse_test_report import show_case, write_case, rollup_detail

    env = _variant_env()
    env["terse_output"] = True
    assert show_case( "failed", env )
    assert not show_case( "passed", env )
    env["show_test_cases"] = True
    assert show_case( "passed", env )

    env["show_test_cases"] = False
    write_case(
            env,
            "buy_sell_ladder",
            {
                "name": "rejects_a_cross",
                "status": "failed",
                "passed": 1,
                "total": 3,
                "terse_lines": [ "check failed" ],
            },
            18_000_000,
    )
    out = capsys.readouterr().out
    assert out == (
            "check failed\n"
            "→ [fail] test/orders · gcc16_dbg_x86_64_cxx2c · test-case · 18 ms · "
            "buy_sell_ladder/rejects_a_cross — 1/3 assertions\n"
    )
    assert rollup_detail( 11, 1, 1, 0, 1, 12, assertions=( 40, 52 ) ) == (
            "11/12 cases, 40/52 assertions, 1 failed, 1 skipped, 1 xfailed"
    )
    assert rollup_detail( 0, 0, 0, 0, 0, 0, assertions=( 0, 0 ), cases=False ) == "no assertions"


class _ExecuteEnv( dict ):
    """Stand-in that records an ``Execute`` the way SCons prints it."""

    def Execute( self, action ):
        progress.terse_print_cmd_line( action, [], [], self )
        return 0


def test_an_executed_copy_is_a_transfer_line_and_hides_the_caller( capsys ):
    env = _layout_env()
    env["terse_output"] = True
    variant = env.pop( "_variant" )
    caller = _ExecuteEnv( env )
    progress.enable_terse_python_actions( caller )
    dest = "/proj/_artifacts/reference_guide_gcc16_dbg_x86_64_cxx2c/protocol.report.html"
    src = variant + "/final/protocol.report.html"
    progress.stash_terse_command(
            'CollateReportIndexAction(["protocol.report.html"], ["protocol.report.html"])',
            [ dest ],
            [ src ],
            caller,
    )
    caller.Execute( 'Copy("{}", "{}")'.format( dest, src ) )
    assert capsys.readouterr().out == (
            "→ [ok]   reference_guide · gcc16_dbg_x86_64_cxx2c · copy · "
            "<final>/protocol.report.html → <artifacts>/protocol.report.html\n"
    )
    assert progress.take_terse_status_emitted()
    assert progress.take_terse_command()[0] is None


def test_an_executed_delete_mkdir_or_chmod_is_a_nested_path_line( capsys ):
    env = _variant_env()
    progress._present_executed_command( 'Delete("foo.o")', [], [], env, False )
    progress._present_executed_command( 'Mkdir("include")', [], [], env, False )
    progress._present_executed_command( 'Chmod("script.sh", 0o755)', [], [], env, False )
    out = capsys.readouterr().out
    assert "Delete(" not in out
    assert "Mkdir(" not in out
    assert "Chmod(" not in out
    assert " · delete · foo.o\n" in out
    assert " · mkdir · include\n" in out
    assert " · chmod · script.sh\n" in out
    assert out.count( "→ [ok]   " ) == 3


def test_an_unknown_execute_is_run_and_hides_a_clean_command( capsys ):
    env = _variant_env()
    progress._present_executed_command( "rm -rf build", [], [], env, False )
    clean = capsys.readouterr().out
    assert clean.startswith( "→ [ok]   " )
    assert " · run\n" in clean
    assert "rm -rf" not in clean
    progress._present_executed_command( "rm -rf build", [], [], env, True )
    failed = capsys.readouterr().out
    assert failed.startswith( "rm -rf build\n" )
    assert " · run\n" in failed
    assert "[error]" in failed


def test_an_executed_touch_stays_hidden_behind_the_caller( capsys ):
    env = _ExecuteEnv( terse_output=True )
    progress.enable_terse_python_actions( env )
    progress.stash_terse_command( "package archive", [ "pkg.tgz" ], [], env )
    env.Execute( 'Touch("pkg.tgz")' )
    assert capsys.readouterr().out == ""
    assert not progress.take_terse_status_emitted()
    assert progress.take_terse_command()[0] == "package archive"


def test_executed_copies_replace_the_python_action_line( capsys ):
    dest = "/proj/_artifacts/reference_guide_gcc16_dbg_x86_64_cxx2c/protocol.report.html"
    src_root = "/proj/_build/reference_guide/gcc16/dbg/x86_64/cxx2c/final"

    def _action( target, source, env ):
        env.Execute( 'Copy("{}/protocol.report.html", "{}/protocol.report.html")'.format(
                os.path.dirname( dest ), src_root,
        ) )
        env.Execute( 'Copy("{}/protocol.report-summary.json", "{}/protocol.report-summary.json")'.format(
                os.path.dirname( dest ), src_root,
        ) )
        return None

    env = _layout_env()
    env["terse_output"] = True
    env.pop( "_variant" )
    caller = _ExecuteEnv( env )
    progress.enable_terse_python_actions( caller )
    progress.stash_terse_command( "CollateReportIndexAction([], [])", [ dest ], [], caller )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[ dest ], source=[], env=caller ) is None
    out = capsys.readouterr().out
    assert "CollateReportIndexAction" not in out
    assert out.count( "→ [ok]   " ) == 2
    assert "protocol.report.html" in out
    assert "protocol.report-summary.json" in out
    assert " · run · " not in out


def test_the_case_leaf_is_coloured_and_the_counts_stay_plain( monkeypatch ):
    from cuppa.cpp import terse_test_report

    monkeypatch.setattr( terse_test_report, "as_colour", lambda meaning, text: "<{}>{}</>".format( meaning, text ) )
    monkeypatch.setattr( terse_test_report, "as_badge", lambda meaning, text: "<badge:{}>{}</>".format( meaning, text ) )
    monkeypatch.setattr( terse_test_report, "as_notice", lambda text: "<notice>" + text + "</notice>" )
    monkeypatch.setattr( terse_test_report, "as_emphasised", lambda text: "<b>" + text + "</b>" )
    monkeypatch.setattr( terse_test_report, "as_subdued", lambda text: "<s>" + text + "</s>" )
    assert terse_test_report.colour_test_name( "pass", "protocol/test_endpoint", case=True ) == (
            "protocol/<success>test_endpoint</>"
    )
    assert terse_test_report.colour_test_name( "fail", "protocol" ) == "<badge:error>protocol</>"
    assert terse_test_report.colour_test_name( "pass", "authentication_type" ) == "<badge:success>authentication_type</>"
    assert "cases" not in terse_test_report.assertion_clause( 6, 6 )
    assert terse_test_report.assertion_clause( 6, 6 ) == "6/6 assertions"
    assert terse_test_report.assertion_clause( 0, 0 ) == "<b><notice>no assertions</notice></b>"
    assert terse_test_report.assertion_clause( 0, 0, label=True ) == "<badge:notice>no assertions</>"
    assert "1 failed" in terse_test_report.rollup_detail( 11, 1, 1, 0, 0, 12, assertions=( 40, 52 ) )


def test_a_reported_test_line_replaces_the_generic_status( capsys ):
    def _action( target, source, env ):
        progress.note_terse_status_emitted()
        sys.stdout.write( "[pass] already reported\n" )
        return None

    env = _terse_env()
    progress.stash_terse_command( "running buy_sell_ladder", [], [], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[], source=[], env=env ) is None
    assert capsys.readouterr().out == "[pass] already reported\n"


class _Slots:
    def __init__( self, count ):
        self._actions = [ object() for _ in range( count ) ]

    def get_action_list( self ):
        return self._actions


class _ActionNode:
    def __init__( self, slots=1, children=None, executor=None ):
        self.executor = executor or _Slots( slots )
        self.kids = list( children or [] )
        self.state = 0

    def has_builder( self ):
        return True

    def get_executor( self ):
        return self.executor

    def children( self, scan=True ):
        return list( self.kids )

    def get_state( self ):
        return self.state


def _compile_line( env, node, source ):
    return progress.format_terse_line(
            "ok", "g++ -c " + source, [ node ], [ source ], env,
    )


def test_an_action_line_leads_with_the_cell_tally_and_overall_percent():
    env = _terse_env()
    first = _ActionNode()
    second = _ActionNode()
    progress.register_terse_actions( env, [ first, second ] )
    assert _compile_line( env, first, "hello.cpp" ).startswith( "  1/  2 · 50% [ok]   " )
    assert _compile_line( env, second, "main.cpp" ).startswith( "  2/  2 · 100% [ok]   " )


def test_archive_and_index_are_two_slots_on_one_library():
    env = _terse_env()
    library = _ActionNode( slots=2 )
    progress.register_terse_actions( env, [ library ] )
    assert _compile_line( env, library, "a.o" ).startswith( "  1/  2 · 50% [ok]   " )
    assert _compile_line( env, library, "a.o" ).startswith( "  2/  2 · 100% [ok]   " )


def test_targets_that_share_an_executor_count_once():
    env = _terse_env()
    executor = _Slots( 1 )
    stdout = _ActionNode( executor=executor )
    report = _ActionNode( executor=executor )
    progress.register_terse_actions( env, [ stdout, report ] )
    assert _compile_line( env, stdout, "buy_sell_ladder" ).startswith( "  1/  1 · 100% [ok]   " )


def test_another_sconscript_changes_the_percent_not_the_cell_fraction():
    orders = _terse_env()
    positions = _terse_env()
    positions[ "sconscript_file" ] = "./test/positions/sconscript"
    orders_node = _ActionNode()
    positions_node = _ActionNode()
    progress.register_terse_actions( orders, [ orders_node ] )
    progress.register_terse_actions( positions, [ positions_node ] )
    assert _compile_line( orders, orders_node, "hello.cpp" ).startswith( "  1/  1 · 50% [ok]   " )
    assert _compile_line( positions, positions_node, "book.cpp" ).startswith( "  1/  1 · 100% [ok]   " )


def test_an_up_to_date_action_is_already_done():
    env = _terse_env()
    skipped = _ActionNode()
    waiting = _ActionNode()
    progress.register_terse_actions( env, [ skipped, waiting ] )
    progress.note_up_to_date_action( skipped )
    assert progress.terse_counts_prefix( env ) == "  1/  2 · 50%"
    assert _compile_line( env, waiting, "hello.cpp" ).startswith( "  2/  2 · 100% [ok]   " )


def test_actions_outside_the_requested_targets_are_not_in_the_total():
    env = _terse_env()
    child = _ActionNode()
    root = _ActionNode( children=[ child ] )
    other = _ActionNode()
    progress.register_terse_actions( env, [ root, child, other ] )
    progress.narrow_progress_ledger( [ root ] )
    assert _compile_line( env, child, "hello.cpp" ).startswith( "  1/  2 · 50% [ok]   " )
    assert _compile_line( env, root, "app" ).startswith( "  2/  2 · 100% [ok]   " )


def test_a_test_case_is_marked_and_does_not_move_the_tally():
    env = _terse_env()
    binary = _ActionNode()
    progress.register_terse_actions( env, [ binary ] )
    progress.remember_terse_action_target( [ binary ] )
    case = progress.format_terse_result_line(
            "pass", env, "test-case", "position_source_id/test_position_source_id",
            duration="0 ms", detail="8/8 assertions",
    )
    plain = "  0/  1 ·  0%"
    assert progress.terse_counts_prefix( env ) == plain
    assert case.startswith( ( " " * ( len( plain ) - 1 ) ) + "→ [pass] " )
    assert "·" not in case.split( "[pass]", 1 )[ 0 ]
    rollup = progress.format_terse_result_line(
            "pass", env, "test", "position_source_id",
            duration="1 ms", detail="2/2 cases, 9/9 assertions",
    )
    assert rollup.startswith( "  1/  1 · 100% [pass] " )
    assert "→" not in rollup


def test_nested_copies_do_not_move_the_tally_and_the_caller_does( capsys ):
    parent = _ActionNode()
    nxt = _ActionNode()
    env = _layout_env()
    env[ "terse_output" ] = True
    env.pop( "_variant" )
    progress.register_terse_actions( env, [ parent, nxt ] )

    def _action( target, source, env ):
        env.Execute( 'Copy("dest/a", "src/a")' )
        env.Execute( 'Copy("dest/b", "src/b")' )
        return None

    caller = _ExecuteEnv( env )
    progress.enable_terse_python_actions( caller )
    progress.stash_terse_command( "CollateReportIndexAction([], [])", [ parent ], [], caller )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[ parent ], source=[], env=caller ) is None
    out = capsys.readouterr().out
    assert out.count( "→ [ok]   " ) == 2
    assert "%" not in out
    assert _compile_line( env, nxt, "hello.cpp" ).startswith( "  2/  2 · 100% [ok]   " )


def test_make_ready_counts_an_up_to_date_node():
    import SCons.Node

    env = _terse_env()
    skipped = _ActionNode()
    skipped.state = SCons.Node.up_to_date
    waiting = _ActionNode()
    progress.register_terse_actions( env, [ skipped, waiting ] )
    progress._credit_up_to_date_targets( [ skipped ] )
    assert progress.terse_counts_prefix( env ) == "  1/  2 · 50%"


def test_the_tally_reserves_three_digits_and_the_arrow_keeps_the_status_column():
    endpoint_env = _terse_env()
    endpoint = [ _ActionNode() for _ in range( 182 ) ]
    progress.register_terse_actions( endpoint_env, endpoint )
    for node in endpoint[ :18 ]:
        progress.note_up_to_date_action( node )
    counted = _compile_line( endpoint_env, endpoint[ 18 ], "decommission_endpoint.cpp" )
    assert counted.startswith( " 19/182 · 10% [ok]   " )

    ethereum_env = _terse_env()
    ethereum_env[ "sconscript_file" ] = "./test/ethereum/sconscript"
    ethereum = [ _ActionNode() for _ in range( 56 ) ]
    progress.register_terse_actions( ethereum_env, ethereum )
    for node in ethereum[ :24 ]:
        progress.note_up_to_date_action( node )
    other = _compile_line( ethereum_env, ethereum[ 24 ], "encoded_transaction_data.cpp" )
    assert other.startswith( " 25/ 56 · " )
    assert other.index( "[ok]" ) == counted.index( "[ok]" )

    progress.remember_terse_action_target( [ endpoint[ 19 ] ] )
    case = progress.format_terse_result_line(
            "pass", endpoint_env, "test-case", "decommission_endpoint/test_id",
            duration="0 ms", detail="2/2 assertions",
    )
    assert case.index( "[pass]" ) == counted.index( "[ok]" )
    assert case[ : case.index( "[pass]" ) ].endswith( "→ " )

    progress.reset_progress_ledger()
    wide_env = _terse_env()
    wide_env[ "sconscript_file" ] = "./test/wide/sconscript"
    wide = _ActionNode( slots=1000 )
    progress.register_terse_actions( wide_env, [ wide ] )
    assert _compile_line( wide_env, wide, "a.cpp" ).startswith( "   1/1000 · " )


def test_the_cell_tally_is_subdued_and_the_percentage_is_plain( monkeypatch ):
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<subdued>{}</subdued>".format( text ) )
    assert progress._colour_counts_prefix( " 19/182 · 10%" ) == (
            "<subdued> 19/182 · </subdued>10%"
    )


def test_progress_hook_installs_once_and_can_be_removed():
    import SCons.Script.Main as main

    original = main.BuildTask.make_ready
    try:
        progress.install_terse_progress_hooks()
        wrapped = main.BuildTask.make_ready
        progress.install_terse_progress_hooks()
        assert main.BuildTask.make_ready is wrapped
        assert getattr( wrapped, "_cuppa_terse_ledger", False )
        assert wrapped is not original
    finally:
        main.BuildTask.make_ready = original
