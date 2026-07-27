import logging
import shutil

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def test_compile_scss(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "css = os.path.join(env['abs_final_dir'], 'sample.css')\n"
        "env.CompileScss(css, 'data/sample.scss')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    css_files = [p for p in find_under_build(project, "sample.css") if p.is_file()]
    assert css_files


def test_markdown_to_html(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.MarkdownToHtml('data/sample.md')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    assert any(p.suffix == ".html" for p in find_under_build(project))


def test_asciidoc_to_html(tmp_path):
    if not shutil.which("asciidoc") and not shutil.which("asciidoctor"):
        message = "asciidoc/asciidoctor not on PATH; skipping AsciidocToHtml integration test"
        logger.warning(message)
        pytest.skip(message)
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "html = os.path.join(env['abs_final_dir'], 'sample_adoc.html')\n"
        "env.AsciidocToHtml(html, 'data/sample.adoc')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    assert find_under_build(project, "sample_adoc.html")
