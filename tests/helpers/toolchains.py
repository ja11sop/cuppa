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


def is_apple_clang_version_text(output):
    """True if --version text is Apple Clang / Apple LLVM."""
    return bool(re.search(r"Apple (?:clang|LLVM) version", output or ""))


def is_apple_clang(command):
    """True if the driver on PATH is Apple Clang / Apple LLVM."""
    try:
        output = subprocess.check_output(
            [command, "--version"],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return is_apple_clang_version_text(output)


def compiler_major_version(command):
    """Return the major version reported by `command --version`, or None.

    Apple Clang is treated as not modules-capable: returns None so helpers
    do not mistake its marketing major (e.g. 21) for LLVM Clang 21.
    """
    try:
        output = subprocess.check_output(
            [command, "--version"],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    # Apple Clang reports high majors but does not support C++20 named modules.
    if is_apple_clang_version_text(output):
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
    Ensure a modules-capable toolchain is available.

    Too-old GCC/Clang **fail** (do not skip) so CI cannot silently greenwash.
    On Windows with CUPPA_TEST_TOOLCHAIN=vc, returns the MSVC toolchain.

    Returns (cuppa_toolchain_alias, driver_command, major).
    """
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        if os.name != "nt":
            pytest.skip("MSVC modules tests require Windows")
        require_toolchain("vc")
        return "vc", "cl", 0

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
        apple_hint = ""
        if family == "clang":
            for probe in ("clang++", "clang"):
                if shutil.which(probe) and is_apple_clang(probe):
                    apple_hint = (
                        " Apple Clang on PATH is not modules-capable; "
                        "install Homebrew llvm and put its bin ahead of "
                        "/usr/bin (e.g. brew install llvm)."
                    )
                    break
        pytest.fail(
            "C++ modules tests require {} {}+ on PATH "
            "(default g++/clang++ via update-alternatives, or a newer versioned driver). "
            "These tests do not skip for unsupported versions.{}".format(
                family, minimum, apple_hint
            )
        )
    return selected


def find_libcxx_std_cppm(driver="clang++", major=None):
    """
    Locate libc++ ``std.cppm`` for ``import std`` tests.

    Mirrors ``Clang._find_libcxx_module_interface``: resource-dir walk, Linux
    ``/usr/lib/llvm-<N>/…``, and Homebrew LLVM layouts on macOS.
    """
    filename = "std.cppm"
    candidates = []
    try:
        result = subprocess.run(
            [driver, "-print-resource-dir"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        resource = (result.stdout or "").strip()
        if resource:
            root = os.path.abspath(os.path.join(resource, "..", "..", ".."))
            candidates.append(os.path.join(root, "share", "libc++", "v1", filename))
    except (OSError, subprocess.SubprocessError):
        pass

    if major:
        candidates.append(
            "/usr/lib/llvm-{}/share/libc++/v1/{}".format(major, filename)
        )
    candidates.append("/usr/share/libc++/v1/{}".format(filename))
    candidates.append("/opt/homebrew/opt/llvm/share/libc++/v1/{}".format(filename))
    candidates.append("/usr/local/opt/llvm/share/libc++/v1/{}".format(filename))

    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


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


# Clang stdlib variants exercised by CI / matrix tests (Linux only).
CLANG_STDLIB_LIBSTDCXX = "libstdc++"
CLANG_STDLIB_LIBCXX = "libc++"
CLANG_STDLIB_VARIANTS = (CLANG_STDLIB_LIBSTDCXX, CLANG_STDLIB_LIBCXX)

_clang_stdlib_usable_cache = {}


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


def clang_stdlib_matrix_supported():
    """
    Dual --clang-stdlib= coverage is a Linux GCC/Clang concern.

    Windows CI uses MSVC (`CUPPA_TEST_TOOLCHAIN=vc`); clang++ may still appear on
    PATH (LLVM install) but --clang-stdlib=libc++ is not a supported matrix cell
    there and can hang.
    """
    if os.name == "nt":
        return False
    forced = os.environ.get("CUPPA_TEST_TOOLCHAIN", "").strip().lower()
    if forced in ("vc", "cl", "msvc"):
        return False
    return True


def clang_stdlib_usable(stdlib):
    """
    True if the default clang++ can compile a trivial TU with this -stdlib=.

    Used so the gcc CI job (clang on PATH, no libc++ packages) does not fail
    the dual-stdlib matrix cell for libc++. Always false off Linux / MSVC jobs.
    """
    if stdlib not in CLANG_STDLIB_VARIANTS:
        return False
    if not clang_stdlib_matrix_supported():
        return False
    if stdlib in _clang_stdlib_usable_cache:
        return _clang_stdlib_usable_cache[stdlib]

    usable = False
    driver = shutil.which("clang++") or shutil.which("clang")
    if driver:
        try:
            result = subprocess.run(
                [driver, "-stdlib={}".format(stdlib), "-std=c++20", "-x", "c++", "-fsyntax-only", "-"],
                input="#include <cstdlib>\nint main() { return 0; }\n",
                capture_output=True,
                text=True,
                timeout=30,
            )
            usable = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            usable = False

    _clang_stdlib_usable_cache[stdlib] = usable
    return usable


def require_clang_stdlib(stdlib):
    """Skip (or fail when CI-pinned) unless Clang can use the given stdlib."""
    if not clang_stdlib_matrix_supported():
        message = "Clang --clang-stdlib= matrix is Linux-only; skipping on this platform/job"
        logger.warning(message)
        pytest.skip(message)
    if clang_stdlib_usable(stdlib):
        return
    pinned = active_clang_stdlib()
    message = (
        "Clang -stdlib={} is not usable with the clang++ on PATH "
        "(missing headers/runtime; install libc++-dev for libc++)"
        .format(stdlib)
    )
    # Pinned CI cells must fail loudly if packages are missing.
    if pinned == stdlib:
        pytest.fail(message)
    logger.warning(message)
    pytest.skip(message)


def clang_stdlib_matrix_params():
    """
    Parametrize ids for Clang builds that should cover both stdlibs.

    When CUPPA_TEST_ARGS already pins a stdlib (CI job), return only that
    variant so we do not triple-run inside a job that is already the dual matrix.
    Otherwise return each of libstdc++ / libc++ that the local clang can use
    (so the gcc job without libc++ packages only runs libstdc++).
    Off Linux / MSVC jobs return a single placeholder id; the test skips.
    """
    if not clang_stdlib_matrix_supported():
        return [CLANG_STDLIB_LIBSTDCXX]
    pinned = active_clang_stdlib()
    if pinned in CLANG_STDLIB_VARIANTS:
        return [pinned]
    usable = [stdlib for stdlib in CLANG_STDLIB_VARIANTS if clang_stdlib_usable(stdlib)]
    # Keep one id so collection succeeds when clang/libc++ are absent; the test skips.
    return usable or [CLANG_STDLIB_LIBSTDCXX]


def _clang_accepts_fprofiles(driver):
    """Return True when ``driver`` accepts ``-fprofiles``."""
    try:
        result = subprocess.run(
            [driver, "-fprofiles", "-fsyntax-only", "-x", "c++", "-"],
            input="int x;\n",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def find_profiles_capable_toolchain():
    """
    Find a Clang that accepts ``-fprofiles`` (C++ Alliance Profiles builds).

    Returns ``(cuppa_alias_or_None, driver_path)`` or ``None``.
    Prefers ``CUPPA_TEST_PROFILES_TOOLCHAIN`` when set, then versioned / default
    clang++ on PATH. Distro Clang typically fails the probe and is skipped.
    """
    forced = os.environ.get("CUPPA_TEST_PROFILES_TOOLCHAIN", "").strip()
    if forced:
        path = shutil.which(forced) or forced
        if path and _clang_accepts_fprofiles(path):
            # Prefer a cuppa alias when the forced name looks like one.
            alias = forced if not os.path.isabs(forced) and "/" not in forced else "clang"
            return alias, path
        return None

    candidates = []
    for name in ("clang++", "clang"):
        path = shutil.which(name)
        if path:
            candidates.append((name if name == "clang++" else "clang", path))
    for major in range(30, 15, -1):
        for prefix in ("clang++-{}", "clang-{}"):
            name = prefix.format(major)
            path = shutil.which(name)
            if path:
                alias = "clang{}".format(major) if "++" in name else "clang{}".format(major)
                candidates.append((alias, path))

    seen = set()
    for alias, path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if is_apple_clang(path):
            continue
        if _clang_accepts_fprofiles(path):
            return alias, path
    return None


def require_profiles_capable_toolchain():
    """Return ``(alias, --toolchains=… flag)`` or skip when no Profiles Clang."""
    found = find_profiles_capable_toolchain()
    if found is None:
        pytest.skip(
            "C++ Profiles tests require a Profiles-capable Clang "
            "(-fprofiles). Install a C++ Alliance Profiles archive and register "
            "it with --toolchain-archive= / --clang-root=, or set "
            "CUPPA_TEST_PROFILES_TOOLCHAIN to its clang++."
        )
    alias, path = found
    logger.info("C++ Profiles tests using %s (%s)", alias, path)
    return alias, "--toolchains={}".format(alias)
