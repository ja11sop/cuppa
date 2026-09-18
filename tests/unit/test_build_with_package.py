#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import os

import pytest
import SCons.Errors

from cuppa.build_with_package import package_dependency
from cuppa.package_managers.gitlab import GitlabPackageDependency
from tests.helpers.fakes import FakeEnv


pytestmark = pytest.mark.unit


def test_package_dependency_requires_registry():
    with pytest.raises(SCons.Errors.StopError):
        package_dependency("widget", package_manager="gitlab")


def test_package_info_none_without_manager():
    Dep = package_dependency(
        "widget", package_manager="gitlab", registry="https://gitlab.example/api/v4"
    )
    Dep._package_manager = None
    env = FakeEnv()
    assert Dep.package_info(env) is None


def test_package_info_identity_and_default_variant(reset_location_caches):
    Dep = package_dependency(
        "widget",
        package_manager="gitlab",
        registry="https://gitlab.example/api/v4",
        package="widget",
        version="1.2.3",
    )
    env = FakeEnv(develop=False)
    info = Dep.package_info(env)
    assert info["manager"] == "gitlab"
    assert info["package"]["id"][0] == "https://gitlab.example/api/v4"
    assert info["package"]["id"][1] == "widget"
    assert info["package"]["id"][2] == "1.2.3"
    assert info["package"]["id"][3] == "rel"
    assert info["package"]["id"][4] is False
    # No toolchain on FakeEnv → tool_variant segment is None.
    assert info["package"]["id"][5] is None
    assert info["package"]["args"]["variant"] == "rel"


def test_package_id_default_variant_via_gitlab_helper():
    pkg = type("Pkg", (), {"_registry": "r", "_package": "p", "_version": "1", "_variant": None})()
    pkg.default_version = lambda version, env: None
    env = FakeEnv(develop=True)
    result = GitlabPackageDependency.package_id(pkg, env)
    assert result["id"][3] == "rel"
    assert result["id"][4] is True
    assert result["id"][5] is None


class _FakeToolchain:
    def __init__(self, name):
        self._name = name

    def package_name(self):
        return self._name


class _FakeVariant:
    def name(self):
        return "dbg"


def test_package_id_includes_tool_variant_per_toolchain():
    pkg = type("Pkg", (), {
        "_registry": "r",
        "_package": "boost",
        "_version": "1.91",
        "_variant": "rel",
    })()
    pkg.default_version = lambda version, env: None

    def make_env(toolchain_name):
        return FakeEnv(
            develop=False,
            toolchain=_FakeToolchain(toolchain_name),
            variant=_FakeVariant(),
            target_arch="x86_64",
            abi="cxx2c",
        )

    gcc_id = GitlabPackageDependency.package_id(pkg, make_env("gcc153"))["id"]
    clang_id = GitlabPackageDependency.package_id(pkg, make_env("clang211"))["id"]
    assert gcc_id[5] == "gcc153_rel_x86_64_cxx2c"
    assert clang_id[5] == "clang211_rel_x86_64_cxx2c"
    assert gcc_id != clang_id


def test_gitlab_override_options_use_reserved_package_namespace():
    registered = []

    def add_option(flag, **attributes):
        registered.append((flag, attributes["dest"]))

    GitlabPackageDependency.add_options("gitlab", "widget", add_option)

    assert ("--widget-gitlab-version", "widget-gitlab-version") in registered
    assert (
        "--package-gitlab-os-override-widget",
        "package-gitlab-os-override-widget",
    ) in registered
    assert (
        "--package-gitlab-toolchain-override-widget",
        "package-gitlab-toolchain-override-widget",
    ) in registered
    assert not any(flag == "--widget-gitlab-os" for flag, _dest in registered)


def test_gitlab_override_option_ids_stay_scoped_to_each_dependency():
    Widget = package_dependency(
        "widget",
        package_manager="gitlab",
        registry="https://gitlab.example/api/v4",
        package="widget",
        version="1.2.3",
    )
    Gadget = package_dependency(
        "gadget",
        package_manager="gitlab",
        registry="https://gitlab.example/api/v4",
        package="gadget",
        version="2.0.0",
    )
    env = FakeEnv(
        develop=False,
        **{
            "package-gitlab-os-override-widget": "debian",
            "package-gitlab-os-override-gadget": "ubuntu",
        }
    )

    widget = Widget.package_info(env)["package"]
    gadget = Gadget.package_info(env)["package"]

    assert widget["args"]["os_override"] == "debian"
    assert gadget["args"]["os_override"] == "ubuntu"
    assert widget["id"][6] == "debian"
    assert gadget["id"][6] == "ubuntu"


