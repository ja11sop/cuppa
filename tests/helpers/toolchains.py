import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Cuppa C++ modules floors (must match toolchain.supports_modules).
MODULES_MIN_GCC_MAJOR = 14
MODULES_MIN_CLANG_MAJOR = 16


def _msvc_available():
    """Return (name, path_or_token) if MSVC looks usable."""
    path = shutil.which("cl")
    if path:
        return "cl", path
    if os.name != "nt":
        return None
    try:
        from SCons.Tool.MSCommon.vc import get_installed_vcs
        if get_installed_vcs():
            return "cl", "msvc"
    except Exception:
        pass
    return None


def require_cxx():
    for name in ("g++", "clang++", "c++", "cl"):
        path = shutil.which(name)
        if path:
            return name, path
    msvc = _msvc_available()
    if msvc:
        return msvc
    message = "No C++ compiler (g++/clang++/c++/cl) found; skipping integration test"
    logger.warning(message)
    pytest.skip(message)


def _versioned_driver_probes(family):
    """
    Map a cuppa toolchain alias to PATH binaries to probe.

    Examples: gcc -> g++/gcc; gcc14 -> g++-14; clang18 -> clang++-18.
    """
    family = {
        "cl": "vc",
        "msvc": "vc",
    }.get(family, family)

    if family == "vc":
        return family, ()

    match = re.match(r"^(gcc|clang)(?P<ver>\d+)?$", family)
    if not match:
        return family, (family,)

    kind = match.group(1)
    ver = match.group("ver")
    if kind == "gcc":
        if not ver:
            return family, ("g++", "gcc")
        major = ver[:2] if len(ver) >= 2 and ver[0] != "0" else ver[0]
        # Prefer major-only driver (g++-14); also try major.minor (g++-14.2)
        probes = ["g++-{}".format(major), "gcc-{}".format(major)]
        if len(ver) > len(major):
            minor = ver[len(major):]
            probes[0:0] = [
                "g++-{}.{}".format(major, minor),
                "gcc-{}.{}".format(major, minor),
            ]
        return family, tuple(probes)

    # clang
    if not ver:
        return family, ("clang++", "clang")
    major = ver[:2] if len(ver) >= 2 else ver
    probes = ["clang++-{}".format(major), "clang-{}".format(major)]
    if len(ver) > len(major):
        minor = ver[len(major):]
        probes[0:0] = [
            "clang++-{}.{}".format(major, minor),
            "clang-{}.{}".format(major, minor),
        ]
    return family, tuple(probes)


def require_toolchain(family):
    """Skip unless a compiler for the toolchain family appears available."""
    family = {
        "cl": "vc",
        "msvc": "vc",
    }.get(family, family)

    if family == "vc":
        msvc = _msvc_available()
        if msvc:
            return msvc
        message = "MSVC toolchain (vc/cl) not available; skipping"
        logger.warning(message)
        pytest.skip(message)

    require_cxx()
    _, names = _versioned_driver_probes(family)
    for name in names:
        path = shutil.which(name)
        if path:
            return name, path
    message = "Toolchain family {!r} not found on PATH; skipping".format(family)
    logger.warning(message)
    pytest.skip(message)


