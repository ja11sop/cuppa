#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.reports.link_style import (
    hosting_style_from_url,
    initialise_report_linking,
    normalize_repository_browse_url,
    repo_relative_path_for_link,
    repository_blob_base,
    resolve_path_remote_link,
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


def test_hosting_style_from_url():
    assert hosting_style_from_url( 'git@github.com:org/repo.git' ) == 'github'
    assert hosting_style_from_url( 'git@git.example.com:org/repo.git' ) == 'gitlab'


def test_initialise_report_linking_remote():
    env = { 'sconstruct_dir': '/tmp/project' }
    assert initialise_report_linking( env, link_style='remote' ) == ''


def test_resolve_path_remote_link_project( tmp_path, monkeypatch ):
    source = tmp_path / '_build' / 'dbg' / 'working' / 'src' / 'widget.cpp'
    source.parent.mkdir( parents=True )
    monkeypatch.setattr(
        'cuppa.test_report.html_report.vcs_info_from_location',
        lambda *args: (
            'git@github.com:org/app.git',
            'git@github.com:org/app.git',
            'main',
            'origin',
            'abc',
        ),
    )
    env = { 'sconstruct_dir': str( tmp_path ) }
    blob_base, relpath = resolve_path_remote_link( str( source ), env )
    assert blob_base == 'https://github.com/org/app/blob/main'
    assert relpath == 'src/widget.cpp'


def test_resolve_path_remote_link_gitlab_dependency( tmp_path, monkeypatch ):
    deps_root = tmp_path / '_download'
    folder = 'git_ssh_git@git.example.com__org_widget@master'
    dep_root = deps_root / folder
    dep_root.mkdir( parents=True )
    ( dep_root / '.git' ).mkdir()
    include_dir = dep_root / 'include' / 'widget'
    include_dir.mkdir( parents=True )
    source = include_dir / 'widget.hpp'
    source.write_text( 'struct Widget {};\n', encoding='utf-8' )

    monkeypatch.setattr(
        'cuppa.core.dependency_identity.short_name_from_git_tree',
        lambda path: ( 'git.example.com/org/widget', 'ssh://git@git.example.com/org/widget' ),
    )

    env = {
        'sconstruct_dir': str( tmp_path ),
        'downloads_root': str( deps_root ),
    }
    blob_base, relpath = resolve_path_remote_link( str( source ), env )
    assert blob_base == 'https://git.example.com/org/widget/-/blob/master'
    assert relpath == 'include/widget/widget.hpp'


def test_source_file_href_remote_style( tmp_path, monkeypatch ):
    source = tmp_path / 'include' / 'widget.hpp'
    source.parent.mkdir()
    monkeypatch.setattr(
        'cuppa.test_report.html_report.vcs_info_from_location',
        lambda *args: (
            'https://github.com/org/app.git',
            'https://github.com/org/app.git',
            'main',
            'origin',
            'abc',
        ),
    )
    env = { 'sconstruct_dir': str( tmp_path ) }
    href = source_file_href(
        str( source ),
        12,
        'remote',
        '',
        repo_relative_path_for_link( str( source ), env ),
        env=env,
    )
    assert href == 'https://github.com/org/app/blob/main/include/widget.hpp#L12'
