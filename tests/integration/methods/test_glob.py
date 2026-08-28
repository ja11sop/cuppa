import re

import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_static_glob_flat_and_recursive(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "tests = env.StaticGlob('*_test.cpp', start='tests', recursive=False)\n"
        "assert len(tests) >= 2\n"
        "deep = env.StaticGlob('*.cpp', start='src')\n"
        "assert any('deep.cpp' in str(n).replace('\\\\\\\\','/') for n in deep)\n"
        "anchored = env.StaticGlob('*.cpp', start='#/src')\n"
        "assert any('deep.cpp' in str(n).replace('\\\\\\\\','/') for n in anchored)\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "env.Compile('src/nested/deep.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")
    assert find_under_build(project, "deep.*")


def test_deprecated_glob_aliases_still_work(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "tests = env.GlobFiles('*_test.cpp', start='tests')\n"
        "assert len(tests) >= 2\n"
        "deep = env.RecursiveGlob('*.cpp', start='src')\n"
        "assert any('deep.cpp' in str(n).replace('\\\\\\\\','/') for n in deep)\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")
    combined = re.sub(
        r'\x1b\[[0-9;]*m',
        '',
        (result.stdout or "") + (result.stderr or ""),
    )
    assert "env.GlobFiles() is deprecated" in combined
    assert "env.RecursiveGlob() is deprecated" in combined


def test_filter_path_parity_with_static_glob(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "candidates = env.StaticGlob('*.cpp', start='src')\n"
        "deep = env.Filter(candidates, match='src/nested/*.cpp')\n"
        "assert any('deep.cpp' in str(n).replace('\\\\\\\\','/') for n in deep)\n"
        "tests = env.StaticGlob('*.cpp', start='tests', recursive=False)\n"
        "hello = env.Filter(tests, match='tests/*_test.cpp')\n"
        "assert len(hello) >= 1\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")


def test_scons_glob_is_not_recursive(tmp_path):
    """SCons Glob matches do not span '/'; '**' is one path segment, not a tree walk."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "starstar = env.Glob('#/src/**/*.cpp')\n"
        "paths = [str(n).replace('\\\\\\\\', '/') for n in starstar]\n"
        "assert any('nested/deep.cpp' in p for p in paths), paths\n"
        # Files directly in src/ are outside one '**' segment.
        "assert not any(p.rstrip('/').endswith('src/hello.cpp') for p in paths), paths\n"
        "top = env.Glob('#/src/*.cpp')\n"
        "top_paths = [str(n).replace('\\\\\\\\', '/') for n in top]\n"
        "assert any(p.endswith('hello.cpp') for p in top_paths), top_paths\n"
        "walked = env.StaticGlob('*.cpp', start='#/src')\n"
        "walked_paths = [str(n).replace('\\\\\\\\', '/') for n in walked]\n"
        "assert any('hello.cpp' in p for p in walked_paths), walked_paths\n"
        "assert any('deep.cpp' in p for p in walked_paths), walked_paths\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_scons_glob_plus_filter_flat_directory(tmp_path):
    """Documented flat-dir recipe: Glob one directory, then Filter."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "candidates = env.Glob('#/tests/*.cpp')\n"
        "assert len(candidates) >= 2\n"
        "tests = env.Filter(candidates, match='*_test.cpp')\n"
        "assert len(tests) >= 2\n"
        "rel = env.Filter(candidates, match='tests/hello_test.cpp')\n"
        "assert len(rel) == 1\n"
        "env.BuildTest('hello_test', rel[0])\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")


def test_static_glob_plus_filter_exclude_detail(tmp_path):
    project = copy_dummy_project(tmp_path)
    detail = project / "src" / "nested" / "detail"
    detail.mkdir(parents=True)
    (detail / "hidden.cpp").write_text("int hidden() { return 0; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "candidates = env.StaticGlob('*.cpp', start='#/src')\n"
        "kept = env.Filter(candidates, match='*.cpp', exclude='*/detail/*')\n"
        "paths = [str(n).replace('\\\\\\\\', '/') for n in kept]\n"
        "assert any('deep.cpp' in p for p in paths), paths\n"
        "assert any('hello.cpp' in p for p in paths), paths\n"
        "assert not any('hidden.cpp' in p for p in paths), paths\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
