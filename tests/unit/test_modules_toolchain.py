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


def test_object_target_keeps_interface_suffix(tmp_path):
    from cuppa.cpp.cxx_modules import object_target_for

    class _Src:
        def __init__( self, path ):
            self.path = path

        def __str__( self ):
            return self.path

    class _Env( dict ):
        def File( self, path ):
            return path

    env = _Env({
        "build_root": "_build",
        "build_dir": str( tmp_path / "working" ),
    })
    cppm = object_target_for( env, _Src( "calc/calc.cppm" ), "", ".o" )
    cpp = object_target_for( env, _Src( "calc/calc.cpp" ), "", ".o" )
    assert cppm.replace( "\\", "/" ).endswith( "calc.cppm.o" )
    assert cpp.replace( "\\", "/" ).endswith( "calc.o" )
    assert cppm != cpp


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
    assert any(f.startswith("-fmodule-output=") for f in flags)
    assert "-x" in flags

    scan = ModuleScan(None, None, [ModuleImport("named", "math")], False)
    consume = toolchain.consume_module_flags(env, scan)
    assert "-fmodule-file=math=/tmp/build/modules/math.pcm" in consume


def test_gcc_mapper_angle_header_candidates(tmp_path):
    build = tmp_path / "working"
    build.mkdir()
    env = {
        "build_dir": str(build),
        "abs_build_dir": str(build),
        "sconscript_dir": str(tmp_path),
        "base_path": str(tmp_path),
        "_cuppa_module_registry": {"named": {}, "headers": {}},
        "toolchain": type("T", (), {})(),
    }
    from cuppa.cpp.cxx_modules import register_header_unit

    bmi = str(build / "modules" / "header--angle--span.gcm")
    bmi_node = object()
    register_header_unit(env, "<span>", bmi, bmi_node)
    register_header_unit(env, "span", bmi, bmi_node)
    mapper = write_gcc_module_mapper(env)
    text = open(mapper).read()
    assert "<span>" in text
    assert "span " in text or "\nspan " in text


def test_collect_named_bmi_nodes_transitive():
    from cuppa.cpp.cxx_modules import collect_named_bmi_nodes

    bmi_a, bmi_b, bmi_c = object(), object(), object()
    registry = {
        "named": {
            "a": {"bmi": bmi_a, "path": "a.pcm", "imports": ["b"]},
            "b": {"bmi": bmi_b, "path": "b.pcm", "imports": ["c"]},
            "c": {"bmi": bmi_c, "path": "c.pcm", "imports": []},
        },
        "headers": {},
    }
    nodes = collect_named_bmi_nodes(registry, "a")
    assert nodes == [bmi_a, bmi_b, bmi_c]


def test_activate_modules_stoperror_unsupported(monkeypatch):
    import SCons.Errors
    from cuppa.methods.modules import activate_modules_for_env

    class FakeToolchain:
        def name(self):
            return "fake-tc"

        def supports_modules(self, env):
            return False

    env = {"toolchain": FakeToolchain(), "modules": True}
    with pytest.raises(SCons.Errors.StopError):
        activate_modules_for_env(env)
    assert env["modules"] is False


def test_parse_header_unit_declaration_angle():
    from cuppa.cpp.module_scanner import parse_header_unit_declaration

    assert parse_header_unit_declaration("<span>") == ("angle", "span", "<span>")
    assert parse_header_unit_declaration("include/widget.hpp")[0] == "quoted"


def test_supports_import_std_gates(monkeypatch):
    from cuppa.toolchains.clang import Clang
    from cuppa.toolchains.gcc import Gcc
    from cuppa.toolchains.cl import Cl

    gcc = Gcc.__new__(Gcc)
    gcc._reported_version = {"major": 15, "minor": 0}
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    assert gcc.supports_import_std(env=None) is True
    gcc._reported_version = {"major": 14, "minor": 0}
    assert gcc.supports_import_std(env=None) is False

    clang = Clang.__new__(Clang)
    clang._reported_version = {"major": 18, "minor": 0}
    clang._stdlib = "libc++"
    assert clang.supports_import_std(env=None) is True
    clang._stdlib = "libstdc++"
    assert clang.supports_import_std(env=None) is False

    assert Cl.__new__(Cl).supports_import_std(env=None) is False


def test_ensure_import_std_dialect_floor():
    from cuppa.methods.modules import ensure_import_std_dialect_floor

    class FakeToolchain:
        def stdcpp_flag_for(self, standard):
            return "-std={}".format(standard)

    class FakeEnv(dict):
        def ReplaceFlags(self, flags):
            self["flags"] = flags

    env = FakeEnv({"stdcpp": "c++20", "toolchain": FakeToolchain()})
    assert ensure_import_std_dialect_floor(env) == "c++23"
    assert env["stdcpp"] == "c++23"
