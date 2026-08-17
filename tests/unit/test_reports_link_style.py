#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.reports.link_style import (
    normalize_repository_browse_url,
    repository_blob_base,
    resolve_report_link_style,
    source_file_href,
)

pytestmark = pytest.mark.unit


def test_repository_blob_base_github():
    base = repository_blob_base(
        'https://github.com/org/repo.git',
        'main',
        'github',
    )
    assert base == 'https://github.com/org/repo/blob/main'


def test_repository_blob_base_github_git_ssh():
    base = repository_blob_base(
        'git@github.com:org/repo.git',
        'main',
        'github',
    )
    assert base == 'https://github.com/org/repo/blob/main'


def test_normalize_repository_browse_url():
    assert normalize_repository_browse_url(
        'git@github.com:cppalliance/capy.git',
    ) == 'https://github.com/cppalliance/capy'
    assert normalize_repository_browse_url(
        'https://gitlab.com/group/repo.git',
    ) == 'https://gitlab.com/group/repo'


def test_repository_blob_base_gitlab():
    base = repository_blob_base(
        'https://gitlab.com/group/repo.git',
        'main',
        'gitlab',
    )
    assert base == 'https://gitlab.com/group/repo/-/blob/main'


def test_resolve_report_link_style_precedence():
    env = {
        'cxx_profiles_report_link_style': 'gitlab',
        'reports_link_style': 'github',
    }
    assert resolve_report_link_style(
        env,
        method_link_style='local',
        per_report_env_key='cxx_profiles_report_link_style',
    ) == 'gitlab'
    assert resolve_report_link_style( env, method_link_style='local' ) == 'github'
    assert resolve_report_link_style( {}, method_link_style='local' ) == 'local'
    assert resolve_report_link_style( {}, method_link_style=None ) == 'local'


def test_source_file_href_remote():
    href = source_file_href(
        'src/widget.cpp',
        10,
        'github',
        'https://github.com/org/repo/blob/main',
        'src/widget.cpp',
    )
    assert href == 'https://github.com/org/repo/blob/main/src/widget.cpp#L10'
