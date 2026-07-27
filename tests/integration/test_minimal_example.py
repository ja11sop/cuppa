import pytest

from tests.helpers.cuppa_runner import assert_success, run_cuppa
from tests.helpers.project import REPO_ROOT


pytestmark = pytest.mark.integration


def test_examples_minimal_build_and_test():
    project = REPO_ROOT / "examples" / "minimal"
    result = run_cuppa(project, "--dbg", "--test")
    assert_success(result)
