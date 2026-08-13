#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.cpp.profiles_report.breadcrumbs import (
    INDEX_ROLLUP_FILES_FRAGMENT,
    INDEX_SCOPES_FRAGMENT,
    scope_breadcrumbs,
    source_breadcrumbs,
)

pytestmark = pytest.mark.unit


def test_scope_breadcrumbs():
    crumbs = scope_breadcrumbs(
        'cxx-profiles-index.html',
        {
            'sconscript': './widget/sconscript',
            'variant_display': 'dbg/x86_64/cxx2c',
            'toolchain': 'clang24_profiles',
        },
    )
    assert len( crumbs ) == 3
    assert crumbs[ 0 ][ 'label' ] == 'Profiles report'
    assert crumbs[ 0 ][ 'href' ] == 'cxx-profiles-index.html'
    assert crumbs[ 1 ][ 'href' ] == 'cxx-profiles-index.html{}'.format(
        INDEX_SCOPES_FRAGMENT,
    )
    assert crumbs[ 2 ][ 'active' ] is True
    assert 'dbg/x86_64/cxx2c' in crumbs[ 2 ][ 'label' ]


def test_source_breadcrumbs_project_file():
    crumbs = source_breadcrumbs(
        '../cxx-profiles-index.html',
        'src/widget.cpp',
    )
    assert len( crumbs ) == 3
    assert crumbs[ 1 ][ 'label' ] == 'By source'
    assert crumbs[ 1 ][ 'href' ] == '../cxx-profiles-index.html{}'.format(
        INDEX_ROLLUP_FILES_FRAGMENT,
    )
    assert crumbs[ 2 ][ 'active' ] is True
    assert crumbs[ 2 ][ 'label' ] == 'src/widget.cpp'


def test_source_breadcrumbs_dependency_file_split():
    crumbs = source_breadcrumbs(
        '../cxx-profiles-index.html',
        'git.example.com/org/widget@master/include/widget.hpp',
        title_split=True,
        title_prefix='git.example.com/org/widget@master',
        title_suffix='include/widget.hpp',
    )
    assert len( crumbs ) == 4
    assert crumbs[ 2 ][ 'label' ] == 'git.example.com/org/widget@master'
    assert crumbs[ 2 ].get( 'href' ) is None
    assert crumbs[ 3 ][ 'active' ] is True
    assert crumbs[ 3 ][ 'label' ] == 'include/widget.hpp'
