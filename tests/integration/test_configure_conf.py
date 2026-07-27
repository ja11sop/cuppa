import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_save_and_show_conf(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\nenv.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    saved = run_cuppa(project, "--dbg", "--save-conf")
    assert_success(saved)
    conf = project / "configure.conf"
    assert conf.exists()
    shown = run_cuppa(project, "--show-conf")
    assert_success(shown)
    assert "dbg" in shown.stdout or conf.read_text()
