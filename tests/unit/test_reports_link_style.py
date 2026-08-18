#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.reports.link_style import (
    DEFAULT_AZURE_DEVOPS_HOSTS,
    DEFAULT_BITBUCKET_HOSTS,
    DEFAULT_GITEA_HOSTS,
    DEFAULT_GITHUB_HOSTS,
    DEFAULT_GITLAB_HOSTS,
    build_unmapped_remote_link_html,
    detect_hosting_provider,
    file_href_for_provider,
    hosting_style_from_url,
    initialise_report_linking,
    log_unknown_hosting_summary,
    normalize_repository_browse_url,
    parse_host_list,
    repo_relative_path_for_link,
    reports_host_config,
    repository_blob_base,
    reset_unknown_hosting_notes,
    resolve_path_remote_link,
    resolve_report_link_style,
    source_file_href,
    source_link_display,
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


def test_repository_blob_base_bitbucket():
    base = repository_blob_base(
        'https://bitbucket.org/org/repo.git',
        'main',
        'bitbucket',
    )
    assert base == 'https://bitbucket.org/org/repo/src/main'


def test_repository_blob_base_gitea():
    base = repository_blob_base(
        'https://codeberg.org/user/repo.git',
        'main',
        'gitea',
    )
    assert base == 'https://codeberg.org/user/repo/src/branch/main'


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


def test_source_file_href_skips_missing_path():
    assert source_file_href(
        None,
        10,
        'local',
        'file:///tmp/project',
        None,
    ) is None


def test_source_file_href_remote():
    href = source_file_href(
        'src/widget.cpp',
        10,
        'github',
        'https://github.com/org/repo/blob/main',
        'src/widget.cpp',
    )
    assert href == 'https://github.com/org/repo/blob/main/src/widget.cpp#L10'


def test_parse_host_list():
    assert parse_host_list( ' git.example.com , corp.example ' ) == [
        'git.example.com',
        'corp.example',
    ]
    assert parse_host_list( [ 'a.example', 'b.example' ] ) == [ 'a.example', 'b.example' ]
    assert parse_host_list( 'https://git.corp.example/' ) == [ 'git.corp.example' ]
    assert parse_host_list( ' HTTPS://Git.Corp.Example/ ' ) == [ 'git.corp.example' ]


def test_detect_hosting_provider_accepts_url_host_config():
    env = { 'reports_gitlab_hosts': [ 'https://git.corp.example/' ] }
    assert detect_hosting_provider(
        'ssh://git@git.corp.example/org/repo.git',
        env,
    ) == 'gitlab'


def test_reports_host_config_defaults():
    config = reports_host_config( {} )
    assert config[ 'github' ] == DEFAULT_GITHUB_HOSTS
    assert config[ 'gitlab' ] == DEFAULT_GITLAB_HOSTS
    assert config[ 'bitbucket' ] == DEFAULT_BITBUCKET_HOSTS
    assert config[ 'gitea' ] == DEFAULT_GITEA_HOSTS
    assert config[ 'azure_devops' ] == DEFAULT_AZURE_DEVOPS_HOSTS


def test_reports_host_config_custom():
    env = {
        'reports_gitlab_hosts': [ 'git.corp.example', 'gitlab.example.com' ],
    }
    config = reports_host_config( env )
    assert config[ 'gitlab' ] == ( 'git.corp.example', 'gitlab.example.com' )


def test_detect_hosting_provider():
    env = { 'reports_gitlab_hosts': [ 'git.corp.example' ] }
    assert detect_hosting_provider( 'git@github.com:org/repo.git' ) == 'github'
    assert detect_hosting_provider( 'https://gitlab.com/group/repo.git' ) == 'gitlab'
    assert detect_hosting_provider( 'https://bitbucket.org/org/repo.git' ) == 'bitbucket'
    assert detect_hosting_provider( 'https://codeberg.org/user/repo.git' ) == 'gitea'
    assert detect_hosting_provider(
        'ssh://git@git.corp.example/org/repo.git',
        env,
    ) == 'gitlab'
    assert detect_hosting_provider( 'ssh://git@git.corp.example/org/repo.git' ) == 'unknown'


def test_hosting_style_from_url():
    assert hosting_style_from_url( 'git@github.com:org/repo.git' ) == 'github'
    assert hosting_style_from_url( 'git@git.example.com:org/repo.git' ) == 'gitlab'


