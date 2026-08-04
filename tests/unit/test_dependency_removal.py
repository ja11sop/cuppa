"""Unit tests for dependency removal helpers (Slice D)."""

import pytest

from cuppa.core import dependency_removal
from cuppa.utility import storage


pytestmark = pytest.mark.unit


def test_parse_dependency_names_splits_and_strips():
    assert dependency_removal.parse_dependency_names( 'widget, boost_package' ) == [
            'widget', 'boost_package',
    ]
    assert dependency_removal.parse_dependency_names( 'widget' ) == [ 'widget' ]
    assert dependency_removal.parse_dependency_names( '' ) == []
    assert dependency_removal.parse_dependency_names( None ) == []


def test_resolve_requested_names_unknown_error():
    cuppa_env = {
        'remove_dependencies': 'widgt',
        'dependencies': { 'widget': object(), 'boost_package': object(), 'boost': object() },
        'default_dependencies': [ 'widget', 'boost_package' ],
        'declared_dependencies': [ 'widget', 'boost_package' ],
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert names == []
    assert isinstance( error, dependency_removal.UnknownDependencyNames )
    assert error.unknown == ( 'widgt', )
    assert 'widget' in error.project_used
    assert 'boost_package' in error.project_used


def test_resolve_requested_names_rejects_registry_only_builtin():
    """Built-in ``boost`` in the registry is not removable unless the project uses it."""
    cuppa_env = {
        'remove_dependencies': 'boost',
        'dependencies': { 'boost': object(), 'boost_package': object() },
        'default_dependencies': [ 'boost_package' ],
        'declared_dependencies': [ 'boost_package' ],
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert names == []
    assert isinstance( error, dependency_removal.UnknownDependencyNames )
    assert error.unknown == ( 'boost', )
    assert error.project_used == ( 'boost_package', )


def test_resolve_requested_names_accepts_builtin_when_defaulted():
    cuppa_env = {
        'remove_dependencies': 'boost',
        'dependencies': { 'boost': object(), 'boost_package': object() },
        'default_dependencies': [ 'boost' ],
        'declared_dependencies': [],
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'boost' ]


def test_resolve_requested_names_all_uses_project_used():
    cuppa_env = {
        'remove_all_dependencies': True,
        'default_dependencies': [ 'widget' ],
        'declared_dependencies': [ 'boost_package' ],
        'dependencies': {
            'widget': object(),
            'boost_package': object(),
            'boost': object(),
            'extra': object(),
        },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'widget', 'boost_package' ]


def test_project_dependency_names_union_preserves_order():
    cuppa_env = {
        'default_dependencies': [ 'a', 'b' ],
        'declared_dependencies': [ 'b', 'c' ],
    }
    assert dependency_removal.project_dependency_names( cuppa_env ) == [ 'a', 'b', 'c' ]


def test_sibling_leftovers_gitlab(tmp_path):
    root = tmp_path / 'dependencies'
    gcc = root / 'gcc153_dbg_x86_64_cxx2c' / 'boost' / '1.91'
    clang = root / 'clang211_dbg_x86_64_cxx2c' / 'boost' / '1.91'
    gcc.mkdir(parents=True)
    clang.mkdir(parents=True)
    (gcc / 'f').write_text( 'x', encoding='utf-8' )
    (clang / 'f').write_text( 'x', encoding='utf-8' )

    target = dependency_removal.RemovalTarget(
            dependency='boost_package',
            path=str( gcc ),
            qualifier='1.91',
            tool_variant='gcc153_dbg_x86_64_cxx2c',
            storage_type='gitlab',
            size_bytes=1,
    )
    leftovers = dependency_removal._sibling_leftovers(
            str( root ), target, { storage.real_path( str( gcc ) ) },
    )
    assert len( leftovers ) == 1
    assert leftovers[0].tool_variant == 'clang211_dbg_x86_64_cxx2c'
    assert leftovers[0].dependency == 'boost_package'


def test_sibling_leftovers_location_branches(tmp_path):
    root = tmp_path / 'dependencies'
    master = root / 'git_https_example.com__org_widget.git@master'
    feature = root / 'git_https_example.com__org_widget.git@feature_x'
    master.mkdir(parents=True)
    feature.mkdir(parents=True)
    (master / 'f').write_text( 'x', encoding='utf-8' )
    (feature / 'f').write_text( 'x', encoding='utf-8' )

    target = dependency_removal.RemovalTarget(
            dependency='widget',
            path=str( master ),
            qualifier='@master',
            tool_variant=None,
            storage_type='location',
            size_bytes=1,
    )
    leftovers = dependency_removal._sibling_leftovers(
            str( root ), target, { storage.real_path( str( master ) ) },
    )
    assert len( leftovers ) == 1
    assert leftovers[0].qualifier == '@feature_x'


def test_relative_removal_path_under_root(tmp_path):
    root = tmp_path / 'dependencies'
    path = root / 'gcc153_rel_x86_64_cxx2c' / 'boost' / '1.91'
    path.mkdir(parents=True)
    assert dependency_removal._relative_removal_path(
            str( path ), str( root )
    ) == 'gcc153_rel_x86_64_cxx2c/boost/1.91'
