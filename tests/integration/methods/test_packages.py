import logging

import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import copy_dummy_project, write_sconstruct, write_sconscript


pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


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
    logger.info("PublishPackage/InstallPackage registered on env (offline registry E2E deferred)")
