# Integration: --stage-develop nest-builds location develop Cuppa projects.

import os

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def own_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _write_dep(dep):
    write_sconstruct(dep)
    write_sconscript(
        dep,
        """\
Import('env')
env.AppendUnique(CPPPATH=['#/include'])
env.BuildStaticLib('widget', 'src/hello.cpp')
""",
    )


def _write_tip(tip, develop_path):
    write_sconstruct(
        tip,
        body="""\
import cuppa

Widget = cuppa.location_dependency(
    'widget',
    location='https://example.com/org/widget.git',
    develop={develop!r},
    include='include',
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
env.BuildWith('widget')
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


def test_location_develop_without_stage_does_not_nest(tmp_path):
    dep = copy_dummy_project(tmp_path / "dep")
    _write_dep(dep)

    tip = copy_dummy_project(tmp_path / "tip")
    _write_tip(tip, os.path.relpath(str(dep), str(tip)))

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        timeout=360,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)
    assert "develop stage" not in result.stdout


def test_location_stage_develop_nests_project_build(tmp_path):
    dep = copy_dummy_project(tmp_path / "dep")
    _write_dep(dep)

    tip = copy_dummy_project(tmp_path / "tip")
    _write_tip(tip, os.path.relpath(str(dep), str(tip)))

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        "--stage-develop",
        timeout=360,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)
    assert "develop stage" in result.stdout
    assert any(dep.rglob("_build")), "nested build should create dep/_build"


def test_location_stage_develop_nests_clean(tmp_path):
    dep = copy_dummy_project(tmp_path / "dep")
    _write_dep(dep)
    assert_success(
        run_cuppa(dep, "--dbg", timeout=360, extra_env=own_home(tmp_path))
    )
    assert any(dep.rglob("_build"))

    tip = copy_dummy_project(tmp_path / "tip")
    _write_tip(tip, os.path.relpath(str(dep), str(tip)))

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        "--stage-develop",
        "-c",
        timeout=360,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)
    assert "develop stage" in result.stdout
