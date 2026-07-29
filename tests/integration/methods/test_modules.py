#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import logging
import shutil
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import (
    assert_failure,
    assert_success,
    build_files,
    find_final_binaries,
    find_under_build,
    run_cuppa,
)
from tests.helpers.project import write_sconscript, write_sconstruct
from tests.helpers.toolchains import (
    require_modules_capable_toolchain,
)
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


def _is_msvc(alias):
    return alias in ("vc", "cl", "msvc") or str(alias).startswith("vc")


def _skip_msvc_feature(alias, feature):
    if _is_msvc(alias):
        pytest.skip("{} is not supported for MSVC modules yet".format(feature))


def _require_import_std_toolchain():
    """
    Select a toolchain that can build import std BMIs.

    GCC 15+ with bits/std.cc, Clang 18+ with libc++ and matching std.cppm,
    or MSVC toolset 14.3+ with STL modules/std.ixx.
    """
    import shutil

    alias, driver, major = require_modules_capable_toolchain()
    if _is_msvc(alias):
        from cuppa.toolchains.cl import find_msvc_modules_dir
        modules_dir = find_msvc_modules_dir()
        if not modules_dir:
            pytest.skip(
                "import std for MSVC requires STL modules/std.ixx "
                "(VS 2022 17.5+ / toolset 14.3+)"
            )
        return alias, "--toolchains={}".format(alias), []
    if _is_gcc_family(alias):
        if major < 15:
            pytest.fail(
                "import std tests require GCC 15+ (found {} major {})".format(alias, major)
            )
        std_cc = Path("/usr/include/c++/{}/bits/std.cc".format(major))
        if not std_cc.is_file():
            pytest.fail("GCC import std source missing: {}".format(std_cc))
        return alias, "--toolchains={}".format(alias), []

    # Clang: need libc++ module interfaces for this compiler major.
    def _has_std_cppm(maj):
        return Path("/usr/lib/llvm-{}/share/libc++/v1/std.cppm".format(maj)).is_file()

    if _has_std_cppm(major) and major >= 18:
        return alias, "--toolchains={}".format(alias), ["--clang-stdlib=libc++"]

    for candidate_major in range(25, 17, -1):
        cmd = "clang++-{}".format(candidate_major)
        if shutil.which(cmd) and _has_std_cppm(candidate_major):
            return (
                "clang{}".format(candidate_major),
                "--toolchains=clang{}".format(candidate_major),
                ["--clang-stdlib=libc++"],
            )

    pytest.fail(
        "import std for Clang requires libc++ std.cppm next to the compiler "
        "(need /usr/lib/llvm-<N>/share/libc++/v1/std.cppm; none found for {})"
        .format(alias)
    )


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
    _skip_msvc_feature(alias, "private module fragments")
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
    assert find_under_build(project, "*.gcm") or find_under_build(project, "*.pcm") or find_under_build(project, "*.ifc")
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
        if path.name.startswith("header--") and path.suffix in (".gcm", ".pcm", ".ifc")
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


