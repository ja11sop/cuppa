from types import SimpleNamespace

import pytest

from cuppa.package_managers.gitlab import (
    GitlabPackageDependency,
    os_release_id,
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
    name = package_file_name(env, package="widget")
    assert name == "widget_debian_gcc15_rel_x86_64_cxx2c.tar.gz"
    url = package_url(
        env,
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.0.0",
    )
    assert url.endswith("/packages/generic/widget/1.0.0/" + name)


def test_os_release_id_falls_back_without_freedesktop(monkeypatch):
    def _missing():
        raise AttributeError("freedesktop_os_release")

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        _missing,
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Windows",
    )
    assert os_release_id() == "windows"

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Darwin",
    )
    assert os_release_id() == "macos"

    toolchain = SimpleNamespace(package_name=lambda: "vc143")
    variant = SimpleNamespace(name=lambda: "rel")
    env = {
        "toolchain": toolchain,
        "variant": variant,
        "target_arch": "x86_64",
        "abi": "cxx17",
    }
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system",
        lambda: "Windows",
    )
    assert package_file_name(env, package="boost") == (
        "boost_windows_vc143_rel_x86_64_cxx17.tar.gz"
    )


def _dependency_for_pkg_config(tmp_path, clean):
    dependency = GitlabPackageDependency.__new__(GitlabPackageDependency)
    dependency._clean = clean
    dependency._library_prefix = ""
    dependency._package_id = "widget/2.28.0/rel"
    dependency._pkg_config_dir = str(tmp_path / "never_extracted" / "pkgconfig")
    dependency._env = SimpleNamespace(
        parsed=[], ParseConfig=lambda command: dependency._env.parsed.append(command)
    )
    return dependency


def test_parse_pkg_config_skipped_when_cleaning_without_package(tmp_path):
    dependency = _dependency_for_pkg_config(tmp_path, clean=True)
    dependency.parse_pkg_config(["widget_kms"])
    assert dependency._env.parsed == []


def test_parse_pkg_config_runs_when_not_cleaning(tmp_path):
    dependency = _dependency_for_pkg_config(tmp_path, clean=False)
    dependency.parse_pkg_config(["widget_kms"])
    assert len(dependency._env.parsed) == 1
    assert "widget_kms" in dependency._env.parsed[0]
