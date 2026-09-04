#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for BuildWith dependency resolve (#250 / dependency-resolve plan)."""

import pytest

from cuppa.core.dependency_resolve import (
    DependencyResolveException,
    is_project_available,
    resolve_registry_name,
)


pytestmark = pytest.mark.unit


def test_is_project_available_builtin_needs_build_with_or_default():
    env = {
        'dependencies': { 'boost': object() },
        'BUILD_WITH': [],
        'default_dependencies': [],
    }
    assert is_project_available( env, 'boost' ) is False

    env['BUILD_WITH'] = [ 'boost' ]
    assert is_project_available( env, 'boost' ) is True


def test_is_project_available_package_when_registered():
    env = {
        'dependencies': { 'boost_package': object() },
        'BUILD_WITH': [],
        'default_dependencies': [],
    }
    assert is_project_available( env, 'boost_package' ) is True


def test_untyped_boost_prefers_project_available_package():
    env = {
        'dependencies': {
            'boost': object(),
            'boost_package': object(),
        },
        'BUILD_WITH': [],
        'default_dependencies': [ 'boost_package' ],
    }
    assert resolve_registry_name( env, 'boost' ) == 'boost_package'


def test_untyped_boost_prefers_package_already_buildwith():
    env = {
        'dependencies': {
            'boost': object(),
            'boost_package': object(),
        },
        'BUILD_WITH': [ 'boost_package' ],
        'default_dependencies': [],
    }
    assert resolve_registry_name( env, 'boost' ) == 'boost_package'


def test_untyped_boost_falls_back_to_archive_builtin():
    env = {
        'dependencies': { 'boost': object() },
        'BUILD_WITH': [],
        'default_dependencies': [],
    }
    assert resolve_registry_name( env, 'boost' ) == 'boost'


def test_explicit_archive_boost_skips_package():
    env = {
        'dependencies': {
            'boost': object(),
            'boost_package': object(),
        },
        'default_dependencies': [ 'boost_package' ],
    }
    assert resolve_registry_name( env, '[archive]boost' ) == 'boost'
    assert resolve_registry_name( env, '[source]boost' ) == 'boost'


def test_explicit_gitlab_boost_maps_to_boost_package():
    env = {
        'dependencies': {
            'boost': object(),
            'boost_package': object(),
        },
    }
    assert resolve_registry_name( env, '[gitlab]boost' ) == 'boost_package'
    assert resolve_registry_name( env, 'boost_package' ) == 'boost_package'


def test_explicit_conan_refused():
    env = { 'dependencies': { 'boost': object() } }
    with pytest.raises( DependencyResolveException ) as caught:
        resolve_registry_name( env, '[conan]boost' )
    assert 'conan' in caught.value.parameter.lower()


def test_resolve_required_false_returns_none():
    assert resolve_registry_name( {}, 'boost', required=False ) is None
