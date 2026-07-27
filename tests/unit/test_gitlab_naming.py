from types import SimpleNamespace

import pytest

from cuppa.package_managers.gitlab import (
    package_file_name,
    package_url,
    remove_prefix,
    remove_suffix,
    tool_variant,
)


pytestmark = pytest.mark.unit


def test_remove_prefix_and_suffix():
    assert remove_prefix("foobar", "foo") == "bar"
    assert remove_prefix("foobar", "baz") == "foobar"
    assert remove_suffix("foobar", "bar") == "foo"
    assert remove_suffix("foobar", "baz") == "foobar"


def test_tool_variant_and_package_names(monkeypatch):
    toolchain = SimpleNamespace(package_name=lambda: "gcc15")
    variant = SimpleNamespace(name=lambda: "rel")
    env = {
        "toolchain": toolchain,
        "variant": variant,
        "target_arch": "x86_64",
        "abi": "cxx2c",
    }
    assert tool_variant(env) == "gcc15_rel_x86_64_cxx2c"
    assert tool_variant(env, variant="dbg") == "gcc15_dbg_x86_64_cxx2c"

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        lambda: {"ID": "debian"},
    )
    name = package_file_name(env, package="capy")
    assert name == "capy_debian_gcc15_rel_x86_64_cxx2c.tar.gz"
    url = package_url(
        env,
        registry="https://gitlab.example/api/v4/projects/1",
        package="capy",
        version="1.0.0",
    )
    assert url.endswith("/packages/generic/capy/1.0.0/" + name)
