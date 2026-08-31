#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Integration test for examples/cuppa_fmt_plugin (location_dependency fmt)."""

import logging
import os
import subprocess
import sys

import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, run_cuppa
from tests.helpers.project import write_sconstruct, write_sconscript
from tests.helpers.toolchains import REPO_ROOT


pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


def _install_plugin_target(target_dir):
    plugin_src = REPO_ROOT / "examples" / "cuppa_fmt_plugin"
    assert plugin_src.is_dir(), "missing examples/cuppa_fmt_plugin"
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
        pytest.fail("pip install cuppa-fmt plugin failed:\n{}".format(completed.stdout))
    return target_dir


def test_fmt_location_pip_plugin_builds_static_lib(tmp_path):
    """Discover fmt via cuppa.dependency.plugins; build/link static lib from source."""
    plugin_site = _install_plugin_target(tmp_path / "plugin_site")

    project = tmp_path / "fmt_location_consumer"
    project.mkdir()
    (project / "hello.cpp").write_text(
        "#include <fmt/core.h>\n"
        "int main() {\n"
        "    fmt::print(\"hello from location fmt plugin\\n\");\n"
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

    existing = os.environ.get("PYTHONPATH", "")
    pythonpath = os.pathsep.join(p for p in (str(plugin_site), existing) if p)
    # First run may download the fmt archive (allow remotes / location fetch).
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
    assert "hello from location fmt plugin" in ran.stdout

    # Cached download should allow a subsequent --offline build.
    again = run_cuppa(
        project,
        "--dbg",
        offline=True,
        timeout=300,
        extra_env={"PYTHONPATH": pythonpath},
    )
    assert_success(again)
