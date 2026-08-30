#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Doc/asset emitters mirror nested sources under final/ (#233)."""

import logging
import shutil

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def _html_under_final(project):
    found = []
    for final in project.glob("_build/**/final"):
        for path in final.rglob("*.html"):
            if path.is_file():
                found.append(path.relative_to(final).as_posix())
    return sorted(found)


def _css_under_final(project):
    found = []
    for final in project.glob("_build/**/final"):
        for path in final.rglob("*.css"):
            if path.is_file():
                found.append(path.relative_to(final).as_posix())
    return sorted(found)


def test_markdown_to_html_mirrors_nested_same_basenames(tmp_path):
    project = tmp_path / "md_mirror"
    project.mkdir()
    (project / "doc" / "a").mkdir(parents=True)
    (project / "doc" / "b").mkdir(parents=True)
    (project / "doc" / "a" / "readme.md").write_text("# A\n", encoding="utf-8")
    (project / "doc" / "b" / "readme.md").write_text("# B\n", encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.MarkdownToHtml(['doc/a/readme.md', 'doc/b/readme.md'])\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    html = _html_under_final(project)
    assert "doc/a/readme.html" in html, html
    assert "doc/b/readme.html" in html, html
    assert "readme.html" not in html, "flat basename collision layout: " + str(html)


def test_markdown_to_html_flat_source_stays_at_final_root(tmp_path):
    project = tmp_path / "md_flat"
    project.mkdir()
    (project / "readme.md").write_text("# Top\n", encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.MarkdownToHtml('readme.md')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    html = _html_under_final(project)
    assert "readme.html" in html, html


def test_compile_scss_mirrors_nested_same_basenames(tmp_path):
    project = tmp_path / "scss_mirror"
    project.mkdir()
    (project / "styles" / "a").mkdir(parents=True)
    (project / "styles" / "b").mkdir(parents=True)
    scss = "$color: #336699;\n.button { color: $color; }\n"
    (project / "styles" / "a" / "app.scss").write_text(scss, encoding="utf-8")
    (project / "styles" / "b" / "app.scss").write_text(scss, encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.CompileScss([], ['styles/a/app.scss', 'styles/b/app.scss'])\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    css = _css_under_final(project)
    assert "styles/a/app.css" in css, css
    assert "styles/b/app.css" in css, css
    assert "app.css" not in css, "flat basename collision layout: " + str(css)
    assert not (project / "styles" / "a" / "app.css").exists(), (
        "default CompileScss must not write beside the source"
    )


def test_compile_scss_default_mirrors_under_final(tmp_path):
    project = tmp_path / "scss_default"
    project.mkdir()
    (project / "data").mkdir()
    (project / "data" / "sample.scss").write_text(
        "$color: #336699;\n.button { color: $color; }\n",
        encoding="utf-8",
    )
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.CompileScss([], 'data/sample.scss')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    css = _css_under_final(project)
    assert "data/sample.css" in css, css


def test_asciidoc_to_html_mirrors_nested_same_basenames(tmp_path):
    if not shutil.which("asciidoc") and not shutil.which("asciidoctor"):
        message = "asciidoc/asciidoctor not on PATH; skipping AsciidocToHtml mirror test"
        logger.warning(message)
        pytest.skip(message)
    project = tmp_path / "adoc_mirror"
    project.mkdir()
    (project / "doc" / "a").mkdir(parents=True)
    (project / "doc" / "b").mkdir(parents=True)
    (project / "doc" / "a" / "readme.adoc").write_text("= A\n\nHello A.\n", encoding="utf-8")
    (project / "doc" / "b" / "readme.adoc").write_text("= B\n\nHello B.\n", encoding="utf-8")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AsciidocToHtml([], ['doc/a/readme.adoc', 'doc/b/readme.adoc'])\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    html = _html_under_final(project)
    assert "doc/a/readme.html" in html, html
    assert "doc/b/readme.html" in html, html
    assert "readme.html" not in html, "flat basename collision layout: " + str(html)
