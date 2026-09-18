# Integration: --develop discovers a package stage; --stage-develop nests a build.

import os

import pytest

from tests.helpers.cuppa_runner import assert_failure, assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


_PUBLISHER_SCONSCRIPT = """\
Import('env')
from cuppa.package_managers.gitlab import GitlabPackagePublisher
env.AppendUnique(CPPPATH=['#/include'])
lib = env.BuildStaticLib('widget', 'src/hello.cpp')
publisher = GitlabPackagePublisher(
    env,
    source_include_dir='#/include',
    source_lib_dir=env['abs_final_dir'],
    registry='https://gitlab.example/api/v4/projects/1',
    package='widget',
    version='1.0.0',
)
env.PublishPackage(lib, publisher)
"""


def own_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _write_tip(tip, develop_path, storage):
    write_sconstruct(
        tip,
        body="""\
import cuppa

Widget = cuppa.package_dependency(
    'widget',
    registry='https://gitlab.example/api/v4/projects/1',
    package='widget',
    version='1.0.0',
    develop={develop!r},
)

cuppa.run(
    default_variants=['dbg'],
    import_dependencies=[Widget],
    auto_enable_dependencies=[Widget],
)
""".format(develop=develop_path),
    )
    write_sconscript(
        tip,
        """\
Import('env')
env.BuildTest('hello_test', 'tests/hello_test.cpp')
""",
    )
    (tip / "tests" / "hello_test.cpp").write_text(
        """\
#include <dummy/hello.hpp>
#include <cstdlib>

int main()
{
    return EXIT_SUCCESS;
}
""",
        encoding="utf-8",
    )


def _stage_dirs(publisher):
    return [
        path for path in publisher.rglob("*")
        if path.is_dir() and path.name == "1.0.0"
        and path.parent.name == "widget"
        and "final" in path.parts
    ]


def test_develop_discovers_existing_stage_without_nesting(tmp_path):
    """--develop alone consumes a pre-built stage; no nested session."""
    publisher = copy_dummy_project(tmp_path / "publisher")
    write_sconstruct(publisher)
    write_sconscript(publisher, _PUBLISHER_SCONSCRIPT)
    assert_success(run_cuppa(publisher, "--dbg", timeout=360, extra_env=own_home(tmp_path)))
    assert _stage_dirs(publisher)

    tip = copy_dummy_project(tmp_path / "tip")
    storage = tmp_path / "storage"
    _write_tip(tip, os.path.relpath(str(publisher), str(tip)), storage)

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        "--storage-root={}".format(storage),
        timeout=360,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)
    assert "develop stage" not in result.stdout
    assert "locally staged package" in result.stdout
    assert not list(storage.rglob("packages/widget")) if storage.exists() else True


def test_develop_without_stage_fails_with_stage_develop_hint(tmp_path):
    publisher = copy_dummy_project(tmp_path / "publisher")
    write_sconstruct(publisher)
    write_sconscript(publisher, _PUBLISHER_SCONSCRIPT)

    tip = copy_dummy_project(tmp_path / "tip")
    storage = tmp_path / "storage"
    _write_tip(tip, os.path.relpath(str(publisher), str(tip)), storage)

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        "--storage-root={}".format(storage),
        timeout=120,
        extra_env=own_home(tmp_path),
    )
    assert_failure(result)
    assert "--stage-develop" in result.stdout


def test_stage_develop_nests_build_and_tip_consumes(tmp_path):
    """--develop --stage-develop nest-stages the package tree for the tip."""
    publisher = copy_dummy_project(tmp_path / "publisher")
    write_sconstruct(publisher)
    write_sconscript(publisher, _PUBLISHER_SCONSCRIPT)

    tip = copy_dummy_project(tmp_path / "tip")
    storage = tmp_path / "storage"
    _write_tip(tip, os.path.relpath(str(publisher), str(tip)), storage)

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        "--stage-develop",
        "--storage-root={}".format(storage),
        timeout=360,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)

    stages = _stage_dirs(publisher)
    assert stages, "expected a staged package under the publisher _build tree"
    assert (stages[0] / "include").is_dir()
    assert (stages[0] / "lib").is_dir()
    assert "develop stage" in result.stdout
    assert "locally staged" in result.stdout
    assert not list(storage.rglob("packages/widget")) if storage.exists() else True
