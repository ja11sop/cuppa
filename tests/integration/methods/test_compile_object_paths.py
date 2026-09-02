import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def _write_collision_fixture(project):
    (project / "src" / "detail" / "router").mkdir(parents=True, exist_ok=True)
    (project / "src" / "buffers" / "detail").mkdir(parents=True, exist_ok=True)
    (project / "src" / "detail" / "router" / "test.cpp").write_text(
        "namespace detail { int test() { return 1; } }\n",
        encoding="utf-8",
    )
    (project / "src" / "detail" / "except.cpp").write_text(
        "namespace detail { int except() { return 1; } }\n",
        encoding="utf-8",
    )
    (project / "src" / "buffers" / "detail" / "except.cpp").write_text(
        "namespace buffers { namespace detail { int except() { return 2; } } }\n",
        encoding="utf-8",
    )
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "sources = env.RecursiveGlob('except.cpp', start='src')\n"
        "assert len(sources) == 2\n"
        "env.BuildStaticLib('excepts', sources)\n"
        "env.Compile('src/detail/router/test.cpp')\n",
    )


def _objects_under_working(project):
    by_working = {}
    for working in sorted(project.glob("_build/**/working")):
        objects = sorted(
            path.relative_to(working)
            for path in working.rglob("*")
            if path.is_file() and path.suffix in (".o", ".obj")
        )
        by_working[str(working.relative_to(project))] = objects
    return by_working


def _object_suffix(by_working):
    for objects in by_working.values():
        for path in objects:
            if path.suffix in (".o", ".obj"):
                return path.suffix
    return None


def _assert_working_layout(by_working):
    assert by_working, "expected object files under working/"
    obj_suffix = _object_suffix(by_working)
    assert obj_suffix is not None, "expected object files under working/"
    expected = [
        f"src/buffers/detail/except{obj_suffix}",
        f"src/detail/except{obj_suffix}",
        f"src/detail/router/test{obj_suffix}",
    ]
    for working_rel, objects in by_working.items():
        rel_paths = [str(path).replace("\\", "/") for path in objects]
        for expected_path in expected:
            assert expected_path in rel_paths, working_rel
        for rel_posix in rel_paths:
            assert not rel_posix.startswith("_build/"), (
                "object path must be relative to working/, not prefixed with build_root: "
                + rel_posix
            )
            assert "/working/" not in rel_posix, (
                "working_dir must not repeat inside working/: " + rel_posix
            )
            assert rel_posix != f"except{obj_suffix}", "flat basename collision layout"
            assert rel_posix != f"test{obj_suffix}", "flat basename collision layout"


def test_compile_nested_same_basename_sources_dbg_and_rel(tmp_path):
    project = copy_dummy_project(tmp_path)
    _write_collision_fixture(project)

    result = run_cuppa(project, "--dbg", "--rel", "--offline")
    assert_success(result)

    by_working = _objects_under_working(project)
    assert len(by_working) == 2, "expected dbg and rel working trees"
    _assert_working_layout(by_working)


def test_compile_object_paths_stable_from_nested_launch(tmp_path):
    project = copy_dummy_project(tmp_path)
    _write_collision_fixture(project)
    nested = project / "nested" / "pkg"
    nested.mkdir(parents=True)

    root_result = run_cuppa(project, "--dbg", "--rel", "--offline")
    assert_success(root_result)
    root_layout = _objects_under_working(project)

    import shutil
    shutil.rmtree(project / "_build")

    # Nested -D + two MSVC variants can exceed the default 180s on Windows CI.
    nested_result = run_cuppa(
        nested,
        "--dbg",
        "--rel",
        "--offline",
        "--scripts=../../sconscript",
        timeout=360,
    )
    assert_success(nested_result)
    nested_layout = _objects_under_working(project)

    assert nested_layout == root_layout
