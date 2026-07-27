import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_expand_template_and_jinja(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "out_txt = os.path.join(env['abs_final_dir'], 'expanded.txt')\n"
        "env.ExpandTemplateFile(out_txt, 'data/template.txt.in', name='cuppa')\n"
        "env.RenderJinjaTemplate(\n"
        "    [os.path.join(env['abs_final_dir'], 'rendered.txt')],\n"
        "    ['data/template.j2'],\n"
        "    variables={'name': 'cuppa'},\n"
        ")\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    expanded = [p for p in find_under_build(project, "expanded.txt") if p.is_file()]
    rendered = [p for p in find_under_build(project, "rendered.txt") if p.is_file()]
    assert expanded and "Hello cuppa!" in expanded[0].read_text()
    assert rendered and "Hello cuppa!" in rendered[0].read_text()
