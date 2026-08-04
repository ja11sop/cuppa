import json
import re

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct


pytestmark = pytest.mark.integration


def own_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "USERPROFILE": str(home)}


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def plant_realistic_dependencies_root(storage):
    """Layouts that match a shared legacy dependencies root."""
    deps = storage / "dependencies"

    vcs = deps / "git_https_github.com__fmtlib_fmt.git"
    (vcs / "include" / "fmt").mkdir(parents=True)
    (vcs / "test" / "gtest").mkdir(parents=True)
    (vcs / "readme").write_text("fmt\n", encoding="utf-8")

    package = deps / "gcc153_rel_x86_64_cxx2c" / "boost" / "1.91"
    package.mkdir(parents=True)
    (package / "include" / "boost").mkdir(parents=True)
    (package / "include" / "boost" / "version.hpp").write_text("//\n", encoding="utf-8")

    branched = deps / "git_ssh_git@host__org_widget@master"
    branched.mkdir(parents=True)
    (branched / "src").mkdir()
    (branched / "src" / "a.cpp").write_text("int a;\n", encoding="utf-8")

    return deps, vcs, package, branched


def plant_archives_and_downloads(storage):
    """GitHub release extracts + matching downloads; one tag without a download."""
    deps = storage / "dependencies"
    downloads = storage / "downloads"
    downloads.mkdir(parents=True)

    fmt_11 = "https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip"
    fmt_12 = "https_github.com__fmtlib_fmt_archive_refs_tags_12.2.0.zip"
    for name in (fmt_11, fmt_12):
        folder = deps / name
        folder.mkdir(parents=True)
        (folder / "include").mkdir()
        (folder / "include" / "fmt").mkdir()
        (folder / "include" / "fmt" / "core.h").write_text("//\n", encoding="utf-8")

    (downloads / fmt_11).write_bytes(b"zip-bytes")

    boost_folder = (
        "https_archives.boost.io__release_1.91.0_source_boost_1_91_0.tar.gz"
    )
    boost = deps / boost_folder
    boost.mkdir(parents=True)
    (boost / "boost").mkdir()
    (boost / "boost" / "version.hpp").write_text("//\n", encoding="utf-8")
    (downloads / boost_folder).write_bytes(b"tar-bytes")

    gitlab = deps / "gcc153_rel_x86_64_cxx2c" / "boost" / "1.91"
    gitlab.mkdir(parents=True)
    (gitlab / "include" / "boost").mkdir(parents=True)
    archive = "boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz"
    pkg_dir = downloads / "packages" / "boost" / "1.91"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / archive).write_bytes(b"pkg-bytes")

    return {
        "fmt_11": fmt_11,
        "fmt_12": fmt_12,
        "boost_folder": boost_folder,
        "gitlab_archive": archive,
    }


def a_project_with_planted_dependency(tmp_path):
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    plant_realistic_dependencies_root(storage)
    write_sconstruct(project)
    return project, storage


def test_list_dependencies_reports_ownership_units_not_nested_source(tmp_path):
    project, storage = a_project_with_planted_dependency(tmp_path)

    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    plain = strip_ansi(listed.stdout)
    assert "Dependencies in" in plain
    assert "DEPENDENCY" in plain
    assert "REMARK" in plain

    # Package / VCS trees appear; nested include/test folders do not.
    assert re.search(r"\bboost\b", plain)
    assert "1.91" in plain or "gitlab packages" in plain
    assert "unreferenced" in plain

    # Three ownership units — not every nested include/test folder.
    assert "3 entries" in plain
    # Default text view has no LOCATION column.
    assert "LOCATION" not in plain.split("\n")[0:20] or "LOCATION" not in [
        line for line in plain.splitlines() if "SIZE" in line and "DEPENDENCY" in line
    ][0]


def test_list_dependencies_json(tmp_path):
    project, storage = a_project_with_planted_dependency(tmp_path)

    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    match = re.search(r"\{.*\}", listed.stdout, re.DOTALL)
    assert match, listed.stdout
    payload = json.loads(match.group(0))
    assert len(payload["entries"]) == 3
    names = {entry["dependency"] for entry in payload["entries"]}
    assert "boost" in names
    assert any("fmt" in name for name in names)
    assert any("widget" in name for name in names)
    boost = next(entry for entry in payload["entries"] if entry["dependency"] == "boost")
    assert boost["qualifier"] == "1.91"
    assert boost["tool_variant"] == "gcc153_rel_x86_64_cxx2c"
    assert boost["state"] == "unreferenced"
    assert "tree" in payload
    assert "sections" in payload["tree"]


