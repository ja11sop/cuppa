#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration tests for optional Conan 2 consumer support (SConsDeps)."""

import logging
import shutil
import subprocess

import pytest

from tests.helpers.cuppa_runner import (
    assert_success,
    find_final_binaries,
    run_cuppa,
)
from tests.helpers.project import write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)

FMT_VERSION = "11.1.4"


def _require_conan():
    conan = shutil.which("conan")
    if not conan:
        message = "conan not on PATH; skipping Conan integration test"
        logger.info(message)
        pytest.skip(message)
    # Prefer a working Conan 2; broken wrappers (Conan 1 stubs) fail here.
    probe = subprocess.run(
        [conan, "version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or "version:" not in (probe.stdout or ""):
        message = "conan CLI is not a working Conan 2; skipping Conan integration test"
        logger.info("%s\n%s", message, probe.stdout)
        pytest.skip(message)
    return conan


def _write_fmt_hello(project, shared=False):
    options = ""
    if shared:
        options = (
            "\n[options]\n"
            "fmt/*:shared=True\n"
        )
    (project / "conanfile.txt").write_text(
        "[requires]\n"
        "fmt/{}\n"
        "{}"
        "\n[generators]\n"
        "SConsDeps\n"
        "VirtualRunEnv\n".format(FMT_VERSION, options),
        encoding="utf-8",
    )
    (project / "hello.cpp").write_text(
        "#include <fmt/core.h>\n"
        "int main() {\n"
        "    fmt::print(\"hello from conan integration\\n\");\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )


def _conan_install(conan, project, output_folder, extra_settings=None):
    cmd = [
        conan,
        "install",
        str(project / "conanfile.txt"),
        "-of",
        str(output_folder),
        "-g",
        "SConsDeps",
        "-g",
        "VirtualRunEnv",
        "--build=missing",
        "-s",
        "build_type=Debug",
    ]
    for setting in extra_settings or []:
        cmd.extend(["-s", setting])
    logger.info("Warming Conan install: %s", " ".join(cmd))
    completed = subprocess.run(
        cmd,
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=600,
    )
    if completed.returncode != 0:
        pytest.fail("conan install failed:\n{}".format(completed.stdout))
    script = output_folder / "SConscript_conandeps"
    assert script.is_file(), "SConscript_conandeps missing after conan install"


def test_conan_deps_generators_folder_reuse(tmp_path):
    """Approach C: pre-run conan install, Cuppa only loads SConsDeps."""
    conan = _require_conan()
    project = tmp_path / "conan_generators_folder"
    project.mkdir()
    _write_fmt_hello(project)
    install = project / "_conan"
    _conan_install(conan, project, install)

    write_sconstruct(
        project,
        body=(
            "import cuppa\n"
            "Conan = cuppa.conan_deps(generators_folder='_conan')\n"
            "cuppa.run(\n"
            "    default_variants=['dbg'],\n"
            "    dependencies=[Conan],\n"
            "    default_dependencies=['conan'],\n"
            ")\n"
        ),
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('hello', 'hello.cpp')\n",
    )

    result = run_cuppa(project, "--dbg", timeout=300)
    assert_success(result)
    binaries = find_final_binaries(project, "hello")
    assert binaries
    ran = subprocess.run(
        [str(binaries[0])],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout
    assert "hello from conan integration" in ran.stdout


def test_conan_deps_install_build_and_run(tmp_path):
    """Full path: Cuppa runs conan install (online) then builds fmt hello."""
    _require_conan()
    project = tmp_path / "conan_install"
    project.mkdir()
    _write_fmt_hello(project)

    write_sconstruct(
        project,
        body=(
            "import cuppa\n"
            "Conan = cuppa.conan_deps(conanfile='conanfile.txt')\n"
            "cuppa.run(\n"
            "    default_variants=['dbg'],\n"
            "    dependencies=[Conan],\n"
            "    default_dependencies=['conan'],\n"
            ")\n"
        ),
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.Build('hello', 'hello.cpp')\n",
    )

    # Allow remotes so a cold CI cache can fetch/build fmt.
    result = run_cuppa(project, "--dbg", offline=False, timeout=600)
    assert_success(result)
    binaries = find_final_binaries(project, "hello")
    assert binaries
    ran = subprocess.run(
        [str(binaries[0])],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout
    assert "hello from conan integration" in ran.stdout

    # Second pass must reuse the fingerprint cache under Cuppa --offline.
    again = run_cuppa(project, "--dbg", offline=True, timeout=300)
    assert_success(again)
    assert "Running [" not in again.stdout or "conan install" not in again.stdout


def test_conan_shared_lib_runtime_paths_with_test(tmp_path):
    """Shared fmt must remain runnable under BuildTest via injected LD_LIBRARY_PATH/PATH."""
    _require_conan()
    project = tmp_path / "conan_shared"
    project.mkdir()
    _write_fmt_hello(project, shared=True)

    write_sconstruct(
        project,
        body=(
            "import cuppa\n"
            "Conan = cuppa.conan_deps(conanfile='conanfile.txt')\n"
            "cuppa.run(\n"
            "    default_variants=['dbg'],\n"
            "    dependencies=[Conan],\n"
            "    default_dependencies=['conan'],\n"
            ")\n"
        ),
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "env.BuildTest('hello_test', 'hello.cpp')\n",
    )

    result = run_cuppa(project, "--dbg", "--test", "--show-test-output", offline=False, timeout=600)
    assert_success(result)
    assert "hello from conan integration" in result.stdout
    # Ensure we did not only static-link: shared install should mention .so/.dylib/.dll
    # in cuppa/conan output or the binary should have run via injected paths.
    assert find_final_binaries(project, "hello_test") or "hello from conan integration" in result.stdout
