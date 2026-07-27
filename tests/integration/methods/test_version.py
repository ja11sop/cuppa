import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_create_version(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "version_cpp = os.path.join(env['abs_final_dir'], 'version.cpp')\n"
        "env.CreateVersion(\n"
        "    version_cpp,\n"
        "    [],\n"
        "    namespaces=['dummy', 'version'],\n"
        "    version='1.2.3',\n"
        ")\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('main', ['apps/main.cpp', version_cpp])\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    version_files = list(find_under_build(project, "version.cpp"))
    assert version_files
