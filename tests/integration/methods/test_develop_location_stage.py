# Integration: --stage-develop nest-builds location develop Cuppa projects.

import logging
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.helpers.cuppa_runner import (
    assert_success,
    find_final_binaries,
    run_cuppa,
)
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript
from tests.helpers.toolchains import require_modules_capable_toolchain


logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULES_PROJECT = REPO_ROOT / "tests" / "fixtures" / "modules_project"


def own_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _modules_toolchain_flag():
    alias, driver, major = require_modules_capable_toolchain()
    logger.info(
        "Location-stage modules test using toolchain %s (%s major %s)",
        alias,
        driver,
        major,
    )
    return "--toolchains={}".format(alias)


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


_STAGED_DEP_SCONSCRIPT = """\
Import('env')
env.AppendUnique(CPPPATH=['#/include'])
lib = env.BuildStaticLib('widget', 'src/hello.cpp')
env.StageLocationDevelop('widget', lib, include_dir='#/include')
"""


_STAGED_TIP_TEST = """\
#include <dummy/hello.hpp>
#include <cstdlib>

int hello_value();

int main()
{
    return hello_value() == dummy_answer() ? EXIT_SUCCESS : EXIT_FAILURE;
}
"""


def test_location_stage_develop_tip_consumes_staged_prefix(tmp_path):
    """Example A/B/C: nest stages final/widget/develop; tip links include+lib from that prefix."""
    dep = copy_dummy_project(tmp_path / "dep")
    write_sconstruct(dep)
    write_sconscript(dep, _STAGED_DEP_SCONSCRIPT)

    tip = copy_dummy_project(tmp_path / "tip")
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
""".format(develop=os.path.relpath(str(dep), str(tip))),
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
        _STAGED_TIP_TEST, encoding="utf-8"
    )

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
    assert "locally staged location" in result.stdout
    stages = [
        path for path in dep.rglob("*")
        if path.is_dir()
        and path.name == "develop"
        and path.parent.name == "widget"
        and "final" in path.parts
    ]
    assert stages, "expected final/widget/develop under the location develop tree"
    assert (stages[0] / "include").is_dir()
    assert (stages[0] / "lib").is_dir()


def test_location_stage_develop_without_prefix_keeps_path_swap(tmp_path):
    """Example D: nest builds but no package-shaped stage → tip does not claim staged consume."""
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
    assert "locally staged location" not in result.stdout


def test_location_develop_discovers_existing_stage_without_nesting(tmp_path):
    """Example B discover half: pre-staged prefix is consumed with --develop alone."""
    dep = copy_dummy_project(tmp_path / "dep")
    write_sconstruct(dep)
    write_sconscript(dep, _STAGED_DEP_SCONSCRIPT)
    assert_success(
        run_cuppa(dep, "--dbg", timeout=360, extra_env=own_home(tmp_path))
    )
    stages = [
        path for path in dep.rglob("*")
        if path.is_dir()
        and path.name == "develop"
        and path.parent.name == "widget"
        and "final" in path.parts
    ]
    assert stages

    tip = copy_dummy_project(tmp_path / "tip")
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
""".format(develop=os.path.relpath(str(dep), str(tip))),
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
        _STAGED_TIP_TEST, encoding="utf-8"
    )

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        timeout=360,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)
    assert "develop stage" not in result.stdout
    assert "locally staged location" in result.stdout


def test_location_stage_develop_tip_consumes_packaged_modules(tmp_path):
    """L3 modules: nest stages BMIs under final/.../modules/; tip imports via BuildWith."""
    toolchain_flag = _modules_toolchain_flag()

    dep = tmp_path / "mathlib"
    shutil.copytree(MODULES_PROJECT, dep)
    write_sconstruct(dep)
    write_sconscript(
        dep,
        """\
Import('env')
lib = env.BuildStaticLib('mathlib', ['math.cppm'])
env.StageLocationDevelop('mathlib', lib, include_dir='#/include')
""",
    )

    tip = tmp_path / "tip"
    tip.mkdir()
    shutil.copy(MODULES_PROJECT / "apps" / "main.cpp", tip / "main.cpp")
    write_sconstruct(
        tip,
        body="""\
import cuppa

Mathlib = cuppa.location_dependency(
    'mathlib',
    location='https://example.com/org/mathlib.git',
    develop={develop!r},
    include='include',
)

cuppa.run(
    default_variants=['dbg'],
    import_dependencies=[Mathlib],
    auto_enable_dependencies=[Mathlib],
)
""".format(develop=os.path.relpath(str(dep), str(tip))),
    )
    write_sconscript(
        tip,
        """\
Import('env')
env.BuildWith('mathlib')
env.Build('math_app', ['main.cpp'])
""",
    )

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        "--stage-develop",
        "--modules",
        "--stdcpp=c++20",
        toolchain_flag,
        timeout=420,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)
    assert "develop stage" in result.stdout
    assert "locally staged location" in result.stdout

    stages = [
        path for path in dep.rglob("*")
        if path.is_dir()
        and path.name == "develop"
        and path.parent.name == "mathlib"
        and "final" in path.parts
    ]
    assert stages, "expected final/mathlib/develop under the location develop tree"
    stage = stages[0]
    assert (stage / "include").is_dir()
    assert (stage / "lib").is_dir()
    assert (stage / "modules" / "module-map.json").is_file()

    binaries = find_final_binaries(tip, "math_app")
    assert binaries
    ran = subprocess.run(
        [str(binaries[0])],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
