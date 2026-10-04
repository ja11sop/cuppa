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
    progress.take_terse_launch()
    yield
    progress.reset_progress_ledger()
    progress.reset_build_interrupted()
    progress.take_terse_status_emitted()
    progress.take_terse_launch()


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


def test_a_progress_description_is_not_printed(capsys):
    progress.terse_print_cmd_line("Progress( Begin )", [], [], {})
    assert capsys.readouterr().out == ""
    assert progress.take_terse_command()[0] is None


def test_a_command_that_never_spawns_is_reprinted_before_the_next_line(capsys):
    progress.terse_print_cmd_line("Removing empty directories", ["stamp"], [], {})
    assert capsys.readouterr().out == ""
    progress.terse_print_cmd_line("Progress( End )", [], [], {})
    assert capsys.readouterr().out == "Removing empty directories\n"
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
    done = progress.format_terse_line( "done", "cmake --build x", [ "stamp" ], [], env )
    warned = progress.format_terse_line( "warn", "g++ -c a.cpp", [ "a.o" ], [ "a.cpp" ], env )
    error = progress.format_terse_line( "error", "g++ -c a.cpp", [ "a.o" ], [ "a.cpp" ], env )
    passed = progress.format_terse_result_line( "pass", env, "test", "binary" )
    failed = progress.format_terse_result_line( "fail", env, "test", "binary" )
    skipped = progress.format_terse_result_line( "skip", env, "test", "test-case" )
    xfail = progress.format_terse_result_line( "xfail", env, "test", "binary" )
    assert ok.index( "test/" ) == warned.index( "test/" ) == passed.index( "test/" )
    assert done.index( "test/" ) == ok.index( "test/" )
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
    assert line == (
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile · "
            "test/orders/src/hello.cpp → _build/hello.o"
    )


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
    assert progress.spell_terse_action(
            "cp -f build/libboost_corosio.a working/libboost_corosio.a",
            ["working/libboost_corosio.a"],
    ) == "copy"
    assert progress.spell_terse_action(
            "ar rc libquince.a a.o",
            ["libquince.a"],
    ) == "archive"
    assert progress.format_terse_line(
            "error", "g++ -o buy_sell_ladder buy_sell_ladder.o", ["buy_sell_ladder"], ["buy_sell_ladder.o"], env,
    ) == "[error] test/orders · gcc16_dbg_x86_64_cxx2c · link · buy_sell_ladder"


def test_staging_cp_of_a_static_library_is_copy_with_transfer_field():
    env = _layout_env()
    env.pop( "_variant" )
    line = progress.format_terse_line(
            "ok",
            "cp -f build/libboost_corosio.a working/libboost_corosio.a",
            [ env["abs_build_dir"] + "/libboost_corosio.a" ],
            [ "/proj/_build/reference_guide/gcc16/dbg/x86_64/cxx2c/cmake-build/libboost_corosio.a" ],
            env,
    )
    assert "· copy ·" in line
    assert "→" in line
    assert "libboost_corosio.a" in line
    assert "· archive ·" not in line


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
            "<final>/reference_guide.html → <artefacts>/reference_guide.html"
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
            "<artefacts>/platform_guide.html → "
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
            "<final>/cycle_ended.report.html → <artefacts>/cycle_ended.report.html"
    )
    elsewhere = progress.format_terse_line(
            "ok",
            'Copy("dest", "src")',
            [ "/proj/_artifacts/documentation/platform_guide/platform_guide.html" ],
            [ variant + "/final/platform_guide.html" ],
            env,
    )
    assert "_artifacts/documentation/platform_guide/platform_guide.html" in elsewhere
    assert "<artefacts>" not in elsewhere.split( "→", 1 )[1]


def test_copy_colours_the_destination_leaf_and_mutes_the_source( monkeypatch ):
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    monkeypatch.setattr( progress, "as_info", lambda text: "<i>" + text + "</i>" )
    monkeypatch.setattr( progress, "as_emphasised", lambda text: "<e>" + text + "</e>" )
    monkeypatch.setattr( progress, "as_emphasised_plain", lambda text: "<e>" + text + "</e>" )
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
    assert "<s><final>/scss/cplx.css</s> <s>→</s> <s><artefacts>/</s><e><i>cplx.css</i></e>" in line


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


def test_markdown_and_asciidoc_show_source_to_product():
    markdown = progress.format_terse_line(
            "ok",
            "markdown",
            [ _LabelledNode( "markdown", "intro.html" ) ],
            [ "user_guides/intro.md" ],
            _variant_env(),
    )
    assert markdown.endswith( "· markdown · user_guides/intro.md → intro.html" )


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
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile-scss · "
            "theme.scss → theme.css"
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
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · asciidoc · "
            "accounts.adoc → accounts_template.asciidoc"
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
            "[warn] test/orders · gcc16_dbg_x86_64_cxx2c · asciidoc · "
            "accounts.adoc → accounts_template.asciidoc"
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
            "[error] test/orders · gcc16_dbg_x86_64_cxx2c · asciidoc · "
            "accounts.adoc → accounts_template.asciidoc"
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
            "[error] test/orders · gcc16_dbg_x86_64_cxx2c · compile-scss · "
            "theme.scss → theme.css"
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
    assert ok == [
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile · "
            "test/orders/hello.cpp → hello.o"
    ]

    warned = progress.render_terse_spawn(
            0, 0, 1, ["warn line\n"], "g++ -c test/orders/hello.cpp", ["hello.o"], source, env,
            " === Warnings 1 === ",
    )
    assert warned[0] == "g++ -c test/orders/hello.cpp"
    assert warned[-1] == (
            "[warn] test/orders · gcc16_dbg_x86_64_cxx2c · compile · "
            "test/orders/hello.cpp → hello.o"
    )
    assert "warn line" in warned
    assert "[ok]" not in "\n".join(warned)


def test_failed_run_prints_the_command_before_the_error_summary():
    failed = progress.render_terse_spawn(
            1, 1, 0, ["bad\n"], "g++ -c hello.cpp", ["hello.o"], ["hello.cpp"], {}, "summary\n",
    )
    assert failed[0] == "g++ -c hello.cpp"
    assert "bad" in failed
    assert "summary" in failed
    assert failed[-1] == "[error] compile · hello.cpp → hello.o"


def test_spawn_folds_a_clean_run_and_discards_the_stash(capsys):
    progress.stash_terse_command(
            "g++ -c test/orders/hello.cpp", ["hello.o"], ["test/orders/hello.cpp"], _variant_env(),
    )
    spawned = _spawned(True)
    assert spawned("noise the compiler wrote") is None
    spawned.finish(0)
    out = capsys.readouterr().out
    assert out.strip() == (
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · compile · "
            "test/orders/hello.cpp → hello.o"
    )
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
    assert out.rstrip().endswith( "[error] compile · hello.cpp → hello.o" )
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
    env["abs_build_dir"] = str(
            tmp_path / "_build" / "test" / "positions" / "gcc16" / "dbg" / "x86_64" / "cxx2c" / "working"
    )
    object_path = os.path.join( env["abs_build_dir"], "deposit_and_withdrawal_simulator.o" )
    expected = (
            "[ok]   test/positions · gcc16_dbg_x86_64_cxx2c · compile · "
            "test/positions/deposit_and_withdrawal_simulator.cpp → "
            "<working>/deposit_and_withdrawal_simulator.o"
    )
    line = progress.format_terse_success(
            "g++ -c " + mirrored,
            [object_path],
            [mirrored],
            env,
    )
    assert line == expected

    origin = _Node( "test/positions/deposit_and_withdrawal_simulator.cpp" )
    via_srcnode = progress.format_terse_success(
            "g++ -c " + mirrored,
            [object_path],
            [_Node( mirrored, origin )],
            env,
    )
    assert via_srcnode == expected

    missing = progress.format_terse_success(
            "g++ -c generated.cpp",
            [os.path.join( env["abs_build_dir"], "generated.o" )],
            ["_build/test/positions/gcc16/dbg/x86_64/cxx2c/working/generated.cpp"],
            env,
    )
    assert "_build/test/positions/" in missing
    assert "→ <working>/generated.o" in missing
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
            " → tuple_mapper.o"
    ) in line
    assert "../" not in line

    climbed = progress.format_terse_success(
            "g++ -c cell.cpp",
            ["cell.o"],
            ["../../_cuppa/_download/src/cell.cpp"],
            env,
    )
    assert "· compile · ~/_cuppa/_download/src/cell.cpp → cell.o" in climbed
    assert "../" not in climbed


