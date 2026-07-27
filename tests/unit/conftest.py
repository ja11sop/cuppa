import pytest

from tests.helpers.fakes import FakeEnv


@pytest.fixture
def fake_env():
    return FakeEnv()


@pytest.fixture
def reset_location_caches():
    """Clear class-level location/package caches between tests."""
    import cuppa.build_with_location as bwl
    import cuppa.build_with_package as bwp

    bwl.base._cached_locations = {}
    bwl.base._includes = None
    bwl.base._sys_includes = None
    bwl.base._source_path = None
    bwl.base._linktype = None
    bwp.base._cached_packages = {}
    yield
    bwl.base._cached_locations = {}
    bwl.base._includes = None
    bwl.base._sys_includes = None
    bwl.base._source_path = None
    bwl.base._linktype = None
    bwp.base._cached_packages = {}


@pytest.fixture
def reset_cuppa_environment():
    """Reset CuppaEnvironment class-level option state between tests."""
    from cuppa.core.environment import CuppaEnvironment

    previous_options = dict(CuppaEnvironment._options)
    previous_cached = dict(CuppaEnvironment._cached_options)
    CuppaEnvironment._options = {
        "default_options": {},
        "configured_options": {},
    }
    CuppaEnvironment._cached_options = {}
    yield CuppaEnvironment
    CuppaEnvironment._options = previous_options
    CuppaEnvironment._cached_options = previous_cached