def test_package_dependency_add_options_idempotent_for_same_name():
    """Second factory with the same BuildWith name must not re-AddOption.

    Multi-toolchain variant envs re-synthesize transitive packages and would
    otherwise raise OptionConflictError on ``--<name>-package-manager``.
    """
    from optparse import OptionConflictError

    from cuppa.build_with_package import _reset_registered_package_options_for_tests

    _reset_registered_package_options_for_tests()
    seen = []

    def add_option( *args, **_kwargs ):
        flag = args[0]
        if flag in seen:
            raise OptionConflictError(
                    "conflicting option string(s): {}".format( flag ),
                    None,
            )
        seen.append( flag )

    first = package_dependency(
            "c_ares",
            package_manager="gitlab",
            registry="https://gitlab.example/api/v4",
            package="c-ares",
            version="1.34.5",
    )
    second = package_dependency(
            "c_ares",
            package_manager="gitlab",
            registry="https://gitlab.example/api/v4",
            package="c-ares",
            version="1.34.5",
    )
    first.add_options( add_option )
    second.add_options( add_option )
    assert "--c_ares-package-manager" in seen
    assert seen.count( "--c_ares-package-manager" ) == 1


def _develop_env(tmp_path, monkeypatch, **overrides):
    """Enough env for GitlabPackageDependency to resolve paths without a network."""
    from types import SimpleNamespace

    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.freedesktop_os_release",
        lambda: {"ID": "debian"},
    )
    monkeypatch.setattr(
        "cuppa.package_managers.gitlab.platform.system", lambda: "Linux"
    )
    (tmp_path / "project").mkdir(exist_ok=True)
    env = FakeEnv(
        offline=False,
        develop=True,
        clean=False,
        dump=False,
        storage_resolve_only=False,
        downloads_root=str(tmp_path / "downloads"),
        dependencies_root=str(tmp_path / "dependencies"),
        sconstruct_dir=str(tmp_path / "project"),
        toolchain=SimpleNamespace(package_name=lambda: "gcc15"),
        variant=SimpleNamespace(name=lambda: "rel"),
        target_arch="x86_64",
        abi="cxx2c",
    )
    env.update(overrides)
    return env


def test_a_relative_package_develop_path_is_anchored_to_the_sconstruct_directory(
    tmp_path, monkeypatch
):
    """The swap must resolve where --list-develop says, not against the working directory."""
    prefix = tmp_path / "widget"
    (prefix / "include").mkdir(parents=True)
    (prefix / "lib").mkdir()

    package = GitlabPackageDependency(
        _develop_env(tmp_path, monkeypatch),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )

    # Anchored to the sconstruct directory, so it names the intended tree wherever
    # cuppa ran from. Left lexical, as location develop paths are: normalising would
    # resolve a symlinked parent to the wrong place.
    assert package.package_dir().startswith(str(tmp_path / "project"))
    assert os.path.samefile(package.package_dir(), prefix)
    assert os.path.samefile(package.include_dir(), prefix / "include")
    # Nothing was downloaded or extracted: develop replaces the fetch entirely.
    assert not (tmp_path / "dependencies").exists()


def test_an_absolute_package_develop_path_is_used_as_given(tmp_path, monkeypatch):
    prefix = tmp_path / "elsewhere" / "widget"
    prefix.mkdir(parents=True)

    package = GitlabPackageDependency(
        _develop_env(tmp_path, monkeypatch),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop=str(prefix),
    )

    assert package.package_dir() == str(prefix)


def test_a_develop_path_is_reported_as_a_develop_tree_not_a_dependency_tree(
    tmp_path, monkeypatch
):
    """Storage listing and removal must not treat a hand-managed copy as cuppa's."""
    prefix = tmp_path / "widget"
    prefix.mkdir()

    package = GitlabPackageDependency(
        _develop_env(tmp_path, monkeypatch),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )
    paths = package.storage_paths()

    assert len(paths["develop"]) == 1
    assert os.path.samefile(paths["develop"][0], prefix)
    assert paths["dependencies"] == []
    assert paths["downloads"] == []


def test_a_publisher_source_tree_is_not_swapped_in_as_a_prefix(
    tmp_path, monkeypatch
):
    """Publisher source stands down from prefix swap; resolve-only skips nested stage."""
    source = tmp_path / "widget"
    source.mkdir()
    (source / "sconstruct").write_text("import cuppa\n", encoding="utf-8")
    (source / "include").mkdir()

    package = GitlabPackageDependency(
        _develop_env(
            tmp_path,
            monkeypatch,
            # Resolve paths only: the fetch this implies is the tip's normal one,
            # not something this test needs to perform.
            storage_resolve_only=True,
        ),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )

    assert not package._using_develop
    assert package._develop_is_publisher_source
    # Resolve-only keeps the extraction path; a real --develop build stages locally.
    assert package.package_dir().startswith(str(tmp_path / "dependencies"))