def test_status_line_colours_the_sconscript_leaf_and_leaves_the_variant_token_plain( monkeypatch ):
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    monkeypatch.setattr( progress, "as_info", lambda text: "<i>" + text + "</i>" )
    monkeypatch.setattr( progress, "as_emphasised", lambda text: "<e>" + text + "</e>" )
    monkeypatch.setattr( progress, "as_emphasised_plain", lambda text: "<e>" + text + "</e>" )
    monkeypatch.setattr( progress, "as_colour", lambda meaning, text: text )
    line = progress.format_terse_success(
            "g++ -c test/orders/src/hello.cpp",
            ["hello.o"],
            ["test/orders/src/hello.cpp"],
            _variant_env(),
    )
    assert line == (
            "[ok]   <s>test/</s><i>orders</i> <s>·</s> <s>gcc16_</s>dbg<s>_x86_64_cxx2c</s> "
            "<s>·</s> <e>compile</e> <s>·</s> <s>test/orders/src/</s><e><i>hello.cpp</i></e>"
            " <s>→</s> <e><i>hello.o</i></e>"
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
    assert draining.startswith( "[ok]   " )
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
            "<final>/protocol.report.html → <artefacts>/protocol.report.html\n"
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
    assert _compile_line( env, first, "hello.cpp" ).startswith( "   1/  2 ·  50% [ok]   " )
    assert _compile_line( env, second, "main.cpp" ).startswith( "   2/  2 · 100% [ok]   " )


def test_a_progress_checkpoint_names_the_scope_and_does_not_count( monkeypatch, tmp_path ):
    env = _terse_env()
    first = _ActionNode()
    second = _ActionNode()
    progress.register_terse_actions( env, [ first, second ] )
    opened = progress.format_terse_progress_checkpoint( "started", None, None, env )
    assert opened == (
            "variant      0% [progress] test/orders/gcc16_dbg_x86_64_cxx2c · begin · 0/2 actions"
    )
    assert opened.index( "[progress]" ) == _compile_line( env, first, "hello.cpp" ).index( "[ok]" )
    assert "1 variant" not in opened
    assert _compile_line( env, first, "hello.cpp" ).startswith( "   1/  2 ·  50% [ok]   " )
    closed = progress.format_terse_progress_checkpoint( "finished", None, None, env )
    assert closed == (
            "variant     50% [progress] test/orders/gcc16_dbg_x86_64_cxx2c · end · 1/2 actions"
    )

    script = progress.format_terse_progress_checkpoint( "begin", None, None, env )
    assert script == (
            "sconscript  50% [progress] test/orders/sconscript · begin · 1 variant · 1/2 actions"
    )

    home = tmp_path / "home"
    project = home / "coding" / "protocols"
    monkeypatch.setattr(
            os.path, "expanduser",
            lambda path: str( home ) if path == "~" else os.path.expanduser( path ),
    )
    outside = {
            "terse_output": True,
            "base_path": str( project ),
            "sconstruct_dir": str( home / "other" ),
            "sconstruct_file": "sconstruct",
    }
    root = progress.format_terse_progress_checkpoint( "sconstruct_begin", None, None, outside )
    assert root.startswith( "sconstruct  50% [progress] ~/other/sconstruct · begin · " )
    assert "1 sconscript · 1 variant · 1/2 actions" in root
    assert "../" not in root
    inside = {
            "terse_output": True,
            "base_path": str( project ),
            "sconstruct_dir": str( project ),
            "sconstruct_file": "sconstruct",
    }
    nested = progress.format_terse_progress_checkpoint( "sconstruct_begin", None, None, inside )
    assert "~/coding/protocols/sconstruct" in nested
    assert not nested.split( "[progress] ", 1 )[ 1 ].startswith( "protocols/" )

    progress.format_terse_progress_checkpoint( "started", None, None, env )
    assert _compile_line( env, second, "main.cpp" ).startswith( "   2/  2 · 100% [ok]   " )


def _current_node( current, executor=None, always_build=False ):
    node = _ActionNode( executor=executor )
    node.is_up_to_date = lambda: current
    node.always_build = always_build
    return node


def test_the_first_begin_line_counts_actions_already_up_to_date( capsys ):
    env = _terse_env()
    current = _current_node( True )
    stale = _current_node( False )
    progress.register_terse_actions( env, [ current, stale ] )
    progress.write_terse_progress_checkpoint( "sconstruct_begin", None, None, env )
    out = capsys.readouterr().out
    assert "sconstruct · begin · 1 sconscript · 1 variant · 1/2 actions" in out
    asked = { "n": 0 }

    def _counted():
        asked[ "n" ] += 1
        return True

    current.is_up_to_date = _counted
    progress.write_terse_progress_checkpoint( "started", None, None, env )
    assert asked[ "n" ] == 0
    assert _compile_line( env, stale, "main.cpp" ).startswith( "   2/  2 · 100% [ok]   " )
    progress.note_up_to_date_action( current )
    assert progress.terse_counts_prefix( env ) == "  2/  2 · 100%"

    progress.reset_progress_ledger()
    shared = _Slots( 1 )
    progress.register_terse_actions( env, [
            _current_node( True, shared ),
            _current_node( False, shared ),
    ] )
    progress.credit_terse_up_to_date_lookahead()
    assert progress.terse_counts_prefix( env ).startswith( "  0/" )

    progress.reset_progress_ledger()
    forced = _current_node( True, always_build=True )
    progress.register_terse_actions( env, [ forced ] )
    progress.credit_terse_up_to_date_lookahead()
    assert progress.terse_counts_prefix( env ).startswith( "  0/" )

    progress.reset_progress_ledger()
    broken = _ActionNode()

    def _boom():
        raise OSError( "stat" )

    broken.is_up_to_date = _boom
    progress.register_terse_actions( env, [ broken ] )
    progress.credit_terse_up_to_date_lookahead()
    assert progress.terse_counts_prefix( env ).startswith( "  0/" )


def test_a_progress_checkpoint_colours_the_badge_and_the_leaf( monkeypatch ):
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    monkeypatch.setattr( progress, "as_info", lambda text: "<i>" + text + "</i>" )
    monkeypatch.setattr( progress, "as_emphasised", lambda text: "<e>" + text + "</e>" )
    monkeypatch.setattr( progress, "as_emphasised_plain", lambda text: "<e>" + text + "</e>" )
    env = _terse_env()
    line = progress.format_terse_progress_checkpoint( "begin", None, None, env )
    assert line.startswith( "<s>sconscript</s>   0% <e><i>[progress]</i></e> " )
    assert "<s>test/</s><i>orders/</i><i>sconscript</i><s> · </s><e>begin</e>" in line
    variant = progress.format_terse_progress_checkpoint( "started", None, None, env )
    assert "<s>test/</s><i>orders/</i>" in variant
    assert "<s>gcc16_</s>dbg<s>_x86_64_cxx2c</s>" in variant
    assert "<e>begin</e>" in variant


def test_delegated_launch_bookend_and_muted_children():
    env = _terse_env()
    first = _ActionNode()
    second = _ActionNode()
    progress.register_terse_actions( env, [ first, second ] )
    launch = progress.format_terse_launch(
            "cmake-build",
            "-B _build/x --parallel 1",
            env,
    )
    assert launch == (
            "delegate     0% [launch] test/orders · gcc16_dbg_x86_64_cxx2c · "
            "cmake-build · -B _build/x --parallel 1"
    )
    assert launch.index( "[launch]" ) == _compile_line( env, first, "hello.cpp" ).index( "[ok]" )
    assert "· start ·" not in launch
    child = progress.format_terse_muted_child( "[1/75] Building CXX object foo.cpp.o", env )
    assert child.endswith( "→ [1/75] Building CXX object foo.cpp.o" )
    assert "[ok]" not in child
    done = progress.format_terse_line(
            "done",
            "cmake --build _build/x --parallel 1",
            [ SimpleNamespace(
                    path="cmake.build.complete",
                    attributes=SimpleNamespace(
                            cuppa_terse_action="cmake-build",
                            cuppa_terse_summary="-B _build/x --parallel 1",
                    ),
            ) ],
            [],
            env,
    )
    assert " [done] test/orders · gcc16_dbg_x86_64_cxx2c · cmake-build · " in done
    assert "-B _build/x --parallel 1" in done
    assert done.index( "test/" ) == _compile_line( env, first, "hello.cpp" ).index( "test/" )


def test_delegated_summary_replaces_stamp_filename_on_status_line():
    env = _terse_env()
    stamp = SimpleNamespace(
            path="cmake.build.complete",
            attributes=SimpleNamespace(
                    cuppa_terse_action="cmake-build",
                    cuppa_terse_summary="-B _build/x --parallel 1",
            ),
    )
    line = progress.format_terse_line(
            "ok",
            "cmake --build _build/x --parallel 1",
            [ stamp ],
            [],
            env,
    )
    assert line == (
            "[ok]   test/orders · gcc16_dbg_x86_64_cxx2c · cmake-build · "
            "-B _build/x --parallel 1"
    )
    assert "cmake.build.complete" not in line


def test_launch_bookend_suppresses_clean_argv_flush( capsys ):
    env = _terse_env()
    progress.stash_terse_command( "cmake --build _build/x", [ "stamp" ], [], env )
    progress.write_terse_launch(
            "cmake-build", "-B _build/x", env, command="cmake --build _build/x",
    )
    out = capsys.readouterr().out
    assert out.startswith( "delegate" )
    assert "[launch] test/orders · gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/x" in out
    assert "· start ·" not in out
    assert "cmake --build _build/x\n" not in out
    progress.flush_unconsumed_terse_command()
    assert capsys.readouterr().out == ""
    emitted, command = progress.take_terse_launch()
    assert emitted
    assert command == "cmake --build _build/x"


def test_shared_across_variants_replaces_the_variant_cell( monkeypatch ):
    env = _terse_env()
    node = SimpleNamespace(
            path="b2",
            attributes=SimpleNamespace( cuppa_terse_action="build-b2" ),
    )
    progress.label_terse_action( [ node ], "build-b2", shared=True )
    assert node.attributes.cuppa_terse_shared == "shared_across_variants"
    line = progress.format_terse_line( "ok", "build b2", [ node ], [], env )
    assert "· shared_across_variants · build-b2 ·" in line
    assert "gcc16_dbg_x86_64_cxx2c" not in line
    launch = progress.format_terse_launch( "build-b2", "tools/build", env, target=[ node ] )
    assert "[launch] test/orders · shared_across_variants · build-b2" in launch
    assert "gcc16_dbg_x86_64_cxx2c" not in launch

    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    painted = progress._coloured_shared_label( "shared_across_variants" )
    assert painted == "shared<s>_across_variants</s>"


def test_build_b2_file_cell_is_the_extract_product( monkeypatch ):
    env = _layout_env()
    env["terse_output"] = True
    boost = "/proj/_download/boost_1_86_0"
    progress.label_terse_location( env, "boost", boost )
    node = SimpleNamespace(
            path=boost + "/b2",
            attributes=SimpleNamespace(),
    )
    progress.label_terse_action( [ node ], "build-b2", paths="product", shared=True )
    line = progress.format_terse_line( "done", "./build.sh", [ node ], [], env )
    assert "· build-b2 · <boost>/b2" in line
    nested = progress.format_terse_line(
            "ok",
            'Copy("{}/b2", "{}/tools/build/src/engine/b2")'.format( boost, boost ),
            [ boost + "/b2" ],
            [ boost + "/tools/build/src/engine/b2" ],
            env,
            count=False,
    )
    assert nested.startswith( "→" )
    assert "· copy ·" in nested
    assert "<boost>/tools/build/src/engine/b2 → <boost>/b2" in nested
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    monkeypatch.setattr( progress, "as_info", lambda text: "<i>" + text + "</i>" )
    monkeypatch.setattr( progress, "as_emphasised", lambda text: "<e>" + text + "</e>" )
    painted = progress.format_terse_line( "done", "./build.sh", [ node ], [], env )
    assert "<s><boost>/</s><e><i>b2</i></e>" in painted


def test_variant_begin_prints_builtin_location_maps( capsys ):
    env = _layout_env()
    env["terse_output"] = True
    progress.write_terse_progress_checkpoint( "started", None, None, env )
    out = capsys.readouterr().out
    assert "variant" in out and "[progress]" in out
    assert "[location]" in out
    assert "reference_guide · gcc16_dbg_x86_64_cxx2c · <working> =" in out
    assert "working" in out
    assert "reference_guide · gcc16_dbg_x86_64_cxx2c · <final> =" in out
    assert "final" in out
    assert "reference_guide · gcc16_dbg_x86_64_cxx2c · <artefacts> =" in out
    assert "_artifacts" in out
    progress.write_terse_progress_checkpoint( "finished", None, None, env )
    closed = capsys.readouterr().out
    assert "[location]" not in closed


def test_sconscript_begin_prints_author_boost_location( capsys ):
    env = _layout_env()
    env["terse_output"] = True
    progress.label_terse_location( env, "boost", "/proj/_download/boost_1_86_0" )
    progress.write_terse_progress_checkpoint( "begin", None, None, env )
    out = capsys.readouterr().out
    assert "sconscript" in out and "[progress]" in out
    assert "[location]" in out
    assert "reference_guide · <boost> =" in out
    assert "gcc16_dbg_x86_64_cxx2c · <boost>" not in out
    assert "_download/boost_1_86_0" in out
    progress.write_terse_progress_checkpoint( "started", None, None, env )
    variant = capsys.readouterr().out
    assert "<boost>" not in variant
    assert "reference_guide · gcc16_dbg_x86_64_cxx2c · <working> =" in variant


def test_location_path_colours_the_sconscript_leaf_like_progress( monkeypatch ):
    env = _layout_env()
    env["terse_output"] = True
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<s>" + text + "</s>" )
    monkeypatch.setattr( progress, "as_info", lambda text: "<i>" + text + "</i>" )
    monkeypatch.setattr( progress, "as_emphasised", lambda text: "<e>" + text + "</e>" )
    monkeypatch.setattr( progress, "as_notice", lambda text: "<n>" + text + "</n>" )
    line = progress.format_terse_location_line(
            "working", env[ "abs_build_dir" ], env, scope="variant",
    )
    assert "<s>→</s>" in line
    assert "<n>[location]</n>" in line
    assert "<e><i>[location]</i></e>" not in line
    assert "<i>[location]</i>" not in line
    assert "<i>reference_guide</i>" in line
    assert "<s>_build</s>" in line
    assert "<s>/</s>dbg<s>/</s>" in line
    assert "<e><i>working</i></e>" in line
    env[ "sconscript_file" ] = "./test/sconscript"
    env[ "abs_build_dir" ] = "/proj/_build/test/gcc16/dbg/x86_64/cxx2c/working"
    test_line = progress.format_terse_location_line(
            "working", env[ "abs_build_dir" ], env, scope="variant",
    )
    assert "<i>test</i>" in test_line
    assert "<s>gcc16_</s>dbg<s>_x86_64_cxx2c</s>" in test_line
    assert "<working>" in test_line
    boost = progress.format_terse_location_line(
            "boost", "/proj/_download/boost_1_86_0", env, scope="sconscript",
    )
    assert "gcc16_dbg_x86_64_cxx2c" not in boost
    assert "<boost>" in boost
    assert "<i>test</i>" in boost


def test_location_library_compile_nests_dependency_and_variant_tokens():
    env = _layout_env()
    env["abs_build_root"] = "/proj/_build"
    env["tool_variant_dir"] = "gcc16/dbg/x86_64/cxx2c"
    download = "/home/u/_cuppa/_download"
    folder = "git_https_github.com__fmtlib_fmt.git@master"
    fmt = download + "/" + folder
    progress.label_terse_location( env, "dependencies", download, scope="sconstruct" )
    progress.label_terse_location(
            env, "fmt", fmt, scope="sconstruct", build_folder=folder,
    )
    line = progress.format_terse_success(
            "g++ -c " + fmt + "/src/format.cc",
            [ "/proj/_build/" + folder + "/gcc16/dbg/x86_64/cxx2c/working/src/format.o" ],
            [ fmt + "/src/format.cc" ],
            env,
    )
    assert "· compile · <dependencies>/<fmt>/src/format.cc → " in line
    assert "_build/<fmt>/<variant>/working/src/format.o" in line
    assert "git_https" not in line

    env["sconscript_file"] = "./test/orders/sconscript"
    progress.label_terse_location( env, "dependencies", download, scope="sconstruct" )
    progress.label_terse_location(
            env, "fmt", fmt, scope="sconstruct", build_folder=folder,
    )
    again = progress.format_terse_success(
            "g++ -c " + fmt + "/src/format.cc",
            [ "/proj/_build/" + folder + "/gcc16/dbg/x86_64/cxx2c/working/src/format.o" ],
            [ fmt + "/src/format.cc" ],
            env,
    )
    assert again.count( "<dependencies>" ) == 1
    assert "<fmt>/<fmt>" not in again
    assert "<dependencies>/<dependencies>" not in again


def test_project_root_location_does_not_wrap_project_sources():
    env = _layout_env()
    env["sconstruct_dir"] = "/proj"
    progress.label_terse_location( env, "app", "/proj", scope="sconstruct" )
    line = progress.format_terse_success(
            "g++ -c test/orders/widget.cpp",
            [ env["abs_build_dir"] + "/widget.o" ],
            [ "/proj/test/orders/widget.cpp" ],
            env,
    )
    assert "· compile · test/orders/widget.cpp → <working>/widget.o" in line
    assert "<app>" not in line


def test_same_extract_two_names_uses_one_token():
    env = _layout_env()
    download = "/home/u/_cuppa/_download"
    date = download + "/git_https_github.com__HowardHinnant_date.git@master"
    progress.label_terse_location( env, "dependencies", download, scope="sconstruct" )
    progress.label_terse_location( env, "date", date, scope="sconstruct" )
    progress.label_terse_location( env, "quince_date_lib", date, scope="sconstruct" )
    line = progress.format_terse_success(
            "g++ -c " + date + "/src/tz.cpp",
            [ "tz.o" ],
            [ date + "/src/tz.cpp" ],
            env,
    )
    assert "· compile · <dependencies>/<date>/src/tz.cpp → tz.o" in line
    assert "<quince_date_lib>" not in line


def test_clean_does_not_print_read_checkpoint_or_maps( capsys ):
    env = _layout_env()
    env["terse_output"] = True
    env["clean"] = True
    env["sconstruct_dir"] = "/proj"
    progress.write_terse_read_checkpoint( env )
    progress.label_terse_location(
            env, "dependencies", "/home/u/_cuppa/_download", scope="sconstruct",
    )
    assert capsys.readouterr().out == ""


def test_develop_location_does_not_nest_under_dependencies():
    env = _layout_env()
    download = "/home/u/_cuppa/_download"
    develop = "/home/u/src/libfoo"
    progress.label_terse_location( env, "dependencies", download, scope="sconstruct" )
    progress.label_terse_location( env, "libfoo", develop, scope="sconstruct" )
    line = progress.format_terse_success(
            "g++ -c " + develop + "/src/foo.cpp",
            [ "foo.o" ],
            [ develop + "/src/foo.cpp" ],
            env,
    )
    assert "· compile · <libfoo>/src/foo.cpp → foo.o" in line
    assert "<dependencies>/<libfoo>" not in line


def test_link_archive_index_use_located_product( capsys ):
    env = _layout_env()
    env["tool_variant_dir"] = "gcc16/dbg/x86_64/cxx2c"
    env["abs_build_root"] = "/proj/_build"
    linked = progress.format_terse_line(
            "ok",
            "g++ -o management management.o",
            [ env["abs_final_dir"] + "/management" ],
            [ env["abs_build_dir"] + "/management.o" ],
            env,
    )
    assert "· link · <final>/management" in linked
    assert "→" not in linked

    folder = "git_https_github.com__fmtlib_fmt.git@master"
    fmt = "/home/u/_cuppa/_download/" + folder
    progress.label_terse_location( env, "dependencies", "/home/u/_cuppa/_download", scope="sconstruct" )
    progress.label_terse_location(
            env, "fmt", fmt, scope="sconstruct", build_folder=folder,
    )
    archive = "/proj/_build/" + folder + "/gcc16/dbg/x86_64/cxx2c/final/libfmt.a"
    archived = progress.format_terse_line(
            "ok", "ar rc libfmt.a format.o", [ archive ], [ fmt + "/src/format.cc" ], env,
    )
    indexed = progress.format_terse_line(
            "ok", "ranlib libfmt.a", [ archive ], [], env,
    )
    assert "· archive · _build/<fmt>/<variant>/final/libfmt.a" in archived
    assert "· index · _build/<fmt>/<variant>/final/libfmt.a" in indexed
    ran = progress.format_terse_line(
            "ok",
            "management",
            [ _LabelledNode( "run", env["abs_final_dir"] + "/management.stdout.log" ) ],
            [ env["abs_final_dir"] + "/management" ],
            env,
    )
    assert ran.endswith( "· run · <final>/management" )
    env["terse_output"] = True
    from cuppa.cpp.terse_test_report import write_case, write_rollup
    write_rollup(
            env, env["abs_final_dir"] + "/management", "pass", 8_000_000,
            1, 0, 0, 0, 0, 1, assertions=( 8, 8 ),
    )
    out = capsys.readouterr().out
    assert "· test · 8 ms · <final>/management — 1/1 cases, 8/8 assertions" in out
    write_case(
            env,
            env["abs_final_dir"] + "/management",
            {
                "name": "rejects_a_cross",
                "status": "failed",
                "passed": 1,
                "total": 3,
            },
            18_000_000,
    )
    case = capsys.readouterr().out
    assert "· test-case · 18 ms · management/rejects_a_cross — 1/3 assertions" in case
    assert "<final>" not in case


def test_read_checkpoint_prints_sconstruct_maps_once( capsys ):
    env = _layout_env()
    env["terse_output"] = True
    env["sconstruct_file"] = "sconstruct"
    env["sconstruct_dir"] = "/proj"
    env["default_dependencies"] = [ "fmt", "boost_package" ]
    env["dependencies"] = {
            "fmt": SimpleNamespace(),
            "boost_package": SimpleNamespace( _package="boost", _package_manager="gitlab" ),
    }
    download = "/home/u/_cuppa/_download"
    fmt = download + "/git_https_github.com__fmtlib_fmt.git@master"
    progress.write_terse_read_checkpoint( env )
    progress.label_terse_location( env, "dependencies", download, scope="sconstruct" )
    progress.label_terse_location( env, "fmt", fmt, scope="sconstruct" )
    progress.write_terse_read_checkpoint( env )
    out = capsys.readouterr().out
    assert out.count( "[progress]" ) == 1
    assert "· read ·" in out
    assert "0%" in out
    assert "2 dependencies" in out
    assert "1 location" in out
    assert "1 package" in out
    assert "<dependencies> =" in out
    assert "<fmt> =" in out
    assert "git_https_github.com__fmtlib_fmt.git@master" in out
    loc = [ line for line in out.splitlines() if "[location]" in line ][0]
    assert loc.startswith( " " )
    progress.write_terse_progress_checkpoint( "sconstruct_begin", None, None, env )
    begin = capsys.readouterr().out
    assert "<dependencies>" not in begin
    assert "<fmt>" not in begin
    assert "· begin" in begin


def test_variant_working_map_substitutes_variant_token():
    env = _layout_env()
    env["tool_variant_dir"] = "gcc16/dbg/x86_64/cxx2c"
    env["sconstruct_dir"] = "/proj"
    progress.label_terse_location( env, "app", "/proj", scope="sconstruct" )
    line = progress.format_terse_location_line(
            "working", env[ "abs_build_dir" ], env, scope="variant",
    )
    assert "<working> =" in line
    assert "<variant>" in line
    assert "gcc16/dbg/x86_64/cxx2c" not in line.split( "<working>", 1 )[ -1 ]


def test_variant_begin_prints_variant_token_map( capsys ):
    env = _layout_env()
    env["terse_output"] = True
    env["tool_variant_dir"] = "gcc16/dbg/x86_64/cxx2c"
    progress.write_terse_progress_checkpoint( "started", None, None, env )
    out = capsys.readouterr().out
    assert "· <variant> =" in out
    assert "gcc16/dbg/x86_64/cxx2c" in out


def test_delegated_python_action_closes_with_done( capsys ):
    env = _terse_env()
    stamp = SimpleNamespace(
            path="cmake.build.complete",
            attributes=SimpleNamespace(
                    cuppa_terse_action="cmake-build",
                    cuppa_terse_summary="-B _build/x",
            ),
    )

    def _action( target, source, env ):
        progress.write_terse_launch(
                "cmake-build", "-B _build/x", env, command="cmake --build _build/x",
        )
        progress.write_terse_muted_child( "[1/1] Linking", env )
        return 0

    progress.stash_terse_command( "cmake --build _build/x", [ stamp ], [], env )
    wrapped = progress._TersePythonCallable( _action )
    assert wrapped( target=[ stamp ], source=[], env=env ) == 0
    out = capsys.readouterr().out
    assert "[launch] test/orders · gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/x" in out
    assert "→ [1/1] Linking" in out
    assert "[done] test/orders · gcc16_dbg_x86_64_cxx2c · cmake-build · -B _build/x" in out
    assert "[ok]" not in out


def test_archive_and_index_are_two_slots_on_one_library():
    env = _terse_env()
    library = _ActionNode( slots=2 )
    progress.register_terse_actions( env, [ library ] )
    assert _compile_line( env, library, "a.o" ).startswith( "   1/  2 ·  50% [ok]   " )
    assert _compile_line( env, library, "a.o" ).startswith( "   2/  2 · 100% [ok]   " )


def test_targets_that_share_an_executor_count_once():
    env = _terse_env()
    executor = _Slots( 1 )
    stdout = _ActionNode( executor=executor )
    report = _ActionNode( executor=executor )
    progress.register_terse_actions( env, [ stdout, report ] )
    assert _compile_line( env, stdout, "buy_sell_ladder" ).startswith( "   1/  1 · 100% [ok]   " )


def test_another_sconscript_changes_the_percent_not_the_cell_fraction():
    orders = _terse_env()
    positions = _terse_env()
    positions[ "sconscript_file" ] = "./test/positions/sconscript"
    orders_node = _ActionNode()
    positions_node = _ActionNode()
    progress.register_terse_actions( orders, [ orders_node ] )
    progress.register_terse_actions( positions, [ positions_node ] )
    assert _compile_line( orders, orders_node, "hello.cpp" ).startswith( "   1/  1 ·  50% [ok]   " )
    assert _compile_line( positions, positions_node, "book.cpp" ).startswith( "   1/  1 · 100% [ok]   " )


def test_an_up_to_date_action_is_already_done():
    env = _terse_env()
    skipped = _ActionNode()
    waiting = _ActionNode()
    progress.register_terse_actions( env, [ skipped, waiting ] )
    progress.note_up_to_date_action( skipped )
    assert progress.terse_counts_prefix( env ) == "  1/  2 ·  50%"
    assert _compile_line( env, waiting, "hello.cpp" ).startswith( "   2/  2 · 100% [ok]   " )


def test_actions_outside_the_requested_targets_are_not_in_the_total():
    env = _terse_env()
    child = _ActionNode()
    root = _ActionNode( children=[ child ] )
    other = _ActionNode()
    progress.register_terse_actions( env, [ root, child, other ] )
    progress.narrow_progress_ledger( [ root ] )
    assert _compile_line( env, child, "hello.cpp" ).startswith( "   1/  2 ·  50% [ok]   " )
    assert _compile_line( env, root, "app" ).startswith( "   2/  2 · 100% [ok]   " )


def test_a_test_case_is_marked_and_does_not_move_the_tally():
    env = _terse_env()
    binary = _ActionNode()
    progress.register_terse_actions( env, [ binary ] )
    progress.remember_terse_action_target( [ binary ] )
    case = progress.format_terse_result_line(
            "pass", env, "test-case", "position_source_id/test_position_source_id",
            duration="0 ms", detail="8/8 assertions",
    )
    plain = "  0/  1 ·   0%"
    assert progress.terse_counts_prefix( env ) == plain
    assert case.startswith( ( " " * len( plain ) ) + "→ [pass] " )
    assert "·" not in case.split( "[pass]", 1 )[ 0 ]
    rollup = progress.format_terse_result_line(
            "pass", env, "test", "position_source_id",
            duration="1 ms", detail="2/2 cases, 9/9 assertions",
    )
    assert rollup.startswith( "   1/  1 · 100% [pass] " )
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
    assert _compile_line( env, nxt, "hello.cpp" ).startswith( "   2/  2 · 100% [ok]   " )


def test_make_ready_counts_an_up_to_date_node():
    import SCons.Node

    env = _terse_env()
    skipped = _ActionNode()
    skipped.state = SCons.Node.up_to_date
    waiting = _ActionNode()
    progress.register_terse_actions( env, [ skipped, waiting ] )
    progress._credit_up_to_date_targets( [ skipped ] )
    assert progress.terse_counts_prefix( env ) == "  1/  2 ·  50%"


def test_the_tally_reserves_three_digits_and_the_arrow_keeps_the_status_column():
    endpoint_env = _terse_env()
    endpoint = [ _ActionNode() for _ in range( 182 ) ]
    progress.register_terse_actions( endpoint_env, endpoint )
    for node in endpoint[ :18 ]:
        progress.note_up_to_date_action( node )
    counted = _compile_line( endpoint_env, endpoint[ 18 ], "decommission_endpoint.cpp" )
    assert counted.startswith( "  19/182 ·  10% [ok]   " )

    ethereum_env = _terse_env()
    ethereum_env[ "sconscript_file" ] = "./test/ethereum/sconscript"
    ethereum = [ _ActionNode() for _ in range( 56 ) ]
    progress.register_terse_actions( ethereum_env, ethereum )
    for node in ethereum[ :24 ]:
        progress.note_up_to_date_action( node )
    other = _compile_line( ethereum_env, ethereum[ 24 ], "encoded_transaction_data.cpp" )
    assert other.startswith( "  25/ 56 · " )
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
    wide_line = _compile_line( wide_env, wide, "a.cpp" )
    assert wide_line.startswith( "   1/1000 · " )
    wide_progress = progress.format_terse_progress_checkpoint( "started", None, None, wide_env )
    assert wide_progress.startswith( " variant" )
    assert wide_line.index( "[ok]" ) == wide_progress.index( "[progress]" )


def test_show_actions_appends_the_raw_command():
    env = _terse_env()
    hidden = progress.format_terse_line( "ok", "g++ -c hello.cpp", [ "a.o" ], [ "hello.cpp" ], env, count=False )
    assert "g++ -c hello.cpp" not in hidden
    env[ "terse_output_show_actions" ] = True
    shown = progress.format_terse_line( "ok", "g++ -c hello.cpp", [ "a.o" ], [ "hello.cpp" ], env, count=False )
    assert shown.endswith( "g++ -c hello.cpp" )
    assert shown.index( "compile" ) < shown.index( "g++" )


def test_the_cell_tally_is_subdued_and_the_percentage_is_plain( monkeypatch ):
    monkeypatch.setattr( progress, "as_subdued", lambda text: "<subdued>{}</subdued>".format( text ) )
    assert progress._colour_counts_prefix( " 19/182 ·  10%" ) == (
            "<subdued> 19/182 · </subdued> 10%"
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
