import logging
import shutil

import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def test_toolchains_gcc_build(tmp_path):
    from tests.helpers.toolchains import require_toolchain

    require_toolchain("gcc")
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('main', 'apps/main.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--toolchains=gcc")
    assert_success(result)
    assert find_final_binaries(project, "main")


def test_toolchains_clang_when_available(tmp_path):
    if not (shutil.which("clang++") or shutil.which("clang")):
        message = "clang not available; skipping clang toolchain integration test"
        logger.warning(message)
        pytest.skip(message)

    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "env.Build('main', 'apps/main.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--toolchains=clang")
    assert_success(result)
    assert find_final_binaries(project, "main")
