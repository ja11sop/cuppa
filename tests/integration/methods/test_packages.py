import tarfile
import zipfile

import pytest

from cuppa.package_managers.gitlab import os_release_id
from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration


_PUBLISH_SCONSCRIPT = """\
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


def _widget_archives(project):
    names = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name.startswith("widget_") and (
            name.endswith(".tar.gz") or name.endswith(".zip")
        ):
            names.append(name)
    return sorted(names)


def _package_archive_paths(project):
    paths = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name.startswith("widget_") and (
            name.endswith(".tar.gz") or name.endswith(".zip")
        ):
            paths.append(path)
    return paths


def _archive_member_names(archive):
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            return zf.namelist()
    with tarfile.open(archive, "r:*") as tf:
        return tf.getnames()


def _archive_contains_static_lib(archive, stem="widget"):
    members = _archive_member_names(archive)
    suffixes = ("lib{}.a".format(stem), "{}.lib".format(stem))
    return any(name.replace("\\", "/").endswith(suffix) for name in members for suffix in suffixes)


def test_package_methods_are_registered(tmp_path):
    """PublishPackage/InstallPackage need a publisher/installer object.

    Verify the methods are present on the env without hitting a live registry.
    """
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        "Import('env')\n"
        "assert hasattr(env, 'PublishPackage')\n"
        "assert hasattr(env, 'InstallPackage')\n"
        "assert callable(env.PublishPackage)\n"
        "assert callable(env.InstallPackage)\n"
        "env.BuildTest('hello_test', 'tests/hello_test.cpp')\n",
    )
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)


def test_gitlab_publish_archive_includes_os_by_default(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(project, _PUBLISH_SCONSCRIPT)
    result = run_cuppa(project, "--dbg")
    assert_success(result)
    names = _widget_archives(project)
    assert len(names) == 1, names
    os_id = os_release_id()
    assert names[0].startswith("widget_{}_".format(os_id)), names[0]


def test_gitlab_publish_archive_omits_os_when_requested(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(project, _PUBLISH_SCONSCRIPT)
    result = run_cuppa(project, "--dbg", "--package-gitlab-os-identity=omit")
    assert_success(result)
    names = _widget_archives(project)
    assert len(names) == 1, names
    os_id = os_release_id()
    assert not names[0].startswith("widget_{}_".format(os_id)), names[0]
    assert names[0].startswith("widget_"), names[0]


def test_gitlab_publisher_stages_generated_relative_lib_dir(tmp_path):
    project = copy_dummy_project(tmp_path)
    write_sconstruct(project)
    write_sconscript(
        project,
        """\
Import('env')
from cuppa.package_managers.gitlab import GitlabPackagePublisher
env.AppendUnique(CPPPATH=['#/include'])
lib = env.BuildStaticLib(
    'widget',
    'src/hello.cpp',
    final_dir='package_lib',
)
publisher = GitlabPackagePublisher(
    env,
    source_include_dir='#/include',
    source_lib_dir='package_lib',
    registry='https://gitlab.example/api/v4/projects/1',
    package='widget',
    version='1.0.0',
)
env.PublishPackage(lib, publisher)
""",
    )

    result = run_cuppa(project, "--rel", "--parallel")
    assert_success(result)
    archives = _package_archive_paths(project)
    assert len(archives) == 1, archives
    assert _archive_contains_static_lib(archives[0])