def compiler_major_version(command):
    """Return the major version reported by `command --version`, or None."""
    try:
        output = subprocess.check_output(
            [command, "--version"],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    # clang: "Debian clang version 21.1.8" / "clang version 16.0.0"
    # gcc:   "g++ (Debian 15.3.0-2) 15.3.0" / "g++ (Ubuntu 13.3.0-6ubuntu2) 13.3.0"
    match = re.search(r"clang version (?P<major>\d+)", output)
    if match:
        return int(match.group("major"))
    match = re.search(r"\) (?P<major>\d+)\.\d+", output)
    if match:
        return int(match.group("major"))
    match = re.search(r"(?:gcc|g\+\+)[^\d]*(\d+)\.\d+", output, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _discover_versioned_drivers(prefix):
    """
    Find `{prefix}-N` binaries on PATH (e.g. g++-15, clang++-18).

    Returns a list of (major, command) sorted newest-first. Does not hardcode
    an upper major bound — whatever is installed is eligible.
    """
    pattern = re.compile(r"^{}-(\d+)$".format(re.escape(prefix)))
    found = {}
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory or not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        for entry in entries:
            match = pattern.match(entry)
            if not match:
                continue
            major = int(match.group(1))
            # Keep the first hit on PATH for each major (PATH order).
            found.setdefault(major, entry)
    return sorted(found.items(), key=lambda item: item[0], reverse=True)


def find_modules_capable_toolchain(family):
    """
    Pick a cuppa toolchain alias that meets the modules version floor.

    Preference order:
    1. Default `g++` / `clang++` on PATH (typically set via update-alternatives)
       → cuppa alias `gcc` / `clang`
    2. Otherwise the newest versioned driver on PATH that meets the floor
       → cuppa alias `gccN` / `clangN`

    Returns (cuppa_alias, driver_command, major) or None.
    """
    if family == "gcc":
        default = "g++"
        minimum = MODULES_MIN_GCC_MAJOR
        prefix = "g++"
        alias_prefix = "gcc"
    elif family == "clang":
        default = "clang++"
        minimum = MODULES_MIN_CLANG_MAJOR
        prefix = "clang++"
        alias_prefix = "clang"
    else:
        return None

    if shutil.which(default):
        reported = compiler_major_version(default)
        if reported is not None and reported >= minimum:
            return alias_prefix, default, reported

    for major, cmd in _discover_versioned_drivers(prefix):
        if major < minimum:
            continue
        if not shutil.which(cmd):
            continue
        reported = compiler_major_version(cmd)
        if reported is not None and reported >= minimum:
            return "{}{}".format(alias_prefix, major), cmd, reported

    return None


def require_modules_capable_toolchain(family=None):
    """
    Ensure a modules-capable Linux toolchain is available.

    MSVC is skipped (unsupported). Too-old GCC/Clang **fail** (do not skip) so
    CI cannot silently greenwash missing compiler coverage.

    Returns (cuppa_toolchain_alias, driver_command, major).
    """
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        pytest.skip("C++ modules are not supported for MSVC in this cuppa release")

    if family is None:
        if forced.startswith("gcc"):
            family = "gcc"
        elif forced.startswith("clang"):
            family = "clang"
        elif forced:
            family = forced
        elif shutil.which("g++") or shutil.which("gcc") or _discover_versioned_drivers("g++"):
            family = "gcc"
        elif shutil.which("clang++") or shutil.which("clang") or _discover_versioned_drivers("clang++"):
            family = "clang"
        else:
            pytest.fail("C++ modules tests require gcc or clang on PATH")

    # Explicit versioned CUPPA_TEST_TOOLCHAIN (e.g. gcc15) — honour when capable.
    if forced.startswith("gcc") and forced != "gcc":
        name, path = require_toolchain(forced)
        major = compiler_major_version(name)
        if major is None or major < MODULES_MIN_GCC_MAJOR:
            pytest.fail(
                "CUPPA_TEST_TOOLCHAIN={!r} is not modules-capable "
                "(need GCC {}+, found major {})"
                .format(forced, MODULES_MIN_GCC_MAJOR, major)
            )
        return forced, name, major
    if forced.startswith("clang") and forced != "clang":
        name, path = require_toolchain(forced)
        major = compiler_major_version(name)
        if major is None or major < MODULES_MIN_CLANG_MAJOR:
            pytest.fail(
                "CUPPA_TEST_TOOLCHAIN={!r} is not modules-capable "
                "(need Clang {}+, found major {})"
                .format(forced, MODULES_MIN_CLANG_MAJOR, major)
            )
        return forced, name, major

    selected = find_modules_capable_toolchain(family)
    if selected is None:
        minimum = MODULES_MIN_GCC_MAJOR if family == "gcc" else MODULES_MIN_CLANG_MAJOR
        pytest.fail(
            "C++ modules tests require {} {}+ on PATH "
            "(default g++/clang++ via update-alternatives, or a newer versioned driver). "
            "These tests do not skip for unsupported versions."
            .format(family, minimum)
        )
    return selected


def default_toolchain_flags():
    """Prefer CUPPA_TEST_TOOLCHAIN, else gcc, else clang, else vc on Windows."""
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip()
    if forced:
        # Cuppa registers MSVC as `vc` (not `cl`).
        if forced in ("cl", "msvc"):
            forced = "vc"
        require_toolchain(forced)
        return ["--toolchains={}".format(forced)]
    if shutil.which("g++") or shutil.which("gcc"):
        return ["--toolchains=gcc"]
    if shutil.which("clang++") or shutil.which("clang"):
        return ["--toolchains=clang"]
    if _msvc_available():
        return ["--toolchains=vc"]
    require_cxx()
    return []


# Clang stdlib variants exercised by CI / matrix tests.
CLANG_STDLIB_LIBSTDCXX = "libstdc++"
CLANG_STDLIB_LIBCXX = "libc++"
CLANG_STDLIB_VARIANTS = (CLANG_STDLIB_LIBSTDCXX, CLANG_STDLIB_LIBCXX)


def clang_stdlib_flag(stdlib):
    """Return the cuppa CLI flag for a Clang standard library choice."""
    return "--clang-stdlib={}".format(stdlib)


def active_clang_stdlib():
    """
    Stdlib selected by CUPPA_TEST_ARGS, if any.

    Returns 'libstdc++', 'libc++', or None when CUPPA_TEST_ARGS does not set it
    (cuppa then applies its Linux default of libstdc++).
    """
    for arg in os.environ.get("CUPPA_TEST_ARGS", "").split():
        if arg.startswith("--clang-stdlib="):
            return arg.split("=", 1)[1]
    return None


def clang_stdlib_matrix_params():
    """
    Parametrize ids for Clang builds that should cover both stdlibs.

    When CUPPA_TEST_ARGS already pins a stdlib (CI job), return only that
    variant so we do not triple-run inside a job that is already the dual matrix.
    Otherwise return both libstdc++ and libc++.
    """
    pinned = active_clang_stdlib()
    if pinned in CLANG_STDLIB_VARIANTS:
        return [pinned]
    return list(CLANG_STDLIB_VARIANTS)
