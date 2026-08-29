import pytest

from tests.helpers.cuppa_runner import assert_success, find_final_binaries, find_under_build, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration

# Portable path helpers for generated sconscripts (avoid '\\' escaping traps on Windows).
_PATH_HELPERS = (
    "import os\n"
    "def posix_path(node):\n"
    "    return str(node).replace(chr(92), '/')\n"
    "def basenames(nodes):\n"
    "    return sorted(os.path.basename(str(n)) for n in nodes)\n"
    "def posix_paths(nodes):\n"
    "    return sorted(posix_path(n) for n in nodes)\n"
)


def test_recursive_glob_walks_tree_and_hash_start(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        + _PATH_HELPERS
        + "env.AppendUnique(CPPPATH=['#/include'])\n"
        "deep = env.RecursiveGlob('*.cpp', start='src')\n"
        "paths = posix_paths(deep)\n"
        "assert any(p.endswith('hello.cpp') for p in paths), paths\n"
        "assert any(p.endswith('nested/deep.cpp') or p.endswith('deep.cpp') for p in paths), paths\n"
        "anchored = env.RecursiveGlob('*.cpp', start='#/src')\n"
        "apaths = posix_paths(anchored)\n"
        "assert any(p.endswith('deep.cpp') for p in apaths), apaths\n"
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
        + _PATH_HELPERS
        + "env.AppendUnique(CPPPATH=['#/include'])\n"
        "flat = env.GlobFiles('*.cpp', start='src')\n"
        "names = basenames(flat)\n"
        "assert names == ['hello.cpp'], names\n"
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
        + _PATH_HELPERS
        + "env.AppendUnique(CPPPATH=['#/include'])\n"
        "top = env.Glob('#/src/*.cpp')\n"
        "one = env.Glob('#/src/**/*.cpp')\n"  # one segment only — not a tree walk
        "walked = env.RecursiveGlob('*.cpp', start='#/src')\n"
        "assert basenames(top) == ['hello.cpp'], basenames(top)\n"
        "assert 'deep.cpp' not in basenames(top), basenames(top)\n"
        "assert basenames(one) == ['deep.cpp'], basenames(one)\n"
        "assert 'hello.cpp' not in basenames(one), basenames(one)\n"
        "walk_names = basenames(walked)\n"
        "assert 'hello.cpp' in walk_names and 'deep.cpp' in walk_names, walk_names\n"
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
        + _PATH_HELPERS
        + "env.AppendUnique(CPPPATH=['#/include'])\n"
        "tree = env.RecursiveGlob('*.cpp', start='#/src')\n"
        "kept = env.Filter(tree, match='*.cpp', exclude='*/detail/*')\n"
        "kept_names = basenames(kept)\n"
        "assert 'deep.cpp' in kept_names and 'hello.cpp' in kept_names, kept_names\n"
        "assert 'hidden.cpp' not in kept_names, kept_names\n"
        "nested = env.Filter(tree, match='**/nested/*.cpp')\n"
        "assert 'deep.cpp' in basenames(nested), basenames(nested)\n"
        "flat = env.Glob('#/tests/*.cpp')\n"
        "tests = env.Filter(flat, match='*_test.cpp')\n"
        "assert len(tests) >= 2\n"
        "rel = env.Filter(flat, match='**/hello_test.cpp')\n"
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
        + _PATH_HELPERS
        + "env.AppendUnique(CPPPATH=['#/include'])\n"
        "walked = env.RecursiveGlob('*.cpp', start='src')\n"
        "flat = env.Glob('#/src/*.cpp')\n"
        "report = os.path.join(env['sconstruct_dir'], 'glob_report.txt')\n"
        "open(report, 'w').write('\\n'.join(basenames(walked)) + '\\n--\\n' + '\\n'.join(basenames(flat)))\n"
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
        + _PATH_HELPERS
        + "env.AppendUnique(CPPPATH=['#/include'])\n"
        "cuppa_nodes = env.GlobFiles('*.cpp', start='src')\n"
        "scons_nodes = env.Glob('#/src/*.cpp')\n"
        "assert basenames(cuppa_nodes) == basenames(scons_nodes)\n"
        "assert basenames(cuppa_nodes) == ['hello.cpp']\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_scons_glob_and_recursive_glob_see_repository_files_in_local_dirs(tmp_path):
    """SCons Repository: Glob, GlobFiles, and RecursiveGlob see repo files in local dirs."""
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
        + _PATH_HELPERS
        + "Repository('#/../repo')\n"
        "scons_nodes = env.Glob('src/*.cpp')\n"
        "assert basenames(scons_nodes) == ['from_repo.cpp', 'local.cpp'], basenames(scons_nodes)\n"
        "cuppa_flat = env.GlobFiles('*.cpp', start='src')\n"
        "assert basenames(cuppa_flat) == ['from_repo.cpp', 'local.cpp'], basenames(cuppa_flat)\n"
        "cuppa_walk = env.RecursiveGlob('*.cpp', start='src')\n"
        "assert basenames(cuppa_walk) == ['from_repo.cpp', 'local.cpp'], basenames(cuppa_walk)\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)


def test_recursive_glob_walks_repository_only_subdirs(tmp_path):
    """RecursiveGlob descends into subdirectory trees that exist only in a Repository."""
    project = tmp_path / "project"
    repo = tmp_path / "repo"
    (project / "src").mkdir(parents=True)
    (repo / "src" / "nested").mkdir(parents=True)
    (project / "src" / "local.cpp").write_text("int local_fn() { return 1; }\n")
    (repo / "src" / "from_repo.cpp").write_text("int from_repo() { return 2; }\n")
    (repo / "src" / "nested" / "deep.cpp").write_text("int deep() { return 3; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        + _PATH_HELPERS
        + "Repository('#/../repo')\n"
        "cuppa_walk = env.RecursiveGlob('*.cpp', start='src')\n"
        "assert basenames(cuppa_walk) == ['deep.cpp', 'from_repo.cpp', 'local.cpp'], "
        "basenames(cuppa_walk)\n"
        "assert any(p.endswith('nested/deep.cpp') for p in posix_paths(cuppa_walk)), "
        "posix_paths(cuppa_walk)\n"
        "assert basenames(env.Glob('src/nested/*.cpp')) == ['deep.cpp']\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)


def test_recursive_glob_repository_local_file_shadows_repo(tmp_path):
    """Same basename on disk wins once — no duplicate nodes from the Repository copy."""
    project = tmp_path / "project"
    repo = tmp_path / "repo"
    (project / "src").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (project / "src" / "shared.cpp").write_text("int shared() { return 1; }\n")
    (repo / "src" / "shared.cpp").write_text("int shared() { return 99; }\n")
    (repo / "src" / "only_repo.cpp").write_text("int only_repo() { return 2; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        + _PATH_HELPERS
        + "Repository('#/../repo')\n"
        "cuppa_walk = env.RecursiveGlob('*.cpp', start='src')\n"
        "assert basenames(cuppa_walk) == ['only_repo.cpp', 'shared.cpp'], basenames(cuppa_walk)\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)


def test_recursive_glob_repository_honours_exclude_and_discard(tmp_path):
    """exclude_dirs / discard_pattern apply to Repository-only subdirectory names."""
    project = tmp_path / "project"
    repo = tmp_path / "repo"
    (project / "src").mkdir(parents=True)
    (repo / "src" / "keep").mkdir(parents=True)
    (repo / "src" / "build").mkdir(parents=True)
    (repo / "src" / "vendor").mkdir(parents=True)
    (project / "src" / "local.cpp").write_text("int local_fn() { return 1; }\n")
    (repo / "src" / "keep" / "kept.cpp").write_text("int kept() { return 2; }\n")
    (repo / "src" / "build" / "skip.cpp").write_text("int skip() { return 3; }\n")
    (repo / "src" / "vendor" / "CMakeLists.txt").write_text("cmake\n")
    (repo / "src" / "vendor" / "hidden.cpp").write_text("int hidden() { return 4; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        + _PATH_HELPERS
        + "Repository('#/../repo')\n"
        "cuppa_walk = env.RecursiveGlob(\n"
        "    '*.cpp', start='src', exclude_dirs=['build'], discard_pattern='CMakeLists.txt')\n"
        "assert basenames(cuppa_walk) == ['kept.cpp', 'local.cpp'], basenames(cuppa_walk)\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)


def test_glob_files_sees_declared_file_nodes_not_on_disk(tmp_path):
    """GlobFiles and RecursiveGlob see declared File nodes; Repository stays separate."""
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "on_disk.cpp").write_text("int on_disk() { return 1; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        + _PATH_HELPERS
        + "# Declare a source node that does not exist on disk yet.\n"
        "ghost = env.File('src/ghost.cpp')\n"
        "assert not ghost.exists()\n"
        "assert 'ghost.cpp' not in os.listdir('src')\n"
        "scons_nodes = env.Glob('src/*.cpp')\n"
        "assert basenames(scons_nodes) == ['ghost.cpp', 'on_disk.cpp'], basenames(scons_nodes)\n"
        "cuppa_flat = env.GlobFiles('*.cpp', start='src')\n"
        "assert basenames(cuppa_flat) == ['ghost.cpp', 'on_disk.cpp'], basenames(cuppa_flat)\n"
        "cuppa_walk = env.RecursiveGlob('*.cpp', start='src')\n"
        "assert basenames(cuppa_walk) == ['ghost.cpp', 'on_disk.cpp'], basenames(cuppa_walk)\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)


def test_recursive_glob_sees_nested_declared_file_nodes(tmp_path):
    """RecursiveGlob merges Dir.entries under nested declared paths with no disk dirs."""
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "on_disk.cpp").write_text("int on_disk() { return 1; }\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        + _PATH_HELPERS
        + "ghost = env.File('src/nested/ghost.cpp')\n"
        "assert not ghost.exists()\n"
        "assert not os.path.isdir('src/nested')\n"
        "cuppa_walk = env.RecursiveGlob('*.cpp', start='src')\n"
        "assert basenames(cuppa_walk) == ['ghost.cpp', 'on_disk.cpp'], basenames(cuppa_walk)\n"
        "assert any(p.endswith('nested/ghost.cpp') for p in posix_paths(cuppa_walk)), "
        "posix_paths(cuppa_walk)\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)


def test_recursive_glob_absolute_start_scenarios_and_filter(tmp_path):
    """Mirror matching_engine: absolute sconscript_dir start, nested *.ebs, Filter, empty out dir."""
    project = tmp_path / "project"
    scenarios = project / "test" / "scenarios"
    (scenarios / "deep").mkdir(parents=True)
    (scenarios / "alpha.ebs").write_text("alpha\n")
    (scenarios / "deep" / "beta.ebs").write_text("beta\n")
    (scenarios / "notes.txt").write_text("ignore\n")
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "import os.path\n"
        + _PATH_HELPERS
        + "scenario_root = os.path.join(env['sconscript_dir'], 'test', 'scenarios')\n"
        "found = env.RecursiveGlob('*.ebs', start=scenario_root)\n"
        "assert basenames(found) == ['alpha.ebs', 'beta.ebs'], basenames(found)\n"
        "skip_list = ['alpha.ebs']\n"
        "kept = [n for n in found if os.path.basename(n.path) not in skip_list]\n"
        "assert basenames(kept) == ['beta.ebs'], basenames(kept)\n"
        "# matching_engine also globs an output dir that may not exist yet\n"
        "out_dir = os.path.join(env['abs_final_dir'], 'scenarios_output')\n"
        "outputs = env.RecursiveGlob('*.ebs', start=out_dir)\n"
        "assert outputs == [], outputs\n"
        "filtered = env.Filter(found, ['*.ebs', '*.log'])\n"
        "assert basenames(filtered) == ['alpha.ebs', 'beta.ebs'], basenames(filtered)\n",
    )
    result = run_cuppa(project, "--dbg")
    assert_success(result)
