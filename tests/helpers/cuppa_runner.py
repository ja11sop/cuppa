import logging
import os
import sys
import subprocess
from pathlib import Path

from tests.helpers.toolchains import REPO_ROOT, default_toolchain_flags, require_cxx

logger = logging.getLogger(__name__)


def run_cuppa(project_dir, *flags, extra_env=None, timeout=180):
    require_cxx()
    env = os.environ.copy()
    pythonpath = str(REPO_ROOT)
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath
    if extra_env:
        env.update(extra_env)

    args = [sys.executable, "-m", "cuppa", "-D", "--offline"]
    if not any(str(flag).startswith("--toolchains") for flag in flags):
        args.extend(default_toolchain_flags())
    args.extend(flags)

    logger.info("Running in %s: %s", project_dir, " ".join(args))
    result = subprocess.run(
        args,
        cwd=str(project_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        text=True,
    )
    if result.returncode != 0:
        logger.info("cuppa output (exit %s):\n%s", result.returncode, result.stdout)
    return result


def assert_success(result):
    assert result.returncode == 0, "cuppa failed:\n{}".format(result.stdout)


def assert_failure(result):
    assert result.returncode != 0, "cuppa unexpectedly succeeded:\n{}".format(result.stdout)


def find_under_build(project_dir, pattern="*"):
    build_root = Path(project_dir) / "_build"
    if not build_root.exists():
        return []
    return sorted(build_root.rglob(pattern))


def find_final_binaries(project_dir, name):
    """Find built programs under final/; accept Windows PROGSUFFIX (.exe)."""
    patterns = [name]
    if not name.lower().endswith(".exe"):
        patterns.append(name + ".exe")
    matches = []
    for pattern in patterns:
        for path in find_under_build(project_dir, pattern):
            if "final" in path.parts and path.is_file():
                matches.append(path)
    return matches
