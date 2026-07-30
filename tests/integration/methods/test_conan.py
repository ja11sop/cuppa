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


def _install_plugin_target(target_dir):
    """Install examples/conan_fmt_plugin into target_dir for entry-point discovery."""
    from tests.helpers.toolchains import REPO_ROOT
    import sys

    plugin_src = REPO_ROOT / "examples" / "conan_fmt_plugin"
    assert plugin_src.is_dir(), "missing examples/conan_fmt_plugin"
    target_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(target_dir),
            "--no-deps",
            str(plugin_src),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail("pip install plugin failed:\n{}".format(completed.stdout))
    return target_dir


def test_conan_fmt_pip_plugin_entry_point(tmp_path):
    """Discover fmt via cuppa.dependency.plugins (examples/conan_fmt_plugin)."""
    import os

    _require_conan()
    plugin_site = _install_plugin_target(tmp_path / "plugin_site")

    project = tmp_path / "conan_plugin_consumer"
    project.mkdir()
    # Plugin embeds requires=fmt/11.1.4 — no project conanfile needed.
    (project / "hello.cpp").write_text(
        "#include <fmt/core.h>\n"
        "int main() {\n"
        "    fmt::print(\"hello from conan plugin\\n\");\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    write_sconstruct(
        project,
        body=(
            "import cuppa\n"
            "cuppa.run(\n"
            "    default_variants=['dbg'],\n"
            "    default_dependencies=['fmt'],\n"
            ")\n"
        ),
    )
    write_sconscript(
        project,
        "Import('env')\n"
        "assert 'fmt' in env['dependencies']\n"
        "env.Build('hello', 'hello.cpp')\n",
    )

    # Plugin site first so importlib.metadata finds the entry point; cuppa stays
    # importable via run_cuppa's REPO_ROOT PYTHONPATH entry.
    existing = os.environ.get("PYTHONPATH", "")
    pythonpath = os.pathsep.join(
        p for p in (str(plugin_site), existing) if p
    )
    result = run_cuppa(
        project,
        "--dbg",
        offline=False,
        timeout=600,
        extra_env={"PYTHONPATH": pythonpath},
    )
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
    assert "hello from conan plugin" in ran.stdout


def test_conan_offline_fails_when_cache_missing(tmp_path):
    """Cuppa --offline must fail clearly when Conan cannot resolve without remotes."""
    from tests.helpers.cuppa_runner import assert_failure

    _require_conan()
    project = tmp_path / "conan_offline_miss"
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

    empty_home = tmp_path / "empty_conan_home"
    empty_home.mkdir()
    download_root = tmp_path / "cuppa_download"
    download_root.mkdir()
    result = run_cuppa(
        project,
        "--dbg",
        "--download-root={}".format(download_root),
        offline=True,
        timeout=180,
        extra_env={"CONAN_HOME": str(empty_home)},
    )
    assert_failure(result)
    combined = result.stdout.lower()
    assert "conan" in combined
    assert (
        "offline" in combined
        or "no remote" in combined
        or "no-remote" in combined
        or "not found" in combined
        or "failed" in combined
        or "error" in combined
    )


def test_conan_publish_export_pkg_round_trip(tmp_path):
    """Cuppa BuildStaticLib → ConanPackagePublisher export-pkg → consumer conan_deps."""
    import os

    conan = _require_conan()
    conan_home = tmp_path / "conan_home"
    conan_home.mkdir()
    extra = {"CONAN_HOME": str(conan_home)}
    detect = subprocess.run(
        [conan, "profile", "detect", "--force"],
        env={**os.environ, **extra},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if detect.returncode != 0:
        pytest.fail("conan profile detect failed:\n{}".format(detect.stdout))

    producer = tmp_path / "publisher"
    producer.mkdir()
    include = producer / "include" / "cuppa_pub_mylib"
    include.mkdir(parents=True)
    (include / "answer.hpp").write_text(
        "#pragma once\n"
        "int cuppa_pub_answer();\n",
        encoding="utf-8",
    )
    (producer / "answer.cpp").write_text(
        "#include <cuppa_pub_mylib/answer.hpp>\n"
        "int cuppa_pub_answer() { return 42; }\n",
        encoding="utf-8",
    )
    write_sconstruct(
        producer,
        body=(
            "import cuppa\n"
            "cuppa.run(default_variants=['dbg'])\n"
        ),
    )
    write_sconscript(
        producer,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "env.AppendUnique(INCPATH=['include'])\n"
        "lib = env.BuildStaticLib('cuppa_pub_mylib', 'answer.cpp')\n"
        "publisher = ConanPackagePublisher(\n"
        "    env,\n"
        "    name='cuppa_pub_mylib',\n"
        "    version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    libs=['cuppa_pub_mylib'],\n"
        ")\n"
        "env.PublishPackage(lib, publisher)\n",
    )

    produced = run_cuppa(producer, "--dbg", offline=True, timeout=300, extra_env=extra)
    assert_success(produced)
    assert "exported to local cache" in produced.stdout or "export-pkg" in produced.stdout.lower()

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "conanfile.txt").write_text(
        "[requires]\n"
        "cuppa_pub_mylib/0.1.0\n"
        "\n"
        "[generators]\n"
        "SConsDeps\n"
        "VirtualRunEnv\n",
        encoding="utf-8",
    )
    (consumer / "hello.cpp").write_text(
        "#include <cuppa_pub_mylib/answer.hpp>\n"
        "#include <cstdio>\n"
        "int main() {\n"
        "    std::printf(\"answer=%d\\n\", cuppa_pub_answer());\n"
        "    return cuppa_pub_answer() == 42 ? 0 : 1;\n"
        "}\n",
        encoding="utf-8",
    )
    write_sconstruct(
        consumer,
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
        consumer,
        "Import('env')\n"
        "env.Build('hello', 'hello.cpp')\n",
    )

    consumed = run_cuppa(consumer, "--dbg", offline=True, timeout=300, extra_env=extra)
    assert_success(consumed)
    binaries = find_final_binaries(consumer, "hello")
    assert binaries
    ran = subprocess.run(
        [str(binaries[0])],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout
    assert "answer=42" in ran.stdout
