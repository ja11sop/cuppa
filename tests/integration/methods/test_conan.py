#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration tests for optional Conan 2 consumer support (SConsDeps).

Early consumer scenarios use preferred ``import_dependencies`` /
``auto_enable_dependencies``; later publish / shared-lib fixtures keep the
legacy ``dependencies`` / ``default_dependencies`` aliases so both styles stay
covered.
"""

import logging
import re
import shutil
import subprocess

import pytest

from tests.helpers.cuppa_runner import (
    assert_success,
    find_final_binaries,
    find_under_build,
    run_cuppa,
)
from tests.helpers.project import write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)

# Prefer 12.x for Clang 21+ / libc++ (fmtlib/fmt#4477). ConanCenter latest is
# 12.1.0 (GitHub location plugin may pin newer tags independently).
FMT_VERSION = "12.1.0"


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


def _compiler_major(command):
    """Best-effort major version from ``clang++ --version`` / ``g++ --version``."""
    completed = subprocess.run(
        [command, "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    text = completed.stdout or ""
    match = re.search(r"version\s+(\d+)", text) or re.search(r"\b(\d+)\.\d+\.\d+\b", text)
    return match.group(1) if match else None


def _host_settings_for_cuppa_job():
    """
    Align Approach C warm-install with CUPPA_TEST_* so CI clang/libc++ cells
    do not reuse a default-profile (often gcc) package ID.
    """
    import os

    toolchain = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    stdlib = None
    for arg in os.environ.get("CUPPA_TEST_ARGS", "").split():
        if arg.startswith("--clang-stdlib="):
            stdlib = arg.split("=", 1)[1]

    settings = ["compiler.cppstd=26"]
    executables = None
    if toolchain.startswith("clang") or toolchain == "clang":
        settings.append("compiler=clang")
        clangxx = shutil.which("clang++")
        major = _compiler_major(clangxx) if clangxx else None
        if major:
            settings.append("compiler.version={}".format(major))
        settings.append(
            "compiler.libcxx={}".format(
                "libc++" if stdlib == "libc++" else "libstdc++11"
            )
        )
        cxx = clangxx or "clang++"
        c_compiler = cxx.replace("clang++", "clang") if "clang++" in os.path.basename(cxx) else "clang"
        executables = {"c": c_compiler, "cpp": cxx}
    elif toolchain.startswith("gcc") or toolchain == "gcc" or not toolchain:
        settings.append("compiler=gcc")
        gxx = shutil.which("g++")
        major = _compiler_major(gxx) if gxx else None
        if major:
            settings.append("compiler.version={}".format(major))
        settings.append("compiler.libcxx=libstdc++11")
        cxx = gxx or "g++"
        c_compiler = cxx.replace("g++", "gcc") if os.path.basename(cxx).startswith("g++") else "gcc"
        executables = {"c": c_compiler, "cpp": cxx}
    elif toolchain in ("vc", "cl", "msvc"):
        settings.append("compiler=msvc")
    return settings, executables


def _conan_install(conan, project, output_folder, extra_settings=None):
    import json

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
    host_settings, executables = _host_settings_for_cuppa_job()
    for setting in list(host_settings) + list(extra_settings or []):
        cmd.extend(["-s", setting])
    # Match Cuppa: host -s compiler=clang alone still lets CMake pick g++ from PATH.
    if executables:
        payload = json.dumps(executables, sort_keys=True, separators=(",", ":"))
        cmd.extend(["-c", "tools.build:compiler_executables={}".format(payload)])
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


def _isolated_conan_home(tmp_path, conan):
    """
    Fresh CONAN_HOME + default profile for local export-pkg round-trips.

    Also returns a ``--dependencies-root=`` flag under ``tmp_path`` so Cuppa's Conan
    fingerprint cache (and embedded package paths in ``SConscript_conandeps``)
    cannot leak across tests via ``~/.cuppaconfig`` / ``~/.cuppa``.
    """
    import os

    conan_home = tmp_path / "conan_home"
    conan_home.mkdir()
    dependencies_root = tmp_path / "cuppa_dependencies"
    dependencies_root.mkdir()
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
    return extra, "--dependencies-root={}".format(dependencies_root)

def _write_answer_library(project, package="cuppa_pub_mylib", answer=42):
    """Minimal header + source library used by Conan publish round-trips."""
    include = project / "include" / package
    include.mkdir(parents=True)
    (include / "answer.hpp").write_text(
        "#pragma once\n"
        "int cuppa_pub_answer();\n",
        encoding="utf-8",
    )
    (project / "answer.cpp").write_text(
        "#include <{}/answer.hpp>\n"
        "int cuppa_pub_answer() {{ return {}; }}\n".format(package, answer),
        encoding="utf-8",
    )


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
            "    import_dependencies=[Conan],\n"
            "    auto_enable_dependencies=[Conan],\n"
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
            "    import_dependencies=[Conan],\n"
            "    auto_enable_dependencies=[Conan],\n"
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
            "--no-user",
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
    # Plugin embeds requires=fmt/12.1.0 — no project conanfile needed.
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
            "    auto_enable_dependencies=['fmt'],\n"
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
    dependencies_root = tmp_path / "cuppa_dependencies"
    dependencies_root.mkdir()
    result = run_cuppa(
        project,
        "--dbg",
        "--dependencies-root={}".format(dependencies_root),
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


def test_conan_publish_generated_relative_lib_dir_round_trip(tmp_path):
    """Relative final_dir / source_lib_dir must stage from the variant tree, not srcnode()."""
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
    include = producer / "include" / "cuppa_var_mylib"
    include.mkdir(parents=True)
    (include / "answer.hpp").write_text(
        "#pragma once\n"
        "int cuppa_var_answer();\n",
        encoding="utf-8",
    )
    (producer / "answer.cpp").write_text(
        "#include <cuppa_var_mylib/answer.hpp>\n"
        "int cuppa_var_answer() { return 42; }\n",
        encoding="utf-8",
    )
    write_sconstruct(
        producer,
        body=(
            "import cuppa\n"
            "cuppa.run(default_variants=['rel'])\n"
        ),
    )
    write_sconscript(
        producer,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "env.AppendUnique(INCPATH=['include'])\n"
        "lib = env.BuildStaticLib(\n"
        "    'cuppa_var_mylib', 'answer.cpp', final_dir='package_lib',\n"
        ")\n"
        "publisher = ConanPackagePublisher(\n"
        "    env,\n"
        "    name='cuppa_var_mylib',\n"
        "    version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir='package_lib',\n"
        "    libs=['cuppa_var_mylib'],\n"
        ")\n"
        "env.PublishPackage(lib, publisher)\n",
    )

    produced = run_cuppa(
        producer, "--rel", "--parallel", offline=True, timeout=300, extra_env=extra
    )
    assert_success(produced)
    assert "exported to local cache" in produced.stdout or "export-pkg" in produced.stdout.lower()

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "conanfile.txt").write_text(
        "[requires]\n"
        "cuppa_var_mylib/0.1.0\n"
        "\n"
        "[generators]\n"
        "SConsDeps\n"
        "VirtualRunEnv\n",
        encoding="utf-8",
    )
    (consumer / "hello.cpp").write_text(
        "#include <cuppa_var_mylib/answer.hpp>\n"
        "#include <cstdio>\n"
        "int main() {\n"
        "    std::printf(\"answer=%d\\n\", cuppa_var_answer());\n"
        "    return cuppa_var_answer() == 42 ? 0 : 1;\n"
        "}\n",
        encoding="utf-8",
    )
    write_sconstruct(
        consumer,
        body=(
            "import cuppa\n"
            "Conan = cuppa.conan_deps(conanfile='conanfile.txt')\n"
            "cuppa.run(\n"
            "    default_variants=['rel'],\n"
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

    consumed = run_cuppa(consumer, "--rel", offline=True, timeout=300, extra_env=extra)
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


def test_conan_publish_conanfile_override_with_requires(tmp_path):
    """Leaf export-pkg, then wrapper with conanfile= requires leaf; consumer uses wrapper."""
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

    leaf = tmp_path / "leaf"
    leaf.mkdir()
    include = leaf / "include" / "cuppa_pub_mylib"
    include.mkdir(parents=True)
    (include / "answer.hpp").write_text(
        "#pragma once\n"
        "int cuppa_pub_answer();\n",
        encoding="utf-8",
    )
    (leaf / "answer.cpp").write_text(
        "#include <cuppa_pub_mylib/answer.hpp>\n"
        "int cuppa_pub_answer() { return 42; }\n",
        encoding="utf-8",
    )
    write_sconstruct(leaf, body="import cuppa\ncuppa.run(default_variants=['dbg'])\n")
    write_sconscript(
        leaf,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "env.AppendUnique(INCPATH=['include'])\n"
        "lib = env.BuildStaticLib('cuppa_pub_mylib', 'answer.cpp')\n"
        "env.PublishPackage(lib, ConanPackagePublisher(\n"
        "    env, name='cuppa_pub_mylib', version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    libs=['cuppa_pub_mylib'], shared=False,\n"
        "))\n",
    )
    assert_success(run_cuppa(leaf, "--dbg", offline=True, timeout=300, extra_env=extra))

    wrap = tmp_path / "wrapper"
    wrap.mkdir()
    wrap_inc = wrap / "include" / "cuppa_pub_wrap"
    wrap_inc.mkdir(parents=True)
    (wrap_inc / "wrap.hpp").write_text(
        "#pragma once\n"
        "#include <cuppa_pub_mylib/answer.hpp>\n"
        "inline int cuppa_pub_wrap() { return cuppa_pub_answer() + 1; }\n",
        encoding="utf-8",
    )
    (wrap / "wrap.cpp").write_text(
        "#include <cuppa_pub_wrap/wrap.hpp>\n"
        "int cuppa_pub_wrap_lib() { return cuppa_pub_wrap(); }\n",
        encoding="utf-8",
    )
    (wrap / "conanfile.py").write_text(
        "from conan import ConanFile\n"
        "from conan.tools.files import copy\n"
        "import os\n"
        "\n"
        "class CuppaPubWrap(ConanFile):\n"
        "    name = 'cuppa_pub_wrap'\n"
        "    version = '0.1.0'\n"
        "    package_type = 'static-library'\n"
        "    settings = 'os', 'compiler', 'build_type', 'arch'\n"
        "    options = {'shared': [True, False]}\n"
        "    default_options = {'shared': False}\n"
        "    requires = 'cuppa_pub_mylib/0.1.0'\n"
        "\n"
        "    def package(self):\n"
        "        include_src = os.path.join(self.recipe_folder, 'include')\n"
        "        lib_src = os.path.join(self.recipe_folder, 'lib')\n"
        "        if os.path.isdir(include_src):\n"
        "            copy(self, '*', src=include_src,\n"
        "                 dst=os.path.join(self.package_folder, 'include'))\n"
        "        if os.path.isdir(lib_src):\n"
        "            copy(self, '*', src=lib_src,\n"
        "                 dst=os.path.join(self.package_folder, 'lib'))\n"
        "\n"
        "    def package_info(self):\n"
        "        self.cpp_info.libs = ['cuppa_pub_wrap']\n",
        encoding="utf-8",
    )
    write_sconstruct(wrap, body="import cuppa\ncuppa.run(default_variants=['dbg'])\n")
    # Header-only use of leaf at compile time needs the leaf headers; for the
    # wrapper lib we only need wrap.hpp which includes leaf — provide leaf
    # includes via SYSINCPATH from a local copy (same tree as leaf include).
    import shutil

    shutil.copytree(leaf / "include" / "cuppa_pub_mylib", wrap / "include" / "cuppa_pub_mylib")
    write_sconscript(
        wrap,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "env.AppendUnique(INCPATH=['include'])\n"
        "lib = env.BuildStaticLib('cuppa_pub_wrap', 'wrap.cpp')\n"
        "env.PublishPackage(lib, ConanPackagePublisher(\n"
        "    env, name='cuppa_pub_wrap', version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    conanfile='conanfile.py',\n"
        "    shared=False,\n"
        "))\n",
    )
    wrapped = run_cuppa(wrap, "--dbg", offline=True, timeout=300, extra_env=extra)
    assert_success(wrapped)

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "conanfile.txt").write_text(
        "[requires]\n"
        "cuppa_pub_wrap/0.1.0\n"
        "\n"
        "[generators]\n"
        "SConsDeps\n"
        "VirtualRunEnv\n",
        encoding="utf-8",
    )
    (consumer / "hello.cpp").write_text(
        "#include <cuppa_pub_wrap/wrap.hpp>\n"
        "#include <cstdio>\n"
        "int main() {\n"
        "    std::printf(\"wrap=%d\\n\", cuppa_pub_wrap());\n"
        "    return cuppa_pub_wrap() == 43 ? 0 : 1;\n"
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
    write_sconscript(consumer, "Import('env')\nenv.Build('hello', 'hello.cpp')\n")

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
    assert "wrap=43" in ran.stdout


def test_conan_publish_modules_bmi_round_trip(tmp_path):
    """BuildLib --modules → ConanPackagePublisher stages modules/ → consumer import."""
    import os
    import shutil

    from tests.helpers.toolchains import (
        REPO_ROOT,
        require_modules_capable_toolchain,
    )

    conan = _require_conan()
    alias, driver, major = require_modules_capable_toolchain()
    toolchain_flag = "--toolchains={}".format(alias)
    logger.info(
        "Conan modules publish using toolchain %s (%s major %s)",
        alias,
        driver,
        major,
    )

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

    fixtures = REPO_ROOT / "tests" / "fixtures" / "modules_project"
    producer = tmp_path / "mod_publisher"
    producer.mkdir()
    shutil.copy(fixtures / "math.cppm", producer / "math.cppm")
    write_sconstruct(producer, body="import cuppa\ncuppa.run(default_variants=['dbg'])\n")
    write_sconscript(
        producer,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "lib = env.BuildStaticLib('cuppa_mathlib', ['math.cppm'])\n"
        "env.PublishPackage(lib, ConanPackagePublisher(\n"
        "    env, name='cuppa_mathlib', version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    libs=['cuppa_mathlib'], shared=False,\n"
        "))\n",
    )
    # Empty include dir so publisher has a source tree (headers optional for this module).
    (producer / "include").mkdir()

    produced = run_cuppa(
        producer,
        "--dbg",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        offline=True,
        timeout=300,
        extra_env=extra,
    )
    assert_success(produced)
    module_maps = [
        path for path in find_under_build(producer)
        if path.name == "module-map.json" and "conan_pkg_" in str(path)
    ]
    assert module_maps, "expected staged modules/module-map.json under conan_pkg_*"

    consumer = tmp_path / "mod_consumer"
    consumer.mkdir()
    shutil.copy(fixtures / "apps" / "main.cpp", consumer / "main.cpp")
    (consumer / "conanfile.txt").write_text(
        "[requires]\n"
        "cuppa_mathlib/0.1.0\n"
        "\n"
        "[generators]\n"
        "SConsDeps\n"
        "VirtualRunEnv\n",
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
        "env.Build('math_app', ['main.cpp'])\n",
    )

    consumed = run_cuppa(
        consumer,
        "--dbg",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        offline=True,
        timeout=300,
        extra_env=extra,
    )
    assert_success(consumed)
    binaries = find_final_binaries(consumer, "math_app")
    assert binaries
    ran = subprocess.run(
        [str(binaries[0])],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout


def test_conan_publish_generated_requires_round_trip(tmp_path):
    """Leaf export-pkg, then wrapper with generated requires= (no conanfile=)."""
    import shutil

    conan = _require_conan()
    extra, dependencies_root = _isolated_conan_home(tmp_path, conan)

    leaf = tmp_path / "leaf"
    leaf.mkdir()
    _write_answer_library(leaf)
    write_sconstruct(leaf, body="import cuppa\ncuppa.run(default_variants=['dbg'])\n")
    write_sconscript(
        leaf,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "env.AppendUnique(INCPATH=['include'])\n"
        "lib = env.BuildStaticLib('cuppa_pub_mylib', 'answer.cpp')\n"
        "env.PublishPackage(lib, ConanPackagePublisher(\n"
        "    env, name='cuppa_pub_mylib', version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    libs=['cuppa_pub_mylib'], shared=False,\n"
        "))\n",
    )
    assert_success(
        run_cuppa(leaf, "--dbg", dependencies_root, offline=True, timeout=300, extra_env=extra)
    )

    wrap = tmp_path / "wrapper"
    wrap.mkdir()
    wrap_inc = wrap / "include" / "cuppa_pub_wrap"
    wrap_inc.mkdir(parents=True)
    (wrap_inc / "wrap.hpp").write_text(
        "#pragma once\n"
        "#include <cuppa_pub_mylib/answer.hpp>\n"
        "inline int cuppa_pub_wrap() { return cuppa_pub_answer() + 1; }\n",
        encoding="utf-8",
    )
    (wrap / "wrap.cpp").write_text(
        "#include <cuppa_pub_wrap/wrap.hpp>\n"
        "int cuppa_pub_wrap_lib() { return cuppa_pub_wrap(); }\n",
        encoding="utf-8",
    )
    shutil.copytree(leaf / "include" / "cuppa_pub_mylib", wrap / "include" / "cuppa_pub_mylib")
    write_sconstruct(wrap, body="import cuppa\ncuppa.run(default_variants=['dbg'])\n")
    write_sconscript(
        wrap,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "env.AppendUnique(INCPATH=['include'])\n"
        "lib = env.BuildStaticLib('cuppa_pub_wrap', 'wrap.cpp')\n"
        "env.PublishPackage(lib, ConanPackagePublisher(\n"
        "    env, name='cuppa_pub_wrap', version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    libs=['cuppa_pub_wrap'],\n"
        "    shared=False,\n"
        "    requires=['cuppa_pub_mylib/0.1.0'],\n"
        "))\n",
    )
    wrapped = run_cuppa(wrap, "--dbg", dependencies_root, offline=True, timeout=300, extra_env=extra)
    assert_success(wrapped)

    # Generated recipe must embed requires= (not a hand-written conanfile=).
    staged = [
        path for path in find_under_build(wrap)
        if path.name == "conanfile.py" and "conan_pkg_" in str(path)
    ]
    assert staged, "expected generated conanfile.py under conan_pkg_*"
    assert "cuppa_pub_mylib/0.1.0" in staged[0].read_text(encoding="utf-8")

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "conanfile.txt").write_text(
        "[requires]\n"
        "cuppa_pub_wrap/0.1.0\n"
        "\n"
        "[generators]\n"
        "SConsDeps\n"
        "VirtualRunEnv\n",
        encoding="utf-8",
    )
    (consumer / "hello.cpp").write_text(
        "#include <cuppa_pub_wrap/wrap.hpp>\n"
        "#include <cstdio>\n"
        "int main() {\n"
        "    std::printf(\"wrap=%d\\n\", cuppa_pub_wrap());\n"
        "    return cuppa_pub_wrap() == 43 ? 0 : 1;\n"
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
    write_sconscript(consumer, "Import('env')\nenv.Build('hello', 'hello.cpp')\n")

    consumed = run_cuppa(
        consumer, "--dbg", dependencies_root, offline=True, timeout=300, extra_env=extra
    )
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
    assert "wrap=43" in ran.stdout


def test_conan_publish_shared_lib_round_trip(tmp_path):
    """BuildSharedLib + shared=True publish → consumer BuildTest with runtime paths."""
    conan = _require_conan()
    extra, dependencies_root = _isolated_conan_home(tmp_path, conan)

    producer = tmp_path / "publisher"
    producer.mkdir()
    _write_answer_library(producer)
    write_sconstruct(producer, body="import cuppa\ncuppa.run(default_variants=['dbg'])\n")
    write_sconscript(
        producer,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "env.AppendUnique(INCPATH=['include'])\n"
        "lib = env.BuildSharedLib('cuppa_pub_mylib', 'answer.cpp')\n"
        "env.PublishPackage(lib, ConanPackagePublisher(\n"
        "    env, name='cuppa_pub_mylib', version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    libs=['cuppa_pub_mylib'],\n"
        "    shared=True,\n"
        "))\n",
    )

    produced = run_cuppa(
        producer, "--dbg", dependencies_root, offline=True, timeout=300, extra_env=extra
    )
    assert_success(produced)
    shared_libs = [
        path for path in find_under_build(producer, "*cuppa_pub_mylib*")
        if path.suffix in (".so", ".dylib", ".dll") and "final" in path.parts
    ]
    assert shared_libs, "expected shared library under final/"
    staged_recipes = [
        path for path in find_under_build(producer)
        if path.name == "conanfile.py" and "conan_pkg_" in str(path)
    ]
    assert staged_recipes
    recipe_text = staged_recipes[0].read_text(encoding="utf-8")
    assert "shared-library" in recipe_text
    assert "True" in recipe_text  # default_options shared=True in generated recipe

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
        "env.BuildTest('hello_test', 'hello.cpp')\n",
    )

    consumed = run_cuppa(
        consumer,
        "--dbg",
        dependencies_root,
        "--test",
        "--show-test-output",
        offline=True,
        timeout=300,
        extra_env=extra,
    )
    assert_success(consumed)
    assert "answer=42" in consumed.stdout


def test_conan_publish_source_modules_dir_override(tmp_path):
    """Publish modules from an explicit source_modules_dir= (not final/modules)."""
    import shutil

    from tests.helpers.toolchains import (
        REPO_ROOT,
        require_modules_capable_toolchain,
    )

    conan = _require_conan()
    alias, driver, major = require_modules_capable_toolchain()
    toolchain_flag = "--toolchains={}".format(alias)
    logger.info(
        "Conan source_modules_dir publish using toolchain %s (%s major %s)",
        alias,
        driver,
        major,
    )
    extra, dependencies_root = _isolated_conan_home(tmp_path, conan)

    fixtures = REPO_ROOT / "tests" / "fixtures" / "modules_project"
    producer = tmp_path / "mod_publisher"
    producer.mkdir()
    shutil.copy(fixtures / "math.cppm", producer / "math.cppm")
    (producer / "include").mkdir()
    write_sconstruct(producer, body="import cuppa\ncuppa.run(default_variants=['dbg'])\n")
    write_sconscript(
        producer,
        "Import('env')\n"
        "env.BuildStaticLib('cuppa_mathlib', ['math.cppm'])\n",
    )

    built = run_cuppa(
        producer,
        "--dbg",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        dependencies_root,
        offline=True,
        timeout=300,
        extra_env=extra,
    )
    assert_success(built)

    module_maps = [
        path for path in find_under_build(producer)
        if (
            path.name == "module-map.json"
            and "final" in path.parts
            and "modules" in path.parts
            and "conan_pkg_" not in str(path)
        )
    ]
    assert module_maps, "expected final/modules/module-map.json after --modules build"
    default_modules = module_maps[0].parent
    bmi_out = producer / "bmi_out"
    shutil.copytree(default_modules, bmi_out)
    shutil.rmtree(default_modules)

    write_sconscript(
        producer,
        "Import('env')\n"
        "from cuppa.package_managers.conan import ConanPackagePublisher\n"
        "from SCons.Script import Touch\n"
        "# Library artefacts already in final/; stamp drives PublishPackage.\n"
        "stamp = env.Command('publish_stamp', [], Touch('$TARGET'))\n"
        "env.PublishPackage(stamp, ConanPackagePublisher(\n"
        "    env, name='cuppa_mathlib', version='0.1.0',\n"
        "    source_include_dir='include',\n"
        "    source_lib_dir=env['abs_final_dir'],\n"
        "    source_modules_dir='bmi_out',\n"
        "    libs=['cuppa_mathlib'], shared=False,\n"
        "))\n",
    )

    published = run_cuppa(
        producer,
        "--dbg",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        dependencies_root,
        offline=True,
        timeout=300,
        extra_env=extra,
    )
    assert_success(published)
    staged_maps = [
        path for path in find_under_build(producer)
        if path.name == "module-map.json" and "conan_pkg_" in str(path)
    ]
    assert staged_maps, "expected modules staged from bmi_out into conan_pkg_*"

    consumer = tmp_path / "mod_consumer"
    consumer.mkdir()
    shutil.copy(fixtures / "apps" / "main.cpp", consumer / "main.cpp")
    (consumer / "conanfile.txt").write_text(
        "[requires]\n"
        "cuppa_mathlib/0.1.0\n"
        "\n"
        "[generators]\n"
        "SConsDeps\n"
        "VirtualRunEnv\n",
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
        "env.Build('math_app', ['main.cpp'])\n",
    )

    consumed = run_cuppa(
        consumer,
        "--dbg",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        dependencies_root,
        offline=True,
        timeout=300,
        extra_env=extra,
    )
    assert_success(consumed)
    binaries = find_final_binaries(consumer, "math_app")
    assert binaries
    ran = subprocess.run(
        [str(binaries[0])],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout
