#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest

from cuppa.cpp.module_scanner import ModuleImport, ModuleScan
from cuppa.toolchains.cxx_modules_support import (
    header_bmi_path,
    header_unit_label,
    named_bmi_path,
    write_gcc_module_mapper,
)


pytestmark = pytest.mark.unit


def test_named_and_header_bmi_paths(tmp_path):
    env = {"build_dir": str(tmp_path / "working")}
    named = named_bmi_path(env, "math.util", ".pcm")
    assert named.endswith("modules/math--util.pcm")
    header = header_bmi_path(env, "include/widget.hpp", ".gcm")
    assert header.replace("\\", "/").endswith("modules/header--include--widget.hpp.gcm")


def test_header_unit_label_strips_variant_dir(tmp_path):
    project = tmp_path / "proj"
    build = project / "_build" / "gcc15" / "dbg" / "x86_64" / "cxx20" / "working"
    env = {
        "build_dir": "_build/gcc15/dbg/x86_64/cxx20/working",
        "abs_build_dir": str(build),
        "sconscript_dir": str(project),
        "base_path": str(project),
    }
    assert header_unit_label(env, "include/widget.hpp") == "include/widget.hpp"
    assert header_unit_label(
        env,
        str(build / "include" / "widget.hpp"),
    ) == "include/widget.hpp"
    assert header_unit_label(
        env,
        "_build/gcc15/dbg/x86_64/cxx20/working/include/widget.hpp",
    ) == "include/widget.hpp"
    bmi = header_bmi_path(env, str(build / "include" / "widget.hpp"), ".gcm")
    assert "_build" not in os.path.basename(bmi)
    assert bmi.endswith("header--include--widget.hpp.gcm")


def test_gcc_mapper_includes_declared_header_spelling(tmp_path):
    build = tmp_path / "working"
    build.mkdir()
    env = {
        "build_dir": str(build),
        "abs_build_dir": str(build),
        "sconscript_dir": str(tmp_path),
        "base_path": str(tmp_path),
        "_cuppa_module_registry": {
            "named": {},
            "headers": {},
        },
    }
    bmi = str(build / "modules" / "header--include--widget.hpp.gcm")
    # Register VariantDir path first (insertion order that previously starved the mapper)
    from cuppa.cpp.cxx_modules import register_header_unit

    class _Bmi:
        pass

    bmi_node = _Bmi()
    # Avoid toolchain.write_module_mapper during register
    env["toolchain"] = type("T", (), {})()
    register_header_unit(
        env,
        str(build / "include" / "widget.hpp"),
        bmi,
        bmi_node,
    )
    register_header_unit(env, "include/widget.hpp", bmi, bmi_node)
    mapper = write_gcc_module_mapper(env)
    text = open(mapper).read()
    assert "include/widget.hpp" in text
    assert "header--include--widget.hpp.gcm" in text


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
