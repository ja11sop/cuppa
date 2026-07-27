import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_compile_static_and_shared_objects(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.CompileStatic('src/hello.cpp')\n"
        "env.CompileShared('src/hello.cpp')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    objects = [p for p in find_under_build(project, "hello.*") if p.suffix in (".o", ".obj")]
    assert objects