def test_list_dependencies_second_pass_still_works(tmp_path):
    project, storage = a_project_with_planted_dependency(tmp_path)

    assert_success(run_cuppa(
        project,
        "--list-dependencies",
        "--exact-sizes",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    ))
    listed = run_cuppa(
        project,
        "--list-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    assert "3 entries" in listed.stdout


def test_list_dependencies_reports_missing_expected_location(tmp_path):
    """A default location dependency with no tree on disk appears as STATE missing."""
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

    listed = run_cuppa(
        project,
        "--offline",
        "--list-dependencies",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    plain = strip_ansi(listed.stdout)
    assert "widget" in plain
    assert "missing" in plain
    assert "1 missing" in plain or ", 1 missing" in plain
    assert "example.com/org/widget.git" in plain or "git+https://example.com/org/widget.git" in plain
    err = listed.stderr or ""
    assert "AttributeError" not in err
    assert "'tuple' object has no attribute" not in err

    as_json = run_cuppa(
        project,
        "--offline",
        "--list-dependencies",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(as_json)
    match = re.search(r"\{.*\}", as_json.stdout, re.DOTALL)
    assert match, as_json.stdout
    payload = json.loads(match.group(0))
    assert payload.get("missing_count", 0) >= 1
    missing = [entry for entry in payload["entries"] if entry["state"] == "missing"]
    assert any(entry["dependency"] == "widget" for entry in missing)
    assert any(
            (entry.get("remote_location") or "").find("widget") >= 0
            for entry in missing
    )


def test_list_dependencies_verbose_archives_and_download_mark(tmp_path):
    """Verbose LOCATION groups GitHub/Boost archives and marks cached downloads with [D]."""
    project = copy_dummy_project(tmp_path)
    storage = tmp_path / "storage"
    plant_archives_and_downloads(storage)
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
        "--list-format=verbose",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(listed)
    plain = strip_ansi(listed.stdout)

    assert "LOCATION" in plain
    assert "archives" in plain
    assert "github.com/fmtlib/fmt" in plain
    assert "11.1.4" in plain
    assert "12.2.0" in plain
    assert "https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip" in plain
    assert "https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip" in plain
    # Only the tag with a downloads-root file is marked.
    assert "[D] https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip" in plain
    assert "[D] https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip" not in plain

    assert re.search(r"\bboost\b", plain)
    assert "1.91.0" in plain or "boost_1_91_0" in plain or "archives.boost.io" in plain
    assert "[D] https://archives.boost.io/release/1.91.0/source/boost_1_91_0.tar.gz" in plain

    # GitLab: registry URL on the version row without [D]; archive leaf with [D].
    assert "gitlab.example/api/v4/projects/1/boost/1.91" in plain
    assert "[D] https://gitlab.example/api/v4/projects/1/boost/1.91" not in plain
    assert "[D] boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz" in plain

    assert "[D] = archive present under downloads" in plain
    assert "corrupt archive" in plain

    as_json = run_cuppa(
        project,
        "--offline",
        "--list-dependencies",
        "--list-format=json",
        "--storage-root={}".format(storage),
        extra_env=own_home(tmp_path),
    )
    assert_success(as_json)
    match = re.search(r"\{.*\}", as_json.stdout, re.DOTALL)
    assert match, as_json.stdout
    payload = json.loads(match.group(0))
    fmt_entries = [
            entry for entry in payload["entries"]
            if (entry.get("short_name") or "") == "github.com/fmtlib/fmt"
            or "fmt_archive" in (entry.get("dependency") or "")
    ]
    assert len(fmt_entries) >= 2
    by_qual = {entry.get("qualifier"): entry for entry in fmt_entries}
    assert by_qual.get("11.1.4", {}).get("has_download") is True
    assert by_qual.get("12.2.0", {}).get("has_download") is False
    assert by_qual["11.1.4"].get("download_path")
    assert by_qual["11.1.4"].get("remote_location", "").endswith("11.1.4.zip")

    gitlab_rows = [
            entry for entry in payload["entries"]
            if entry.get("type") == "gitlab" and entry.get("qualifier") == "1.91"
    ]
    assert gitlab_rows
    assert any(entry.get("has_download") for entry in gitlab_rows)
    assert any(
            (entry.get("remote_location") or "").endswith("/boost/1.91")
            for entry in gitlab_rows
    )
