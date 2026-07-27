import logging
import os
import shutil
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


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
    probes = {
        "gcc": ("g++", "gcc"),
        "clang": ("clang++", "clang"),
    }
    names = probes.get(family, (family,))
    for name in names:
        path = shutil.which(name)
        if path:
            return name, path
    message = "Toolchain family {!r} not found on PATH; skipping".format(family)
    logger.warning(message)
    pytest.skip(message)


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
