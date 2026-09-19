# Integration: --stage-develop-plan reports leaf-first order without nesting.

import os

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def own_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "USERPROFILE": str(home)}


def test_stage_develop_plan_reports_order_without_nesting(tmp_path):
    leaf = copy_dummy_project(tmp_path / "leaf")
    write_sconstruct(leaf)
    write_sconscript(
        leaf,
        "Import('env')\nenv.AppendUnique(CPPPATH=['#/include'])\n",
    )

    mid = copy_dummy_project(tmp_path / "mid")
    write_sconstruct(
        mid,
        body="""\
import cuppa
Leaf = cuppa.location_dependency(
    'leaf',
    location='https://example.com/org/leaf.git',
    develop={leaf!r},
    include='include',
)
cuppa.run(default_variants=['dbg'], import_dependencies=[Leaf])
""".format(leaf=os.path.relpath(str(leaf), str(mid))),
    )
    write_sconscript(mid, "Import('env')\nenv.BuildWith('leaf')\n")

    tip = copy_dummy_project(tmp_path / "tip")
    write_sconstruct(
        tip,
        body="""\
import cuppa
Mid = cuppa.location_dependency(
    'mid',
    location='https://example.com/org/mid.git',
    develop={mid!r},
    include='include',
)
Leaf = cuppa.location_dependency(
    'leaf',
    location='https://example.com/org/leaf.git',
    develop={leaf!r},
    include='include',
)
cuppa.run(
    default_variants=['dbg'],
    import_dependencies=[Mid, Leaf],
    auto_enable_dependencies=[Mid, Leaf],
)
""".format(
            mid=os.path.relpath(str(mid), str(tip)),
            leaf=os.path.relpath(str(leaf), str(tip)),
        ),
    )
    write_sconscript(tip, "Import('env')\n")

    result = run_cuppa(
        tip,
        "--dbg",
        "--develop",
        "--stage-develop-plan",
        timeout=120,
        extra_env=own_home(tmp_path),
    )
    assert_success(result)
    assert "Develop stage plan" in result.stdout
    assert "nothing was built or cleaned" in result.stdout
    assert "develop stage" not in result.stdout or "Develop stage plan" in result.stdout
    numbered = [line for line in result.stdout.splitlines() if " of 2" in line]
    assert len(numbered) >= 2
    assert "leaf" in numbered[0]
    assert "mid" in numbered[1]
    assert not any(leaf.rglob("_build"))
    assert not any(mid.rglob("_build"))