def test_a_publisher_source_tree_is_not_swapped_in_during_a_cascade(
    tmp_path, monkeypatch
):
    """Cascade still treats a publisher develop path as source, not a prefix."""
    source = tmp_path / "widget"
    source.mkdir()
    (source / "sconstruct").write_text("import cuppa\n", encoding="utf-8")
    (source / "include").mkdir()

    package = GitlabPackageDependency(
        _develop_env(
            tmp_path,
            monkeypatch,
            storage_resolve_only=True,
            **{"build-and-publish-dependencies": True},
        ),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )

    assert not package._using_develop
    assert package._develop_is_publisher_source
    assert package.package_dir().startswith(str(tmp_path / "dependencies"))


def test_publisher_source_consume_discovers_existing_stage(tmp_path, monkeypatch):
    """--develop alone links an existing final/<package>/<version>/ (no nest)."""
    source = tmp_path / "widget"
    source.mkdir()
    (source / "sconstruct").write_text("import cuppa\n", encoding="utf-8")
    stage = (
        source / "_build" / "gcc" / "rel" / "x86_64" / "cxx2c"
        / "final" / "widget" / "1.2"
    )
    (stage / "include").mkdir(parents=True)
    (stage / "lib").mkdir()

    nested = []

    def _must_not_nest(*args, **kwargs):
        nested.append( True )
        raise AssertionError( "discovery mode must not nest-stage" )

    monkeypatch.setattr(
        "cuppa.package_managers.package_cascade.run_nested_stage",
        _must_not_nest,
    )

    package = GitlabPackageDependency(
        _develop_env(tmp_path, monkeypatch),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )

    assert not nested
    assert not package._using_develop
    assert package._develop_is_publisher_source
    assert os.path.samefile(package.package_dir(), stage)
    assert package.include_dir().endswith(os.path.join("include"))


def test_publisher_source_without_stage_errors_unless_stage_develop(
    tmp_path, monkeypatch
):
    source = tmp_path / "widget"
    source.mkdir()
    (source / "sconstruct").write_text("import cuppa\n", encoding="utf-8")

    with pytest.raises(SCons.Errors.StopError, match="--stage-develop"):
        GitlabPackageDependency(
            _develop_env(tmp_path, monkeypatch),
            registry="https://gitlab.example/api/v4/projects/1",
            package="widget",
            version="1.2",
            variant="rel",
            develop="../widget",
        )


def test_stage_develop_nests_then_consumes_stage(tmp_path, monkeypatch):
    source = tmp_path / "widget"
    source.mkdir()
    (source / "sconstruct").write_text("import cuppa\n", encoding="utf-8")
    stage = (
        source / "_build" / "gcc" / "rel" / "x86_64" / "cxx2c"
        / "final" / "widget" / "1.2"
    )

    def _nest(env, publisher_dir, label):
        (stage / "include").mkdir(parents=True)
        (stage / "lib").mkdir()

    monkeypatch.setattr(
        "cuppa.package_managers.package_cascade.run_nested_stage",
        _nest,
    )

    package = GitlabPackageDependency(
        _develop_env(tmp_path, monkeypatch, **{"stage-develop": True}),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )

    assert os.path.samefile(package.package_dir(), stage)


def test_legacy_prefix_develop_still_swaps_in_with_a_note(
    tmp_path, monkeypatch, caplog
):
    prefix = tmp_path / "widget"
    (prefix / "include").mkdir(parents=True)
    (prefix / "lib").mkdir()

    import logging
    caplog.set_level(logging.INFO)

    package = GitlabPackageDependency(
        _develop_env(tmp_path, monkeypatch),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )

    assert package._using_develop
    assert os.path.samefile(package.package_dir(), prefix)
    assert any("built package prefix" in r.message for r in caplog.records)


def test_a_built_prefix_is_still_swapped_in_during_a_cascade(tmp_path, monkeypatch):
    """A publisher build stages cuppa-publish.json beside include/ and lib/.

    Reading that as a publisher tree would take a package for the project that built it.
    """
    prefix = tmp_path / "widget"
    (prefix / "include").mkdir(parents=True)
    (prefix / "lib").mkdir()
    (prefix / "cuppa-publish.json").write_text("{}", encoding="utf-8")

    package = GitlabPackageDependency(
        _develop_env(
            tmp_path, monkeypatch, **{"build-and-publish-dependencies": True}
        ),
        registry="https://gitlab.example/api/v4/projects/1",
        package="widget",
        version="1.2",
        variant="rel",
        develop="../widget",
    )

    assert package._using_develop
    assert os.path.samefile(package.package_dir(), prefix)
