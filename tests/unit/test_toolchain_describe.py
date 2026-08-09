#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

from unittest.mock import patch

import pytest

from cuppa.toolchains.clang import Clang
from cuppa.toolchains.describe import (
    describe_toolchain,
    format_dialects_line,
    format_usable_features_line,
    join_flag_tokens,
)
from cuppa.toolchains.gcc import Gcc


pytestmark = pytest.mark.unit


def _gcc( major, minor=0 ):
    toolchain = Gcc.__new__( Gcc )
    toolchain._reported_version = {
        'major': major,
        'minor': minor,
        'name': 'gcc{}'.format( major ),
        'version': '{}.{}'.format( major, minor ),
        'short_version': str( major ),
    }
    toolchain.values = {}
    with patch( 'cuppa.build_platform.name', return_value='Linux' ):
        toolchain._initialise_toolchain( toolchain._reported_version )
    return toolchain


def _clang( major, minor=0, stdlib='libstdc++' ):
    toolchain = Clang.__new__( Clang )
    toolchain._reported_version = {
        'major': major,
        'minor': minor,
        'name': 'clang{}'.format( major ),
        'version': '{}.{}'.format( major, minor ),
        'short_version': str( major ),
    }
    toolchain._suppress_debug_for_auto = False
    toolchain._stdlib = stdlib
    toolchain._gcov_format = None
    toolchain._cxx_path = None
    toolchain.values = {}
    with patch( 'cuppa.build_platform.name', return_value='Linux' ):
        with patch.object( toolchain, '_resolve_versioned_tool', return_value=None ):
            toolchain._initialise_toolchain( toolchain._reported_version, stdlib )
    return toolchain


def test_join_flag_tokens_keeps_placeholders():
    text = join_flag_tokens( [
            '-rdynamic',
            '-Xlinker -Bstatic',
            '<static_libs>',
            '-Xlinker',
            '-Bdynamic',
            '<dynamic_libs>',
    ] )
    assert text == (
            '-rdynamic -Xlinker -Bstatic <static_libs> '
            '-Xlinker -Bdynamic <dynamic_libs>'
    )


def test_gcc_describe_dialects_newest_first_with_default():
    toolchain = _gcc( 14 )
    assert toolchain.default_dialect() == 'c++2c'
    payload = describe_toolchain( toolchain )
    assert payload['default_dialect'] == 'c++2c'
    assert payload['dialects'][:3] == [ 'c++2c', 'c++26', 'c++2b' ]
    assert 'c++23' in payload['dialects']
    assert 'c++20' in payload['dialects']
    assert 'c++98' in payload['dialects']
    assert 'c++latest' not in payload['dialects']
    line = format_dialects_line( payload['dialects'], payload['default_dialect'] )
    assert line.startswith( 'c++2c (default), c++26, c++2b' )


def test_gcc_older_omits_newer_dialects():
    payload = describe_toolchain( _gcc( 7 ) )
    assert payload['default_dialect'] == 'c++1z'
    assert 'c++2a' not in payload['dialects']
    assert 'c++26' not in payload['dialects']
    assert payload['dialects'][:2] == [ 'c++1z', 'c++17' ]


def test_gcc_describe_has_c_cxx_link_and_placeholders():
    payload = describe_toolchain( _gcc( 15 ) )
    dbg = payload['variants']['dbg']
    assert 'c++' in dbg and '-std=c++2c' in dbg['c++']
    assert dbg['c++'].endswith( '<sources>' )
    assert 'c' in dbg and dbg['c'].endswith( '<sources>' )
    assert dbg['link'].startswith( '<objects>' )
    assert '<static_libs>' in dbg['link']
    assert '<dynamic_libs>' in dbg['link']
    # Default DYNAMICLIBS listed before the open <dynamic_libs> slot.
    assert '-Xlinker -Bdynamic -lpthread -lrt <dynamic_libs>' in dbg['link']
    assert 'cov' in payload['variants']
    assert 'rel' in payload['variants']


def test_clang_describe_lists_libcxx_link_defaults():
    payload = describe_toolchain( _clang( 18, stdlib='libc++' ) )
    link = payload['variants']['dbg']['link']
    assert '-lpthread -lrt -lc++abi -lc++' in link
    assert link.index( '-lpthread' ) < link.index( '<dynamic_libs>' )


def test_clang_describe_includes_stdlib_choices():
    payload = describe_toolchain( _clang( 18, stdlib='libstdc++' ) )
    assert payload['default_stdlib'] == 'libstdc++'
    assert payload['stdlib_choices'] == list( Clang.stdlib_choices() )
    assert payload['default_dialect'] == 'c++2c'


def test_describe_default_dialect_matches_baked_flags():
    """Describe must use toolchain.default_dialect(), not a parallel version table."""
    gcc = _gcc( 15 )
    assert gcc.default_dialect() == 'c++2c'
    assert '-std=c++2c' in gcc.values['debug_cxx_flags']
    assert describe_toolchain( gcc )['default_dialect'] == gcc.default_dialect()

    clang = _clang( 18 )
    assert clang.default_dialect() == 'c++2c'
    assert '-std=c++2c' in clang.values['debug_cxx_flags']
    assert describe_toolchain( clang )['default_dialect'] == clang.default_dialect()


def test_usable_features_shorthand():
    assert format_usable_features_line(
            'c++2a', gated=[ 'concepts' ], dialect_inclusive=False
    ) == 'concepts'
    assert format_usable_features_line(
            'c++2a', gated=[ 'coroutines' ]
    ) == 'all c++2a, coroutines'
    assert format_usable_features_line(
            'c++2c', experimental=[ 'modules (experimental)' ]
    ) == 'all c++2c, modules (experimental)'


def test_gcc_describe_usable_features_by_version():
    with patch( 'cuppa.build_platform.name', return_value='Linux' ):
        assert describe_toolchain( _gcc( 9 ) )['usable_features'] == [ 'concepts' ]
        assert describe_toolchain( _gcc( 10 ) )['usable_features'] == [
                'all c++2a', 'coroutines',
        ]
        assert describe_toolchain( _gcc( 12 ) )['usable_features'] == [ 'all c++2b' ]
        assert describe_toolchain( _gcc( 15 ) )['usable_features'] == [
                'all c++2c', 'modules (experimental)',
        ]


def test_clang_describe_usable_features_modules():
    with patch( 'cuppa.build_platform.name', return_value='Linux' ):
        assert describe_toolchain( _clang( 15 ) )['usable_features'] == [ 'all c++2b' ]
        assert describe_toolchain( _clang( 18 ) )['usable_features'] == [
                'all c++2c', 'modules (experimental)',
        ]