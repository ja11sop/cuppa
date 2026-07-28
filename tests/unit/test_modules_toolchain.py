#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.module_scanner import ModuleImport, ModuleScan
from cuppa.toolchains.cxx_modules_support import header_bmi_path, named_bmi_path


pytestmark = pytest.mark.unit


def test_named_and_header_bmi_paths(tmp_path):
    env = {"build_dir": str(tmp_path / "working")}
    named = named_bmi_path(env, "math.util", ".pcm")
    assert named.endswith("modules/math--util.pcm")
    header = header_bmi_path(env, "include/widget.hpp", ".gcm")
    assert "modules/header--" in header.replace("\\", "/")
    assert header.endswith(".gcm")


def test_clang_supports_modules_version_gate(monkeypatch):
    from cuppa.toolchains.clang import Clang

    toolchain = Clang.__new__(Clang)
    toolchain._reported_version = {"major": 16, "minor": 0}
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    assert toolchain.supports_modules(env=None) is True
    toolchain._reported_version = {"major": 15, "minor": 0}
    assert toolchain.supports_modules(env=None) is False


def test_gcc_supports_modules_version_gate(monkeypatch):
    from cuppa.toolchains.gcc import Gcc

    toolchain = Gcc.__new__(Gcc)
    toolchain._reported_version = {"major": 14, "minor": 0}
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    assert toolchain.supports_modules(env=None) is True
    toolchain._reported_version = {"major": 13, "minor": 0}
    assert toolchain.supports_modules(env=None) is False


def test_cl_does_not_support_modules():
    from cuppa.toolchains.cl import Cl

    toolchain = Cl.__new__(Cl)
    assert toolchain.supports_modules(env=None) is False


def test_clang_interface_and_consume_flags():
    from cuppa.toolchains.clang import Clang

    toolchain = Clang.__new__(Clang)
    env = {
        "build_dir": "/tmp/build",
        "_cuppa_module_registry": {
            "named": {"math": {"path": "/tmp/build/modules/math.pcm", "bmi": object()}},
            "headers": {},
        },
    }
    flags = toolchain.interface_module_flags(env, "math", "/tmp/build/modules/math.pcm")
    assert "-fmodules" in flags
    assert any(f.startswith("-fmodule-output=") for f in flags)

    scan = ModuleScan(None, None, [ModuleImport("named", "math")])
    consume = toolchain.consume_module_flags(env, scan)
    assert "-fmodule-file=math=/tmp/build/modules/math.pcm" in consume
