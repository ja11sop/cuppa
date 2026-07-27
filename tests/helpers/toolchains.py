import logging
import os
import shutil
import subprocess
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def require_cxx():
    for name in ("g++", "clang++", "c++"):
        path = shutil.which(name)
        if path:
            return name, path
    message = "No C++ compiler (g++/clang++/c++) found on PATH; skipping integration test"
    logger.warning(message)
    pytest.skip(message)


def require_toolchain(family):
    """Skip unless a compiler for the toolchain family appears available."""
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
    """Prefer gcc when present; otherwise omit --toolchains and use platform default."""
    if shutil.which("g++") or shutil.which("gcc"):
        return ["--toolchains=gcc"]
    if shutil.which("clang++") or shutil.which("clang"):
        return ["--toolchains=clang"]
    require_cxx()
    return []
