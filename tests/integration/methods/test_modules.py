#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging
import os
import shutil
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import write_sconscript, write_sconstruct
from tests.helpers.toolchains import require_toolchain

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULES_PROJECT = REPO_ROOT / "tests" / "fixtures" / "modules_project"


def _copy_modules_project(tmp_path):
    dest = tmp_path / "modules_project"
    shutil.copytree(MODULES_PROJECT, dest)
    return dest


def _require_modules_toolchain():
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        pytest.skip("C++ modules are not supported for MSVC in this cuppa release")
    family = forced if forced in ("gcc", "clang") else None
    if family:
        require_toolchain(family)
    else:
        # Prefer whatever default_toolchain_flags would pick, but skip MSVC-only hosts
        require_toolchain("gcc")


def test_named_module_build(tmp_path):
    _require_modules_toolchain()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('math_app', ['math.cppm', 'apps/main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20")
    assert_success(result)
    assert find_final_binaries(project, "math_app")


def test_header_unit_build(tmp_path):
    _require_modules_toolchain()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.HeaderUnit('include/widget.hpp')\n"
        "env.Build('widget_app', ['apps/header_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20")
    assert_success(result)
    assert find_final_binaries(project, "widget_app")
