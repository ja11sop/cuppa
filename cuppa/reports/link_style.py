#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Shared source-link styles for HTML reports (test, Profiles, future coverage)
#-------------------------------------------------------------------------------

import os

REPORT_LINK_STYLES = ( 'local', 'gitlab', 'github' )


def resolve_report_link_style(
    env,
    method_link_style=None,
    per_report_env_key=None,
):
    """Return the effective source link style for one report emission.

    Precedence: per-report CLI env key → ``reports_link_style`` → method kwarg → ``local``.
    """
    if per_report_env_key:
        per_report = env.get( per_report_env_key )
        if per_report:
            return per_report
    session = env.get( 'reports_link_style' )
    if session:
        return session
    if method_link_style is not None:
        return method_link_style
    return 'local'


def repository_blob_base( repository_url, branch, link_style ):
    """Return the repository blob URL prefix for GitHub or GitLab."""
    if not repository_url or not branch or link_style not in ( 'gitlab', 'github' ):
        return ''
    base = os.path.splitext( str( repository_url ).rstrip( '/' ) )[ 0 ]
    if link_style == 'github':
        return '{}/blob/{}'.format( base, branch )
    return '{}/-/blob/{}'.format( base, branch )


def initialise_report_linking( env, link_style=None ):
    """Resolve the link base URI or raw VCS tuple used by HTML report emitters."""
    from cuppa.test_report.html_report import vcs_info_from_location

    if link_style == 'raw':
        url, repository, branch, remote, revision = vcs_info_from_location(
            env[ 'sconstruct_dir' ],
            env.get( 'current_branch' ),
            env.get( 'current_revision' ),
        )
        return url, repository, branch, remote, revision

    if link_style == 'local':
        return 'file://' + env[ 'sconstruct_dir' ]

    url, repository, branch, remote, revision = vcs_info_from_location(
        env[ 'sconstruct_dir' ],
        env.get( 'current_branch' ),
        env.get( 'current_revision' ),
    )
    if link_style in ( 'gitlab', 'github' ) and url and branch:
        return repository_blob_base( url, branch, link_style )
    if url:
        return url
    return ''


def source_file_href( path, line, link_style, link_base, display_path ):
    """Build a clickable href for one source location in an HTML report."""
    if not path or link_style not in REPORT_LINK_STYLES:
        return None
    display = display_path if display_path is not None else path
    if link_style == 'local':
        if link_base:
            joined = os.path.join( link_base, display )
            return '{}#L{}'.format( joined, line ) if line else joined
        return None
    if link_style in ( 'gitlab', 'github' ) and link_base:
        href = '{}/{}'.format( link_base.rstrip( '/' ), display )
        if line:
            href = '{}#L{}'.format( href, line )
        return href
    return None
