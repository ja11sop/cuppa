#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from unittest.mock import patch

import pytest

from cuppa.toolchains.cl import MODULES_MIN_MSVC_TOOLSET, Cl


@pytest.mark.unit
@pytest.mark.parametrize(
    "scons_version,alias,major,minor,experimental",
    [
        ("14.5", "vc145", 14, 5, False),
        ("14.3", "vc143", 14, 3, False),
        ("14.2", "vc142", 14, 2, False),
        ("14.2Exp", "vc142e", 14, 2, True),
        ("14.1", "vc141", 14, 1, False),
        ("14.0", "vc140", 14, 0, False),
        ("14.51", "vc1451", 14, 51, False),
        ("12.0", "vc120", 12, 0, False),
    ],
)
def test_parse_toolset_version(scons_version, alias, major, minor, experimental):
    parsed = Cl.parse_toolset_version(scons_version)
    assert parsed.scons == scons_version
    assert parsed.alias == alias
    assert parsed.major == major
    assert parsed.minor == minor
    assert parsed.experimental is experimental
    assert Cl.vc_version(scons_version) == alias
    assert Cl.toolset_key(scons_version) == (major, minor)


@pytest.mark.unit
def test_vc_version_naming():
    assert Cl.vc_version("14.3") == "vc143"
    assert Cl.vc_version("14.2Exp") == "vc142e"
    assert Cl.vc_version("14.0") == "vc140"
    assert Cl.vc_version("14.5") == "vc145"


@pytest.mark.unit
@pytest.mark.parametrize(
    "scons_version,expected",
    [
        ("14.1", False),
        ("14.0", False),
        ("14.2", True),
        ("14.2Exp", True),
        ("14.3", True),
        ("14.5", True),
        ("14.51", True),
    ],
)
def test_supports_modules_uses_scons_toolset_floor(scons_version, expected):
    toolchain = Cl.__new__(Cl)
    toolchain._toolset = Cl.parse_toolset_version(scons_version)
    toolchain._long_version = toolchain._toolset.scons
    with patch("cuppa.build_platform.name", return_value="Windows"):
        assert toolchain.supports_modules(None) is expected
    assert MODULES_MIN_MSVC_TOOLSET == (14, 2)


@pytest.mark.unit
@pytest.mark.parametrize(
    "standard,expected",
    [
        ("c++14", "-std:c++14"),
        ("c++1y", "-std:c++14"),
        ("c++17", "-std:c++17"),
        ("c++1z", "-std:c++17"),
        ("c++20", "-std:c++20"),
        ("c++2a", "-std:c++20"),
        ("c++23", "-std:c++23"),
        ("c++2b", "-std:c++23"),
        ("c++26", "-std:c++latest"),
        ("c++2c", "-std:c++latest"),
        ("c++latest", "-std:c++latest"),
        ("c++11", "-std:c++14"),
        ("c++98", "-std:c++14"),
    ],
)
def test_stdcpp_flag_for(standard, expected):
    toolchain = Cl.__new__(Cl)
    assert toolchain.stdcpp_flag_for(standard) == expected


@pytest.mark.unit
def test_abi_flag_default_and_override():
    toolchain = Cl.__new__(Cl)

    class Env(dict):
        pass

    env = Env()
    env["stdcpp"] = None
    assert toolchain.abi_flag(env) == "-std:c++20"
    assert toolchain.abi(env) == "c++20"

    env["stdcpp"] = "c++17"
    assert toolchain.abi_flag(env) == "-std:c++17"
    assert toolchain.abi(env) == "c++17"


@pytest.mark.unit
def test_architecture_aliases_include_arm64():
    assert Cl._supported_architectures["arm64"] == "arm64"
    assert Cl._supported_architectures["aarch64"] == "arm64"
    assert Cl._supported_architectures["x86_64"] == "amd64"
    assert Cl._target_architectures[("amd64", "arm64")] == "amd64_arm64"
    assert Cl._target_architectures[("arm64", "arm64")] == "arm64"
