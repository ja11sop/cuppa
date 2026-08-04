"""Unit tests for dependency removal helpers (Slice D)."""

import pytest

from cuppa.core import dependency_removal, dependency_storage
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
        'dependencies': { 'widget': object(), 'boost_package': object() },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert names == []
    assert error is not None
    assert 'widgt' in error
    assert 'widget' in error
    assert 'boost_package' in error


def test_resolve_requested_names_all_uses_defaults():
    cuppa_env = {
        'remove_all_dependencies': True,
        'default_dependencies': [ 'widget', 'boost_package' ],
        'dependencies': { 'widget': object(), 'boost_package': object(), 'extra': object() },
    }
    names, error = dependency_removal.resolve_requested_names( cuppa_env )
    assert error is None
    assert names == [ 'widget', 'boost_package' ]


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


def test_looks_like_tool_variant_still_works():
    assert dependency_storage.looks_like_tool_variant_dir( 'gcc153_dbg_x86_64_cxx2c' )
    assert not dependency_storage.looks_like_tool_variant_dir( 'git_https_example.com__org_widget.git@master' )
