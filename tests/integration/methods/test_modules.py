#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging
import shutil
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import (
    assert_success,
    build_files,
    find_final_binaries,
    find_under_build,
    run_cuppa,
)
from tests.helpers.project import write_sconscript, write_sconstruct
from tests.helpers.toolchains import require_modules_capable_toolchain

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULES_PROJECT = REPO_ROOT / "tests" / "fixtures" / "modules_project"


def _copy_modules_project(tmp_path):
    dest = tmp_path / "modules_project"
    shutil.copytree(MODULES_PROJECT, dest)
    return dest


def _modules_toolchain_flag():
    """Prefer default gcc/clang (e.g. via update-alternatives); probe only if needed."""
    alias, driver, major = require_modules_capable_toolchain()
    logger.info("C++ modules tests using toolchain %s (%s major %s)", alias, driver, major)
    return alias, "--toolchains={}".format(alias)


def _is_gcc_family(alias):
    return alias == "gcc" or alias.startswith("gcc")


def test_named_module_build(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('math_app', ['math.cppm', 'apps/main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "math_app")


def test_header_unit_build(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.HeaderUnit('include/widget.hpp')\n"
        "env.Build('widget_app', ['apps/header_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "widget_app")


def test_implementation_unit_build(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('impl_app', ['math_decl.cppm', 'math_impl.cpp', 'apps/impl_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "impl_app")


def test_interface_partition_build(tmp_path):
    """Primary interface re-exports a partition (export import :point)."""
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    # Primary listed before the partition — BMI pre-registration must still work.
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('geo_app', [\n"
        "    'geo/geo.cppm',\n"
        "    'geo/point.cppm',\n"
        "    'apps/geo_main.cpp',\n"
        "])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "geo_app")


def test_implementation_partition_build(tmp_path):
    """Internal partition (module calc:core) used by an implementation unit."""
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('calc_app', [\n"
        "    'calc/calc.cppm',\n"
        "    'calc/core.cpp',\n"
        "    'calc/calc.cpp',\n"
        "    'apps/calc_main.cpp',\n"
        "])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "calc_app")


def test_private_module_fragment_build(tmp_path):
    """
    Private module fragment (module :private;).

    GCC still reports this as unimplemented; Clang supports it.
    """
    alias, toolchain_flag = _modules_toolchain_flag()
    if _is_gcc_family(alias):
        pytest.skip("GCC does not implement private module fragments yet")
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('secrets_app', ['secrets.cppm', 'apps/secrets_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "secrets_app")


def test_module_reexport_build(tmp_path):
    """export import util; from a second named module."""
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('reexport_app', [\n"
        "    'appmod.cppm',\n"
        "    'util.cppm',\n"
        "    'apps/reexport_main.cpp',\n"
        "])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "reexport_app")


def test_mixed_named_module_and_header_unit(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.HeaderUnit('include/widget.hpp')\n"
        "env.Build('mixed_app', ['math.cppm', 'apps/mixed_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "mixed_app")


def test_named_module_build_then_clean(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('math_app', ['math.cppm', 'apps/main.cpp'])\n",
    )
    assert_success(run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag))
    assert find_final_binaries(project, "math_app")
    assert find_under_build(project, "*.gcm") or find_under_build(project, "*.pcm")
    assert find_under_build(project, "*.o") or find_under_build(project, "*.obj")

    assert_success(
        run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag, "--clean")
    )
    leftover = build_files(project)
    assert leftover == [], (
        "expected no files under _build after --clean, found:\n"
        + "\n".join(str(path) for path in leftover)
    )


def test_header_unit_build_then_clean(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.HeaderUnit('include/widget.hpp')\n"
        "env.Build('widget_app', ['apps/header_main.cpp'])\n",
    )
    assert_success(run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag))
    assert find_final_binaries(project, "widget_app")
    header_bmis = [
        path for path in build_files(project)
        if path.name.startswith("header--") and path.suffix in (".gcm", ".pcm")
    ]
    assert header_bmis

    assert_success(
        run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag, "--clean")
    )
    leftover = build_files(project)
    assert leftover == [], (
        "expected no files under _build after --clean, found:\n"
        + "\n".join(str(path) for path in leftover)
    )
