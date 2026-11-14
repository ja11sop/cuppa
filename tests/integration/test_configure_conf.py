import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_save_and_show_conf(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\nenv.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    saved = run_cuppa(project, "--dbg", "--save-conf")
    assert_success(saved)
    conf = project / "configure.conf"
    assert conf.exists()
    shown = run_cuppa(project, "--show-conf")
    assert_success(shown)
    assert "dbg" in shown.stdout or conf.read_text()


def test_show_global_conf_reports_home_file_only(tmp_path, isolate_cuppa_home):
    project = copy_dummy_project(tmp_path / "project")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\nenv.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    home = isolate_cuppa_home
    digest = "aaaaaaaaaaaaaaaa"
    (home / ".cuppaconfig").write_text(
        "offline = True\n"
        "toolchains = ['gcc']\n"
        "gitlab_package_latest_{} = '1.92'\n"
        "gitlab_package_latest_label_{} = 'boost'\n"
        "gitlab_package_latest_bbbbbbbbbbbbbbbb = '1.34.8'\n".format(
            digest, digest
        ),
        encoding="utf-8",
    )
    (project / "configure.conf").write_text(
        "dbg = True\noffline = False\n",
        encoding="utf-8",
    )

    shown = run_cuppa(project, "--show-global-conf")
    assert_success(shown)
    out = shown.stdout or ""
    assert "Running in CONFIGURE mode" in out
    assert "global configuration" in out.lower() or "~/.cuppaconfig" in out
    assert "offline" in out
    assert "toolchains" in out
    # Project-only keys must not appear on the global-only equivalent line.
    assert "--dbg" not in out
    equivalent = [
            line for line in out.splitlines() if line.startswith( "cuppa -D " )
    ]
    assert equivalent
    assert "gitlab_package_latest_label_" not in equivalent[0]
    assert "registry latest mapping" in out
    assert "boost" in out
    assert "(unknown package)" in out
    assert "Nothing to be done" in out


def test_update_conf_stores_one_transcript_choice(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    conf = project / "configure.conf"
    conf.write_text("terse_output = True\n", encoding="utf-8")
    updated = run_cuppa(project, "--normal-output", "--update-conf")
    assert_success(updated)
    text = conf.read_text(encoding="utf-8")
    assert "terse_output = False" in text
