#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Two Cuppa --rel processes: second should not re-archive or re-link (#262).

Minimal static-lib + BuildTest tree. Passed on pre-parity GCC; kept as a
regression guard for gcc-ar / -ffat-lto-objects and Clang's matching story.
Does not claim a large consumer re-link is fixed.
"""

import logging
import os
import re

import pytest

from tests.helpers.cuppa_runner import assert_success, find_under_build, run_cuppa
from tests.helpers.project import write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


def _skip_if_msvc():
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        message = "MSVC has no Cuppa GCC/Clang LTO path; skipping --rel LTO incremental test"
        logger.warning(message)
        pytest.skip(message)


def _write_lto_shared_lib_project(project):
    """Static lib linked by two BuildTest binaries (shared .a is the interesting case)."""
    (project / "lib").mkdir()
    (project / "tests").mkdir()
    (project / "lib" / "answer.cpp").write_text(
        "int answer()\n"
        "{\n"
        "    return 42;\n"
        "}\n",
        encoding="utf-8",
    )
    for name in ("alpha_test", "beta_test"):
        (project / "tests" / "{}.cpp".format(name)).write_text(
            "int answer();\n"
            "int main()\n"
            "{\n"
            "    return answer() == 42 ? 0 : 1;\n"
            "}\n",
            encoding="utf-8",
        )
    write_sconstruct(project, default_variants=["rel"])
    write_sconscript(
        project,
        "Import('env')\n"
        "lib = env.BuildStaticLib('answer', 'lib/answer.cpp')\n"
        "env.AppendUnique(LIBPATH=[env['abs_final_dir']])\n"
        "alpha = env.BuildTest('alpha_test', 'tests/alpha_test.cpp', LIBS=[lib])\n"
        "beta = env.BuildTest('beta_test', 'tests/beta_test.cpp', LIBS=[lib])\n"
        "env.Depends(alpha, lib)\n"
        "env.Depends(beta, lib)\n",
    )


def _final_artefacts(project):
    binaries = []
    archives = []
    for path in find_under_build(project):
        if "final" not in path.parts or not path.is_file():
            continue
        if path.suffix in (".a", ".lib"):
            archives.append(path)
        elif path.suffix in ("", ".exe") or path.name in ("alpha_test", "beta_test"):
            if path.suffix in (".stdout.log", ".stderr.log", ".success", ".json"):
                continue
            if path.name.endswith(".stdout.log") or path.name.endswith(".stderr.log"):
                continue
            if ".report." in path.name or path.name.endswith(".success"):
                continue
            if path.name.startswith("alpha_test") or path.name.startswith("beta_test"):
                if path.suffix in ("", ".exe"):
                    binaries.append(path)
    return sorted(binaries), sorted(archives)


def _mtime_map(paths):
    return {str(path): path.stat().st_mtime_ns for path in paths}


def _rebuild_lines(stdout):
    """Return stdout lines that look like compile/archive/link work (not Progress)."""
    lines = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Progress(") or stripped.startswith("scons:"):
            continue
        if stripped.startswith("cuppa:"):
            continue
        if "Starting Test Suite" in stripped or "Test [" in stripped:
            continue
        if "= PASSED =" in stripped or "= FAILED =" in stripped:
            continue
        if "Time: Wall" in stripped:
            continue
        # Colourised paths aside, builders usually show the tool name early.
        if re.search(
            r"(^|/|\s)(g\+\+|clang\+\+|gcc-ar|llvm-ar|ar\b|ranlib\b|lib\.exe)",
            stripped,
        ):
            lines.append(stripped)
        elif " -o " in stripped and "/final/" in stripped.replace("\\", "/"):
            lines.append(stripped)
        elif " -c " in stripped and (".o " in stripped or ".o$" in stripped or stripped.endswith(".o")):
            lines.append(stripped)
    return lines


def test_rel_lto_second_invocation_does_not_relink(tmp_path):
    """Two Cuppa --rel processes: second should not re-archive or re-link (#262).

    Guard for release LTO tooling. Minimal trees may already be incremental;
    consumer re-links still need ``--debug=explain`` on the affected project.
    """
    _skip_if_msvc()

    project = tmp_path / "lto_incremental"
    project.mkdir()
    _write_lto_shared_lib_project(project)

    first = run_cuppa(project, "--rel", "--parallel", timeout=300)
    assert_success(first)

    binaries, archives = _final_artefacts(project)
    assert archives, "expected a static archive under final/"
    assert len(binaries) >= 2, "expected alpha_test and beta_test under final/, got {}".format(
        binaries
    )

    before_bin = _mtime_map(binaries)
    before_ar = _mtime_map(archives)

    second = run_cuppa(project, "--rel", "--test", timeout=300)
    assert_success(second)

    rebuild = _rebuild_lines(second.stdout)
    after_bin = _mtime_map(binaries)
    after_ar = _mtime_map(archives)

    changed_binaries = [path for path, mtime in before_bin.items() if after_bin.get(path) != mtime]
    changed_archives = [path for path, mtime in before_ar.items() if after_ar.get(path) != mtime]

    if rebuild or changed_binaries or changed_archives:
        logger.warning(
            "Second --rel --test was not fully incremental (spike for #262).\n"
            "rebuild lines (%s):\n%s\nchanged binaries: %s\nchanged archives: %s\n"
            "stdout tail:\n%s",
            len(rebuild),
            "\n".join(rebuild[:40]),
            changed_binaries,
            changed_archives,
            "\n".join(second.stdout.splitlines()[-80:]),
        )

    assert not changed_archives, (
        "static archive mtime changed on second --rel --test: {}".format(changed_archives)
    )
    assert not changed_binaries, (
        "test binary mtime changed on second --rel --test: {}".format(changed_binaries)
    )
    assert not rebuild, (
        "second --rel --test recompiled/archived/linked:\n{}".format("\n".join(rebuild))
    )
