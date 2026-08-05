import json
import re
from pathlib import Path

import pytest

from cuppa.core.dependency_identity import gitlab_archive_name
from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct
from tests.integration.test_list_dependencies import own_home, plant_archives_and_downloads, strip_ansi


pytestmark = pytest.mark.integration


def _json_payload(result):
    match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
    assert match, result.stdout
    return json.loads(match.group(0))


def _boost_package_sconstruct():
    return """\
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
"""


def test_list_downloads_hierarchical_text_and_json(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    planted = plant_archives_and_downloads(storage)
    leftover = storage / "downloads" / "orphan.tar.gz"
    leftover.write_bytes(b"orphan-bytes")
    write_sconstruct(project, body=_boost_package_sconstruct())

    listed = run_cuppa(
        project,
        "--offline",
        "--list-downloads",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    plain = strip_ansi(listed.stdout)
    assert "Downloads in" in plain
    assert "DEPENDENCY / DOWNLOAD" in plain
    assert "source archives" in plain
    assert "referenced from downloads" in plain
    assert "unreferenced downloads" in plain
    assert planted["fmt_11"] in plain or "11.1.4.zip" in plain
    assert planted["boost_folder"] in plain or "boost_1_91_0" in plain
    assert planted["gitlab_archive"] in plain
    assert "[E]" in plain
    assert "orphan.tar.gz" in plain
    assert "download total" in plain
    assert "[E] = dependency extracted from the download above" in plain

    verbose = run_cuppa(
        project,
        "--offline",
        "--list-downloads",
        "--list-format=verbose",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(verbose)
    verbose_plain = strip_ansi(verbose.stdout)
    assert "LOCATION" in verbose_plain
    assert "orphan.tar.gz" in verbose_plain

    as_json = run_cuppa(
        project,
        "--offline",
        "--list-downloads",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(as_json)
    payload = _json_payload(as_json)
    assert payload["archive_count"] >= 4
    kinds = {entry["kind"] for entry in payload["entries"]}
    assert "archive" in kinds
    assert "product" in kinds
    labels = {entry.get("label") for entry in payload["entries"]}
    assert planted["gitlab_archive"] in labels
    assert "orphan.tar.gz" in labels
    assert any(entry.get("kind") == "product" for entry in payload["entries"])
    assert payload["tree"]["sections"]


def test_list_downloads_marks_selected_gitlab_archive_referenced(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    deps = storage / "dependencies"
    downloads = storage / "downloads"
    deps.mkdir(parents=True)
    downloads.mkdir(parents=True)
    write_sconstruct(project, body=_boost_package_sconstruct())

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
    tool_variant = missing[0].get("tool_variant")
    selected_path = missing[0]["path"]
    assert tool_variant and selected_path

    selected = Path(selected_path)
    selected.mkdir(parents=True)
    (selected / "include").mkdir(parents=True)
    (selected / "include" / "boost.hpp").write_text("//\n", encoding="utf-8")

    archive = gitlab_archive_name("boost", tool_variant)
    pkg_dir = downloads / "packages" / "boost" / "1.91"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / archive).write_bytes(b"pkg-bytes")
    leftover_name = "boost_debian_clang999_rel_x86_64_cxx2c.tar.gz"
    if leftover_name == archive:
        leftover_name = "boost_debian_gcc999_rel_x86_64_cxx2c.tar.gz"
    (pkg_dir / leftover_name).write_bytes(b"other-pkg")

    downloads_listed = run_cuppa(
        project,
        "--offline",
        "--list-downloads",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(downloads_listed)
    data = _json_payload(downloads_listed)
    archives = [entry for entry in data["entries"] if entry.get("kind") == "archive"]
    by_label = {entry["label"]: entry for entry in archives}
    assert archive in by_label
    assert by_label[archive]["state"] == "referenced"
    assert by_label[archive]["dependency"] == "boost_package"
    assert leftover_name in by_label
    assert by_label[leftover_name]["state"] == "unreferenced"
    products = [entry for entry in data["entries"] if entry.get("kind") == "product"]
    assert any(entry.get("label") == "[E] {}".format(tool_variant) for entry in products)

    def find_archive_leaf(node, name):
        if node.get("kind") == "leaf" and node.get("label") == name:
            return node
        for child in node.get("children") or []:
            found = find_archive_leaf(child, name)
            if found is not None:
                return found
        return None

    archive_leaf = None
    for section in data["tree"]["sections"]:
        archive_leaf = find_archive_leaf(section, archive)
        if archive_leaf is not None:
            break
    assert archive_leaf is not None
    assert [child.get("label") for child in archive_leaf.get("children") or []] == [
            "[E] {}".format(tool_variant)
    ]