def test_angle_header_unit_build(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.HeaderUnit('<span>')\n"
        "env.Build('angle_app', ['apps/angle_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "angle_app")
    assert any(
        path.name.startswith("header--angle--span") and path.suffix in (".gcm", ".pcm", ".ifc")
        for path in build_files(project)
    )


def test_library_with_named_module(tmp_path):
    """BuildStaticLib + Build consumer share the same env BMI registry."""
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildStaticLib('mathlib', ['math.cppm'])\n"
        "env.AppendUnique(LIBPATH=[env['abs_final_dir']])\n"
        "env.Build('math_lib_app', ['apps/main.cpp'], LIBS=['mathlib'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "math_lib_app")
    static_libs = [
        path for path in find_under_build(project, "*mathlib*")
        if path.suffix in (".a", ".lib") and "final" in path.parts
    ]
    assert static_libs


def test_module_sugar_build(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Module('math', interface='math.cppm')\n"
        "env.Build('math_sugar_app', ['apps/main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "math_sugar_app")


def test_cxxm_interface_smoke(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('cxxm_app', ['math.cxxm', 'apps/cxxm_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "cxxm_app")


def test_unresolved_import_fails(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('broken_app', ['apps/main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_failure(result)
    assert "Unresolved C++ module imports" in result.stdout


def test_partition_incremental_rebuild(tmp_path):
    """Touching a partition interface should rebuild primary BMI and consumer object."""
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('geo_app', [\n"
        "    'geo/geo.cppm',\n"
        "    'geo/point.cppm',\n"
        "    'apps/geo_main.cpp',\n"
        "])\n",
    )
    assert_success(run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag))

    def _bmi_named(stem):
        matches = [
            path for path in build_files(project)
            if path.stem == stem and path.suffix in (".gcm", ".pcm", ".ifc")
        ]
        assert matches, "missing BMI for {}".format(stem)
        return matches[0]

    def _object_named(name):
        matches = [
            path for path in build_files(project)
            if path.stem == name and path.suffix in (".o", ".obj")
        ]
        assert matches, "missing object for {}".format(name)
        return matches[0]

    primary = _bmi_named("geo")
    partition = _bmi_named("geo--point")
    consumer = _object_named("geo_main")
    before = {
        "primary": primary.stat().st_mtime_ns,
        "partition": partition.stat().st_mtime_ns,
        "consumer": consumer.stat().st_mtime_ns,
    }

    import time
    time.sleep(1.1)
    point = project / "geo" / "point.cppm"
    point.write_text(point.read_text() + "\n// touch for rebuild\n")

    assert_success(run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag))
    after_partition = partition.stat().st_mtime_ns
    after_primary = primary.stat().st_mtime_ns
    after_consumer = consumer.stat().st_mtime_ns
    assert after_partition > before["partition"]
    assert after_primary > before["primary"]
    assert after_consumer > before["consumer"]


def test_import_std_build(tmp_path):
    alias, toolchain_flag, extra = _require_import_std_toolchain()
    logger.info("import std test using %s", alias)
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('std_app', ['apps/std_main.cpp'])\n",
    )
    result = run_cuppa(
        project,
        "--dbg",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        *extra,
        timeout=300,
    )
    assert_success(result)
    assert find_final_binaries(project, "std_app")
    assert any(
        path.stem == "std" and path.suffix in (".gcm", ".pcm", ".ifc")
        for path in build_files(project)
    )


def test_import_std_compat_build(tmp_path):
    alias, toolchain_flag, extra = _require_import_std_toolchain()
    logger.info("import std.compat test using %s", alias)
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('std_compat_app', ['apps/std_compat_main.cpp'])\n",
    )
    result = run_cuppa(
        project,
        "--dbg",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        *extra,
        timeout=300,
    )
    assert_success(result)
    assert find_final_binaries(project, "std_compat_app")
    assert any(
        path.stem in ("std.compat", "std--compat") and path.suffix in (".gcm", ".pcm", ".ifc")
        for path in build_files(project)
    )


def test_shared_library_with_named_module(tmp_path):
    """Shared lib + consumer. On MSVC, MATH_DLL_EXPORT enables dllexport in math.cppm
    so the linker emits an import library."""
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPDEFINES=['MATH_DLL_EXPORT'])\n"
        "env.BuildSharedLib('mathlib_shared', ['math.cppm'])\n"
        "env.AppendUnique(LIBPATH=[env['abs_final_dir']])\n"
        "env.AppendUnique(RPATH=[env['abs_final_dir']])\n"
        "env.Build('math_shared_app', ['apps/main.cpp'], LIBS=['mathlib_shared'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "math_shared_app")
    shared_libs = [
        path for path in find_under_build(project, "*mathlib_shared*")
        if path.suffix in (".so", ".dylib", ".dll") and "final" in path.parts
    ]
    assert shared_libs


def test_ccm_interface_smoke(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('ccm_app', ['math.ccm', 'apps/ccm_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "ccm_app")


def test_ixx_interface_smoke(tmp_path):
    """MSVC-style .ixx interface suffix (registered in MODULE_SOURCE_SUFFIXES)."""
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('ixx_app', ['math.ixx', 'apps/ixx_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "ixx_app")


def test_cpp_export_module_smoke(tmp_path):
    _, toolchain_flag = _modules_toolchain_flag()
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('cpp_iface_app', ['math_iface.cpp', 'apps/cpp_iface_main.cpp'])\n",
    )
    result = run_cuppa(project, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(project, "cpp_iface_app")


def test_modules_coverage_probe(tmp_path):
    """Smoke that --cov --modules can compile a named-module binary (gcc/clang only)."""
    import os
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        pytest.skip("coverage is not supported for MSVC")
    alias, toolchain_flag = _modules_toolchain_flag()
    if not _is_gcc_family(alias):
        # Clang coverage works via llvm-cov; still worth a light probe.
        pass
    project = _copy_modules_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('cov_math_app', ['math.cppm', 'apps/main.cpp'])\n",
    )
    result = run_cuppa(
        project, "--cov", "--modules", "--stdcpp=c++20", toolchain_flag, timeout=300
    )
    assert_success(result)
    assert find_final_binaries(project, "cov_math_app")


def test_packaged_modules_install_and_import(tmp_path):
    """Producer installs BMIs under final/modules; a separate consumer loads the map."""
    _, toolchain_flag = _modules_toolchain_flag()
    producer = _copy_modules_project(tmp_path / "producer")
    write_sconstruct(producer)
    write_sconscript(
        producer,
        "Import('env')\n"
        "env.BuildStaticLib('mathlib', ['math.cppm'])\n",
    )
    assert_success(run_cuppa(producer, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag))
    module_maps = [
        path for path in find_under_build(producer)
        if path.name == "module-map.json"
    ]
    assert module_maps
    modules_dir = module_maps[0].parent
    lib_dir = modules_dir.parent
    assert (modules_dir / "module-map.json").is_file()

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    shutil.copy(MODULES_PROJECT / "apps" / "main.cpp", consumer / "main.cpp")
    write_sconstruct(consumer)
    write_sconscript(
        consumer,
        "Import('env')\n"
        "env.ImportModules({!r})\n"
        "env.AppendUnique(LIBPATH=[{!r}])\n"
        "env.Build('packaged_app', ['main.cpp'], LIBS=['mathlib'])\n"
        .format(str(modules_dir), str(lib_dir)),
    )
    result = run_cuppa(consumer, "--dbg", "--modules", "--stdcpp=c++20", toolchain_flag)
    assert_success(result)
    assert find_final_binaries(consumer, "packaged_app")
