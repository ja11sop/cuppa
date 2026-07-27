import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_build_static_and_shared_lib(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.BuildStaticLib('hello', 'src/hello.cpp')\n"
        "env.BuildSharedLib('hello_shared', 'src/hello.cpp')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    static_libs = [p for p in find_under_build(project, "*hello*") if p.suffix in (".a", ".lib") and "final" in p.parts]
    shared_libs = [
        p for p in find_under_build(project, "*hello_shared*")
        if p.suffix in (".so", ".dylib", ".dll") and "final" in p.parts
    ]
    assert static_libs
    assert shared_libs
