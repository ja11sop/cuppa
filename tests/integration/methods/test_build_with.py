import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_build_with_location_dependency(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(
        project,
        body=(
            "import cuppa\n"
            "Headers = cuppa.location_dependency(\n"
            "    'dummy_headers',\n"
            "    location='include',\n"
            "    include='.',\n"
            ")\n"
            "cuppa.run(\n"
            "    default_variants=['dbg'],\n"
            "    import_dependencies=[Headers],\n"
            ")\n"
        ),
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildWith('dummy_headers')\n"
        "assert env.Using('dummy_headers') is not None\n"
        "env.Build('main', 'apps/main.cpp')\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    assert find_final_binaries(project, "main")
