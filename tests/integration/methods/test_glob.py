import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


def test_recursive_glob_walks_tree_and_hash_start(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "deep = env.RecursiveGlob('*.cpp', start='src')\n"
        "paths = [str(n).replace('\\\\\\\\', '/') for n in deep]\n"
        "assert any('hello.cpp' in p for p in paths), paths\n"
        "assert any('nested/deep.cpp' in p or p.endswith('deep.cpp') for p in paths), paths\n"
        "anchored = env.RecursiveGlob('*.cpp', start='#/src')\n"
        "apaths = [str(n).replace('\\\\\\\\', '/') for n in anchored]\n"
        "assert any('deep.cpp' in p for p in apaths), apaths\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n"
        "env.Compile('src/nested/deep.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")
    assert find_under_build(project, "deep.*")


def test_glob_files_is_flat_only(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "flat = env.GlobFiles('*.cpp', start='src')\n"
        "paths = [str(n).replace('\\\\\\\\', '/') for n in flat]\n"
        "assert any(p.endswith('hello.cpp') for p in paths), paths\n"
        "assert not any('deep.cpp' in p for p in paths), paths\n"
        "tests = env.GlobFiles('*_test.cpp', start='tests')\n"
        "assert len(tests) >= 2\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_scons_glob_matrix_vs_recursive_glob(tmp_path):
    """Name the mismatch: directory Glob vs recursive snapshot walk."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "top = env.Glob('#/src/*.cpp')\n"
        "one = env.Glob('#/src/**/*.cpp')\n"  # one segment only — not a tree walk
        "walked = env.RecursiveGlob('*.cpp', start='#/src')\n"
        "def norm(nodes):\n"
        "    return sorted(str(n).replace('\\\\\\\\', '/') for n in nodes)\n"
        "top_p, one_p, walk_p = norm(top), norm(one), norm(walked)\n"
        "assert any(p.endswith('hello.cpp') for p in top_p), top_p\n"
        "assert not any('deep.cpp' in p for p in top_p), top_p\n"
        "assert any('nested/deep.cpp' in p for p in one_p), one_p\n"
        "assert not any(p.rstrip('/').endswith('src/hello.cpp') for p in one_p), one_p\n"
        "assert any('hello.cpp' in p for p in walk_p), walk_p\n"
        "assert any('deep.cpp' in p for p in walk_p), walk_p\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_filter_on_recursive_glob_and_scons_glob(tmp_path):
    project = copy_dummy_project(tmp_path)
    detail = project / "src" / "nested" / "detail"
    detail.mkdir(parents=True)
    (detail / "hidden.cpp").write_text("int hidden() { return 0; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "tree = env.RecursiveGlob('*.cpp', start='#/src')\n"
        "kept = env.Filter(tree, match='*.cpp', exclude='*/detail/*')\n"
        "kpaths = [str(n).replace('\\\\\\\\', '/') for n in kept]\n"
        "assert any('deep.cpp' in p for p in kpaths), kpaths\n"
        "assert any('hello.cpp' in p for p in kpaths), kpaths\n"
        "assert not any('hidden.cpp' in p for p in kpaths), kpaths\n"
        "nested = env.Filter(tree, match='src/nested/*.cpp')\n"
        "assert any('deep.cpp' in str(n).replace('\\\\\\\\', '/') for n in nested)\n"
        "flat = env.Glob('#/tests/*.cpp')\n"
        "tests = env.Filter(flat, match='*_test.cpp')\n"
        "assert len(tests) >= 2\n"
        "rel = env.Filter(flat, match='tests/hello_test.cpp')\n"
        "assert len(rel) == 1\n"
        "env.BuildTest('hello_test', rel[0])\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
    assert find_final_binaries(project, "hello_test")


def test_snapshot_vs_directory_glob_both_see_new_file_next_invocation(tmp_path):
    """Low-impact check: both APIs re-read with the sconscript each cuppa run."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    marker = project / "src" / "added_later.cpp"
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "walked = env.RecursiveGlob('*.cpp', start='src')\n"
        "flat = env.Glob('#/src/*.cpp')\n"
        "w = [str(n).replace('\\\\\\\\', '/') for n in walked]\n"
        "f = [str(n).replace('\\\\\\\\', '/') for n in flat]\n"
        "report = os.path.join(env['sconstruct_dir'], 'glob_report.txt')\n"
        "open(report, 'w').write('\\n'.join(w) + '\\n--\\n' + '\\n'.join(f))\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result1 = run_cuppa(project, "--dbg", "--test")
    assert_success(result1)
    report1 = (project / "glob_report.txt").read_text()
    assert "added_later.cpp" not in report1

    marker.write_text("int added_later() { return 0; }\n")
    assert marker.exists()
    result2 = run_cuppa(project, "--dbg", "--test")
    assert_success(result2)
    report2 = (project / "glob_report.txt").read_text()
    walked_part, flat_part = report2.split("--\n", 1)
    assert "added_later.cpp" in walked_part
    assert "added_later.cpp" in flat_part


def test_glob_files_and_scons_glob_same_flat_basenames(tmp_path):
    """Apples-to-apples flat match: same files, different node path forms / machinery."""
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "env.AppendUnique(CPPPATH=['#/include'])\n"
        "cuppa_nodes = env.GlobFiles('*.cpp', start='src')\n"
        "scons_nodes = env.Glob('#/src/*.cpp')\n"
        "def basenames(nodes):\n"
        "    return sorted(os.path.basename(str(n).replace('\\\\\\\\', '/')) for n in nodes)\n"
        "assert basenames(cuppa_nodes) == basenames(scons_nodes)\n"
        "assert basenames(cuppa_nodes) == ['hello.cpp']\n"
        "# Path forms often differ even when the file set matches:\n"
        "cuppa_strs = [str(n).replace('\\\\\\\\', '/') for n in cuppa_nodes]\n"
        "scons_strs = [str(n).replace('\\\\\\\\', '/') for n in scons_nodes]\n"
        "assert any(s.endswith('hello.cpp') for s in cuppa_strs)\n"
        "assert any(s.endswith('hello.cpp') for s in scons_strs)\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_scons_glob_sees_repository_files_cuppa_snapshot_does_not(tmp_path):
    """SCons Repository: Glob finds repo files; GlobFiles / RecursiveGlob only see local disk."""
    project = tmp_path / "project"
    repo = tmp_path / "repo"
    (project / "src").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (project / "src" / "local.cpp").write_text("int local_fn() { return 1; }\n")
    (repo / "src" / "from_repo.cpp").write_text("int from_repo() { return 2; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "Repository('#/../repo')\n"
        "scons_nodes = env.Glob('src/*.cpp')\n"
        "scons_names = sorted(str(n).replace('\\\\\\\\', '/').split('/')[-1] for n in scons_nodes)\n"
        "assert scons_names == ['from_repo.cpp', 'local.cpp'], scons_names\n"
        "cuppa_flat = env.GlobFiles('*.cpp', start='src')\n"
        "flat_names = sorted(str(n).replace('\\\\\\\\', '/').split('/')[-1] for n in cuppa_flat)\n"
        "assert flat_names == ['local.cpp'], flat_names\n"
        "cuppa_walk = env.RecursiveGlob('*.cpp', start='src')\n"
        "walk_names = sorted(str(n).replace('\\\\\\\\', '/').split('/')[-1] for n in cuppa_walk)\n"
        "assert walk_names == ['local.cpp'], walk_names\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)


def test_scons_glob_sees_declared_file_nodes_not_on_disk(tmp_path):
    """Declared env.File nodes appear in Glob; GlobFiles only lists real directory entries."""
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "on_disk.cpp").write_text("int on_disk() { return 1; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os\n"
        "# Declare a source node that does not exist on disk yet.\n"
        "ghost = env.File('src/ghost.cpp')\n"
        "assert not ghost.exists()\n"
        "assert 'ghost.cpp' not in os.listdir('src')\n"
        "scons_nodes = env.Glob('src/*.cpp')\n"
        "scons_names = sorted(str(n).replace('\\\\\\\\', '/').split('/')[-1] for n in scons_nodes)\n"
        "assert scons_names == ['ghost.cpp', 'on_disk.cpp'], scons_names\n"
        "cuppa_flat = env.GlobFiles('*.cpp', start='src')\n"
        "flat_names = sorted(str(n).replace('\\\\\\\\', '/').split('/')[-1] for n in cuppa_flat)\n"
        "assert flat_names == ['on_disk.cpp'], flat_names\n"
        "cuppa_walk = env.RecursiveGlob('*.cpp', start='src')\n"
        "walk_names = sorted(str(n).replace('\\\\\\\\', '/').split('/')[-1] for n in cuppa_walk)\n"
        "assert walk_names == ['on_disk.cpp'], walk_names\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
