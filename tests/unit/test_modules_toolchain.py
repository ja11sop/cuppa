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
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Darwin")
    assert toolchain.supports_modules(env=None) is True
    toolchain._reported_version = {"major": 15, "minor": 0}
    assert toolchain.supports_modules(env=None) is False


def test_gcc_supports_modules_version_gate(monkeypatch):
    from cuppa.toolchains.gcc import Gcc

    toolchain = Gcc.__new__(Gcc)
    toolchain._reported_version = {"major": 14, "minor": 0}
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    assert toolchain.supports_modules(env=None) is True
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Darwin")
    assert toolchain.supports_modules(env=None) is True
    toolchain._reported_version = {"major": 13, "minor": 0}
    assert toolchain.supports_modules(env=None) is False


def test_cl_supports_modules_on_windows_version_gate(monkeypatch):
    from cuppa.toolchains.cl import Cl

    # Floors use SCons toolset ids (14.2, 14.3, 14.5), not compiler update numbers.
    toolchain = Cl.__new__(Cl)
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Windows")
    for capable in ("14.2", "14.3", "14.5"):
        toolchain._long_version = capable
        assert toolchain.supports_modules(env=None) is True
    for too_old in ("14.1", "14.0"):
        toolchain._long_version = too_old
        assert toolchain.supports_modules(env=None) is False
    monkeypatch.setattr("cuppa.build_platform.name", lambda: "Linux")
    toolchain._long_version = "14.5"
    assert toolchain.supports_modules(env=None) is False


def test_cl_interface_and_consume_flags_use_space_separated_paths():
    from cuppa.toolchains.cl import Cl

    toolchain = Cl.__new__(Cl)
    win_bmi = r"C:\build\modules\math.ifc"
    flags = toolchain.interface_module_flags({}, "math", win_bmi)
    assert "-interface" in flags
    assert "-ifcOutput" in flags
    assert win_bmi in flags
    # Colon form breaks MSVC on drive-letter paths (C3474 on ':C:\...').
    assert not any(f.startswith("-ifcOutput:") for f in flags)
    assert flags[flags.index("-ifcOutput") + 1] == win_bmi

    internal = toolchain.interface_module_flags({}, "calc:core", win_bmi, exported=False)
    assert "-internalPartition" in internal
    assert "-interface" not in internal

    env = {
        "build_dir": r"C:\build",
        "_cuppa_module_registry": {
            "named": {
                "math": {"path": win_bmi, "bmi": object()},
                "calc": {"path": r"C:\build\modules\calc.ifc", "bmi": object()},
                "calc:core": {"path": r"C:\build\modules\calc--core.ifc", "bmi": object()},
            },
            "headers": {},
        },
    }
    scan = ModuleScan(None, None, [ModuleImport("named", "math")], False)
    consume = toolchain.consume_module_flags(env, scan)
    assert "-reference" in consume
    assert "math={}".format(win_bmi) in consume
    assert not any(f.startswith("-reference:") for f in consume)

    # Internal partition must reference primary, not itself.
    partition_scan = ModuleScan(None, "calc:core", [], False)
    partition_consume = toolchain.consume_module_flags(env, partition_scan)
    assert "calc={}".format(r"C:\build\modules\calc.ifc") in partition_consume
    assert "calc:core=" not in " ".join(partition_consume)


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


class _DialectToolchain:
    """Toolchain stub built by _toolchain() with only the queries under test."""

    def name(self):
        return "fake-tc"

    def stdcpp_flag_for(self, standard):
        return "-std={}".format(standard)


class _DialectEnv(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.replaced = []

    def ReplaceFlags(self, flags):
        self.replaced.append(flags)


def _toolchain(abi=None, abi_flag=None, abi_raises=False):
    toolchain = _DialectToolchain.__new__(_DialectToolchain)
    if abi_raises:
        def raising(env):
            raise RuntimeError("no dialect available")
        toolchain.abi = raising
    elif abi is not None:
        toolchain.abi = lambda env: abi
    if abi_flag is not None:
        toolchain.abi_flag = lambda env: abi_flag
    return toolchain


def test_dialect_ranks_are_ordinal():
    from cuppa.methods.modules import dialect_rank

    ordered = ["c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23", "c++26"]
    ranks = [dialect_rank(standard) for standard in ordered]
    assert ranks == sorted(ranks)
    # A pre-C++11 dialect must never outrank a modules-capable one.
    assert dialect_rank("c++98") < dialect_rank("c++20")
    assert dialect_rank("c++2c") == dialect_rank("c++26")
    assert dialect_rank("c++latest") >= dialect_rank("c++23")
    assert dialect_rank(None) == 0


@pytest.mark.parametrize(
    "value,expected",
    [
        ("c++20", "c++20"),
        ("-std=c++2c", "c++2c"),
        ("-std:c++latest", "c++latest"),
        ("-std=c++17", "c++17"),
        ("-std=gnu++17", None),
        ("", None),
        (None, None),
    ],
)
def test_dialect_from_flag_forms(value, expected):
    from cuppa.methods.modules import dialect_from_flag

    assert dialect_from_flag(value) == expected


def test_modules_floor_keeps_a_toolchain_default_that_already_meets_it():
    from cuppa.methods.modules import ensure_modules_dialect_floor

    env = _DialectEnv({"toolchain": _toolchain(abi="c++2c")})
    assert ensure_modules_dialect_floor(env) == "c++2c"
    assert "stdcpp" not in env
    assert env.replaced == []


def test_modules_floor_keeps_msvc_latest_default():
    from cuppa.methods.modules import ensure_modules_dialect_floor

    env = _DialectEnv({"toolchain": _toolchain(abi_flag="-std:c++latest")})
    assert ensure_modules_dialect_floor(env) == "c++latest"
    assert env.replaced == []


def test_modules_floor_raises_a_toolchain_default_below_it():
    from cuppa.methods.modules import ensure_modules_dialect_floor

    env = _DialectEnv({"toolchain": _toolchain(abi_flag="-std=c++17")})
    assert ensure_modules_dialect_floor(env) == "c++20"
    assert env["stdcpp"] == "c++20"
    assert env.replaced == [["-std=c++20"]]


def test_modules_floor_raises_an_explicitly_requested_lower_dialect():
    from cuppa.methods.modules import ensure_modules_dialect_floor

    env = _DialectEnv({"stdcpp": "c++17", "toolchain": _toolchain(abi="c++2c")})
    assert ensure_modules_dialect_floor(env) == "c++20"
    assert env["stdcpp"] == "c++20"


def test_modules_floor_falls_back_when_a_dialect_query_fails():
    from cuppa.methods.modules import ensure_modules_dialect_floor

    env = _DialectEnv({"toolchain": _toolchain(abi_raises=True, abi_flag="-std=c++2b")})
    assert ensure_modules_dialect_floor(env) == "c++2b"
    assert env.replaced == []


def test_sources_use_modules_detects_module_participation():
    from cuppa.cpp.cxx_modules import sources_use_modules

    plain = ModuleScan(None, None, [], False)
    importing = ModuleScan(None, None, [ModuleImport("named", "math")], False)
    implementation = ModuleScan(None, "math", [], False)

    assert sources_use_modules([("tu", "main.cpp", plain)]) is False
    assert sources_use_modules([("object", "prebuilt.o", None)]) is False
    assert sources_use_modules([("tu", "main.cpp", importing)]) is True
    assert sources_use_modules([("tu", "impl.cpp", implementation)]) is True
    assert sources_use_modules([("bmi", "math.cppm", plain)]) is True
