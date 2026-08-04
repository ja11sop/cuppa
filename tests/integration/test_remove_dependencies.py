"""Integration tests for --remove-dependencies (Slice D)."""

import json
import re

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct
from tests.integration.test_list_dependencies import own_home, strip_ansi


pytestmark = pytest.mark.integration


def _json_payload(result):
    match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
    assert match, result.stdout
    return json.loads(match.group(0))


def test_remove_dependencies_unknown_name(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    (storage / "dependencies").mkdir(parents=True)
    write_sconstruct(
        project,
        body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='git+https://example.com/org/widget.git@master',
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Widget],
    default_dependencies=['widget'],
)
""",
    )
    removed = run_cuppa(
        project,
        "--offline",
        "--remove-dependencies=widgt",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert removed.returncode != 0
    plain = strip_ansi(removed.stdout + (removed.stderr or ""))
    assert "unknown" in plain.lower()
    assert "widgt" in plain
    assert "widget" in plain


def test_remove_location_keeps_sibling_branch(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    master = deps / "git_https_example.com__org_widget.git@master"
    feature = deps / "git_https_example.com__org_widget.git@feature_x"
    master.mkdir(parents=True)
    feature.mkdir(parents=True)
    (master / "src").mkdir()
    (master / "src" / "a.cpp").write_text("int a;\n", encoding="utf-8")
    (feature / "src").mkdir()
    (feature / "src" / "b.cpp").write_text("int b;\n", encoding="utf-8")

    write_sconstruct(
        project,
        body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='git+https://example.com/org/widget.git@master',
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Widget],
    default_dependencies=['widget'],
)
""",
    )

    dry = run_cuppa(
        project,
        "--offline",
        "-n",
        "--remove-dependencies=widget",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(dry)
    plain = strip_ansi(dry.stdout)
    assert "Would remove" in plain or "would rm" in plain.lower()
    assert master.is_dir()
    assert feature.is_dir()

    removed = run_cuppa(
        project,
        "--offline",
        "--remove-dependencies=widget",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "Removed" in plain
    assert "Leaving" in plain
    assert "feature_x" in plain or "@feature_x" in plain
    assert not master.exists()
    assert feature.is_dir()
    assert "list-dependencies" in plain


def test_remove_develop_skips_working_copy(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    (storage / "dependencies").mkdir(parents=True)
    develop = tmp_path / "coding" / "widget"
    develop.mkdir(parents=True)
    (develop / "include").mkdir()
    (develop / "include" / "w.hpp").write_text("//\n", encoding="utf-8")

    write_sconstruct(
        project,
        body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='git+https://example.com/org/widget.git@master',
    develop={develop!r},
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Widget],
    default_dependencies=['widget'],
)
""".format(develop=str(develop)),
    )

    removed = run_cuppa(
        project,
        "--offline",
        "--develop",
        "--remove-dependencies=widget",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "develop" in plain.lower() or "Skipped" in plain
    assert develop.is_dir()
    assert (develop / "include" / "w.hpp").is_file()


def test_remove_gitlab_package_keeps_other_toolchain(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    deps.mkdir(parents=True)

    write_sconstruct(
        project,
        body="""\
import cuppa

Boost = cuppa.package_dependency(
    'boost_package',
    package_manager='gitlab',
    registry='https://gitlab.example/api/v4/projects/1',
    package='boost',
    version='1.91',
)

cuppa.run(
    default_variants=['dbg'],
    dependencies=[Boost],
    default_dependencies=['boost_package'],
)
""",
    )

    listed = run_cuppa(
        project,
        "--offline",
        "--list-dependencies",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    payload = _json_payload(listed)
    missing = [
            entry for entry in payload["entries"]
            if entry.get("dependency") == "boost_package" and entry.get("state") == "missing"
    ]
    assert missing, payload["entries"]
    selected_path = missing[0]["path"]
    tool_variant = missing[0].get("tool_variant")
    assert tool_variant
    assert selected_path

    from pathlib import Path
    selected = Path(selected_path)
    selected.mkdir(parents=True)
    (selected / "include").mkdir(parents=True)
    (selected / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")

    other_variant = "clang999_dbg_x86_64_cxx2c"
    if other_variant == tool_variant:
        other_variant = "gcc999_dbg_x86_64_cxx2c"
    other = deps / other_variant / "boost" / "1.91"
    other.mkdir(parents=True)
    (other / "include").mkdir(parents=True)
    (other / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")

    removed = run_cuppa(
        project,
        "--offline",
        "--dbg",
        "--remove-dependencies=boost_package",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(removed)
    plain = strip_ansi(removed.stdout)
    assert "Removed" in plain or "removed" in plain
    assert not selected.exists()
    assert other.is_dir()
    assert "Leaving" in plain
