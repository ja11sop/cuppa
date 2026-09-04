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


def test_is_project_available_non_builtin_when_registered():
    env = {
        'dependencies': { 'widget_lib_package': object() },
        'BUILD_WITH': [],
        'default_dependencies': [],
    }
    assert is_project_available( env, 'widget_lib_package' ) is True


def test_untyped_prefers_legacy_package_over_short_name():
    """General case: widget_lib_package beats archive/short widget_lib."""
    env = {
        'dependencies': {
            'widget_lib': object(),
            'widget_lib_package': object(),
        },
        'BUILD_WITH': [],
        'default_dependencies': [ 'widget_lib_package' ],
    }
    assert resolve_registry_name( env, 'widget_lib' ) == 'widget_lib_package'


def test_untyped_prefers_package_already_buildwith():
    env = {
        'dependencies': {
            'widget_lib': object(),
            'widget_lib_package': object(),
        },
        'BUILD_WITH': [ 'widget_lib_package' ],
        'default_dependencies': [],
    }
    assert resolve_registry_name( env, 'widget_lib' ) == 'widget_lib_package'


def test_untyped_prefers_typed_gitlab_registry_key():
    env = {
        'dependencies': {
            'widget_lib': object(),
            '[gitlab]widget_lib': object(),
        },
        'default_dependencies': [ '[gitlab]widget_lib' ],
    }
    assert resolve_registry_name( env, 'widget_lib' ) == '[gitlab]widget_lib'


def test_untyped_falls_back_to_short_name():
    env = {
        'dependencies': { 'widget_lib': object() },
        'BUILD_WITH': [],
        'default_dependencies': [],
    }
    assert resolve_registry_name( env, 'widget_lib' ) == 'widget_lib'


def test_untyped_boost_prefers_boost_package():
    env = {
        'dependencies': {
            'boost': object(),
            'boost_package': object(),
        },
        'default_dependencies': [ 'boost_package' ],
    }
    assert resolve_registry_name( env, 'boost' ) == 'boost_package'


def test_untyped_boost_falls_back_to_archive_builtin():
    env = {
        'dependencies': { 'boost': object() },
        'BUILD_WITH': [],
        'default_dependencies': [],
    }
    assert resolve_registry_name( env, 'boost' ) == 'boost'


def test_explicit_archive_skips_legacy_package():
    env = {
        'dependencies': {
            'widget_lib': object(),
            'widget_lib_package': object(),
        },
        'default_dependencies': [ 'widget_lib_package' ],
    }
    assert resolve_registry_name( env, '[archive]widget_lib' ) == 'widget_lib'
    assert resolve_registry_name( env, '[source]widget_lib' ) == 'widget_lib'


def test_explicit_gitlab_maps_to_legacy_package():
    env = {
        'dependencies': {
            'widget_lib': object(),
            'widget_lib_package': object(),
        },
    }
    assert resolve_registry_name( env, '[gitlab]widget_lib' ) == 'widget_lib_package'


def test_explicit_gitlab_boost_maps_to_boost_package():
    env = {
        'dependencies': {
            'boost': object(),
            'boost_package': object(),
        },
    }
    assert resolve_registry_name( env, '[gitlab]boost' ) == 'boost_package'
    assert resolve_registry_name( env, 'boost_package' ) == 'boost_package'


def test_explicit_gitlab_does_not_select_always_on_builtin_short_name():
    env = { 'dependencies': { 'boost': object() } }
    with pytest.raises( DependencyResolveException ):
        resolve_registry_name( env, '[gitlab]boost' )


def test_explicit_conan_refused():
    env = { 'dependencies': { 'widget_lib': object() } }
    with pytest.raises( DependencyResolveException ) as caught:
        resolve_registry_name( env, '[conan]widget_lib' )
    assert 'conan' in caught.value.parameter.lower()


def test_resolve_required_false_returns_none():
    assert resolve_registry_name( {}, 'widget_lib', required=False ) is None