def test_file_href_for_provider_shapes():
    browse = 'https://github.com/org/repo'
    assert file_href_for_provider(
        browse, 'main', 'src/widget.cpp', 10, 'github',
    ) == 'https://github.com/org/repo/blob/main/src/widget.cpp#L10'
    assert file_href_for_provider(
        'https://gitlab.com/group/repo', 'main', 'src/widget.cpp', 10, 'gitlab',
    ) == 'https://gitlab.com/group/repo/-/blob/main/src/widget.cpp#L10'
    assert file_href_for_provider(
        'https://bitbucket.org/org/repo', 'main', 'src/widget.cpp', 10, 'bitbucket',
    ) == 'https://bitbucket.org/org/repo/src/main/src/widget.cpp#lines-10'
    assert file_href_for_provider(
        'https://codeberg.org/user/repo', 'main', 'src/widget.cpp', 10, 'gitea',
    ) == 'https://codeberg.org/user/repo/src/branch/main/src/widget.cpp#L10'
    assert file_href_for_provider(
        'https://dev.azure.com/org/project/_git/repo',
        'main',
        'src/widget.cpp',
        10,
        'azure_devops',
    ).startswith(
        'https://dev.azure.com/org/project/_git/repo?path=/src/widget.cpp&version=GBmain&line=10'
    )


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
    resolution = resolve_path_remote_link( str( source ), env )
    assert resolution.provider == 'github'
    assert resolution.browse_url == 'https://github.com/org/app'
    assert resolution.relpath == 'src/widget.cpp'
    assert file_href_for_provider(
        resolution.browse_url,
        resolution.ref,
        resolution.relpath,
        None,
        resolution.provider,
    ) == 'https://github.com/org/app/blob/main/src/widget.cpp'


def test_resolve_path_remote_link_custom_host( tmp_path, monkeypatch ):
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
    resolution = resolve_path_remote_link( str( source ), env )
    assert resolution.provider == 'unknown'
    assert resolution.browse_url == 'https://git.example.com/org/widget'
    assert resolution.relpath == 'include/widget/widget.hpp'


def test_source_link_display_unmapped_partial_link( tmp_path, monkeypatch ):
    source = tmp_path / 'include' / 'widget.hpp'
    source.parent.mkdir()
    monkeypatch.setattr(
        'cuppa.test_report.html_report.vcs_info_from_location',
        lambda *args: (
            'ssh://git@git.example.com/org/app.git',
            'ssh://git@git.example.com/org/app.git',
            'main',
            'origin',
            'abc',
        ),
    )
    env = { 'sconstruct_dir': str( tmp_path ) }
    display = source_link_display(
        str( source ),
        12,
        'remote',
        '',
        repo_relative_path_for_link( str( source ), env ),
        env=env,
    )
    assert display[ 'href' ] == 'https://git.example.com/org/app'
    assert display[ 'label' ] == (
        'https://git.example.com/org/app/include/widget.hpp#L12'
    )
    assert display[ 'label_html' ].startswith(
        '<a href="https://git.example.com/org/app">https://git.example.com/org/app</a>'
    )
    assert '/include/widget.hpp#L12' in display[ 'label_html' ]
    assert 'title="GitHub">GH</a>' in display[ 'label_html' ]
    assert 'title="GitLab">GL</a>' in display[ 'label_html' ]


def test_build_unmapped_remote_link_html_respects_hint_flag():
    from cuppa.reports.link_style import RemoteLinkResolution

    resolution = RemoteLinkResolution(
        browse_url='https://git.example.com/org/app',
        ref='main',
        relpath='include/widget.hpp',
        provider='unknown',
        source_url='ssh://git@git.example.com/org/app.git',
    )
    html_with_hints = build_unmapped_remote_link_html(
        resolution,
        12,
        { 'reports_remote_provider_hints': True },
    )
    assert 'GH</a>' in html_with_hints
    html_without_hints = build_unmapped_remote_link_html(
        resolution,
        12,
        { 'reports_remote_provider_hints': False },
    )
    assert 'GH</a>' not in html_without_hints


def test_unknown_hosting_summary_dedupes_repos( caplog ):
    import logging
    from cuppa.reports.link_style import _record_unknown_hosting

    caplog.set_level( logging.INFO, logger='cuppa' )
    caplog.set_level( logging.DEBUG, logger='cuppa' )
    env = {}
    reset_unknown_hosting_notes( env )
    browse = 'https://git.example.com/org/app'
    _record_unknown_hosting( browse, env )
    _record_unknown_hosting( browse, env )
    _record_unknown_hosting( 'https://git.example.com/org/lib', env )
    _record_unknown_hosting( 'https://git.other.example/org/lib', env )
    log_unknown_hosting_summary( env )
    info_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
    ]
    assert len( info_messages ) == 1
    assert 'Unmapped repository hosts for remotes:' in info_messages[ 0 ]
    assert 'https://git.example.com/org/app' not in info_messages[ 0 ]
    assert 'git.example.com' in info_messages[ 0 ]
    assert 'git.other.example' in info_messages[ 0 ]
    assert info_messages[ 0 ].count( 'git.example.com' ) == 1
    assert 'https://git.example.com' not in info_messages[ 0 ]
    assert 'GH/GL/BB/GT/AD provider hint links' in info_messages[ 0 ]
    assert '--reports-gitlab-hosts=HOST' in info_messages[ 0 ]
    debug_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.DEBUG
    ]
    assert len( debug_messages ) == 2


def test_reports_host_flags_register_without_trailing_equals():
    from cuppa.methods.reports import ReportsLinkStyleMethod

    registered = []

    def capture_option( flag, **kwargs ):
        registered.append( flag )

    ReportsLinkStyleMethod.add_options( capture_option )
    host_flags = [
        flag for flag in registered
        if flag.startswith( '--reports-' ) and flag.endswith( '-hosts' )
    ]
    assert host_flags
    assert all( not flag.endswith( '=' ) for flag in host_flags )
    assert '--reports-gitlab-hosts' in host_flags


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
