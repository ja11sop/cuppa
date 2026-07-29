import logging
import os
import sys
import subprocess
from pathlib import Path

from tests.helpers.toolchains import REPO_ROOT, default_toolchain_flags, require_cxx

logger = logging.getLogger(__name__)


def _split_extra_args(extra_args):
    return [part for part in extra_args.split() if part]


def _option_key(arg):
    """Return the option name for --foo / --foo=bar style args, else None."""
    if not isinstance(arg, str) or not arg.startswith("--"):
        return None
    return arg.split("=", 1)[0]


def merge_cuppa_args(*flag_groups):
    """
    Merge cuppa CLI flag groups left-to-right.

    Later groups win for the same option key (e.g. --clang-stdlib=), so an
    explicit test flag overrides CUPPA_TEST_ARGS defaults from CI/env.
    """
    merged = []
    seen = {}
    for group in flag_groups:
        for flag in group:
            key = _option_key(flag)
            if key is None:
                merged.append(flag)
                continue
            if key in seen:
                merged[seen[key]] = flag
            else:
                seen[key] = len(merged)
                merged.append(flag)
    return merged


def cuppa_test_env_args():
    """Optional CI/local extras from CUPPA_TEST_ARGS (e.g. --clang-stdlib=libc++)."""
    return _split_extra_args(os.environ.get("CUPPA_TEST_ARGS", "").strip())


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
    default_tc = []
    if not any(str(flag).startswith("--toolchains") for flag in flags):
        default_tc = default_toolchain_flags()

    # Env extras first; explicit *flags override (e.g. import std forcing libc++).
    args.extend(merge_cuppa_args(default_tc, cuppa_test_env_args(), list(flags)))

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


def build_files(project_dir):
    """Return all regular files under `_build/` (empty dirs are ignored)."""
    return [path for path in find_under_build(project_dir) if path.is_file()]


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
