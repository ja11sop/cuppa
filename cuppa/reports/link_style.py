#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Shared source-link styles for HTML reports (test, Profiles, future coverage)
#-------------------------------------------------------------------------------

import os

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

REPORT_LINK_STYLES = ( 'local', 'gitlab', 'github', 'remote' )

_WORKING_DIR_MARKER = '/working/'
_UNQUALIFIED_SUFFIX = ' (unqualified)'


def normalize_repository_browse_url( repository_url ):
    """Return ``https://host/org/repo`` for ``git@``, ``https://``, and scp-style remotes."""
    if not repository_url:
        return None
    text = str( repository_url ).strip()
    if not text:
        return None
    if '://' in text:
        parsed = urlparse( text )
        if parsed.scheme in ( 'http', 'https' ):
            path = ( parsed.path or '' ).rstrip( '/' )
            if path.endswith( '.git' ):
                path = path[:-4]
            if '/archive/' in path:
                archive_base = path.split( '/archive/' )[ 0 ]
                if archive_base.endswith( '.git' ):
                    archive_base = archive_base[:-4]
                path = archive_base
            netloc = parsed.netloc.split( '@' )[-1 ]
            return 'https://{}{}'.format( netloc, path )
    from cuppa.core.dependency_identity import short_name_from_git_url

    short = short_name_from_git_url( text )
    if not short or '/' not in short:
        return None
    host, path = short.split( '/', 1 )
    return 'https://{}/{}'.format( host, path )


def hosting_style_from_url( repository_url ):
    """Return ``github`` or ``gitlab`` blob URL shape for a repository URL."""
    browse = normalize_repository_browse_url( repository_url )
    if browse and 'github.com' in browse.lower():
        return 'github'
    return 'gitlab'


def browse_url_from_short_name( short_name ):
    """Turn ``host/org/repo`` short names into an ``https://`` browse base."""
    if not short_name:
        return None
    text = str( short_name ).strip().rstrip( '/' )
    if not text or '/' not in text:
        return None
    if text.startswith( 'http://' ) or text.startswith( 'https://' ):
        return normalize_repository_browse_url( text )
    return 'https://{}'.format( text )


def ref_from_qualifier( qualifier ):
    """Extract a VCS ref from a dependency ``@branch`` / ``@tag`` qualifier."""
    if not qualifier:
        return None
    text = str( qualifier ).strip()
    if not text.startswith( '@' ):
        return None
    ref = text[ 1: ]
    if ref.endswith( _UNQUALIFIED_SUFFIX ):
        ref = ref[ : -len( _UNQUALIFIED_SUFFIX ) ]
    return ref or None


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
    browse = normalize_repository_browse_url( repository_url )
    if not browse or not branch or link_style not in ( 'gitlab', 'github' ):
        return ''
    if link_style == 'github':
        return '{}/blob/{}'.format( browse, branch )
    return '{}/-/blob/{}'.format( browse, branch )


def _try_relpath( path, root ):
    if not path or not root:
        return None
    try:
        rel = os.path.relpath( path, os.path.realpath( root ) )
    except ValueError:
        return None
    if rel.startswith( '..' ):
        return None
    return rel.replace( os.sep, '/' )


def _storage_root_for_path( path, env ):
    for key in ( 'dependencies_root', 'downloads_root' ):
        root = env.get( key )
        if not root:
            continue
        try:
            real_root = os.path.realpath( root )
            real_path = os.path.realpath( path )
        except OSError:
            real_root = root
            real_path = path
        try:
            if os.path.commonpath( [ real_path, real_root ] ) == real_root:
                return real_root
        except ValueError:
            continue

    normalized = os.path.normpath( path )
    parts = normalized.split( os.sep )
    for index, part in enumerate( parts ):
        if part in ( 'dependencies', '_download' ):
            return os.sep.join( parts[ : index + 1 ] )
    return None


def repo_relative_path_for_link( path, env ):
    """Repo-relative path segment for remote blob URLs (not human display)."""
    if not path:
        return path

    normalized = os.path.normpath( path ).replace( '\\', '/' )
    if _WORKING_DIR_MARKER in normalized:
        return normalized.split( _WORKING_DIR_MARKER, 1 )[ 1 ]

    storage_root = _storage_root_for_path( path, env )
    if storage_root:
        rel = _try_relpath( path, storage_root )
        if rel:
            parts = rel.split( '/', 1 )
            remainder = parts[ 1 ] if len( parts ) > 1 else ''
            if remainder:
                return remainder
            return rel

    for root in ( env.get( 'sconstruct_dir' ), env.get( 'cxx_profiles_report_root' ) ):
        rel = _try_relpath( path, root )
        if rel:
            if _WORKING_DIR_MARKER in rel:
                return rel.split( _WORKING_DIR_MARKER, 1 )[ 1 ]
            return rel

    return path.replace( '\\', '/' )


def _dependency_remote_link( path, env ):
    from cuppa.core.dependency_identity import enrich_described, short_name_from_git_tree
    from cuppa.core.dependency_storage import describe_tree_path

    storage_root = _storage_root_for_path( path, env )
    if not storage_root:
        return None

    rel = _try_relpath( path, storage_root )
    if not rel:
        return None

    parts = rel.split( '/', 1 )
    folder = parts[ 0 ]
    remainder = parts[ 1 ] if len( parts ) > 1 else ''
    if not remainder:
        return None

    dependency_root = os.path.join( storage_root, folder )
    described = describe_tree_path( dependency_root, storage_root )
    enrich_described( dependency_root, described )

    ref = ref_from_qualifier( described.get( 'qualifier' ) )
    source_url = described.get( 'source_url' )
    browse = normalize_repository_browse_url( source_url ) if source_url else None
    if not browse:
        browse = browse_url_from_short_name( described.get( 'short_name' ) )

    if os.path.isdir( os.path.join( dependency_root, '.git' ) ):
        _short, git_url = short_name_from_git_tree( dependency_root )
        if git_url and not browse:
            browse = normalize_repository_browse_url( git_url )
        if not ref:
            from cuppa.scms import git as git_scm

            try:
                _url, _repository, branch, _remote, _revision = git_scm.Git.info(
                    dependency_root,
                )
                ref = branch or ref
            except ( git_scm.Git.Error, OSError, TypeError, ValueError ):
                pass

    if not browse or not ref:
        return None

    style = hosting_style_from_url( browse )
    blob_base = repository_blob_base( browse, ref, style )
    if not blob_base:
        return None
    return blob_base, remainder


def _project_remote_link( path, env ):
    from cuppa.test_report.html_report import vcs_info_from_location

    sconstruct_dir = env.get( 'sconstruct_dir' )
    if not sconstruct_dir:
        return None

    url, repository, branch, _remote, _revision = vcs_info_from_location(
        sconstruct_dir,
        env.get( 'current_branch' ),
        env.get( 'current_revision' ),
    )
    repo_url = repository or url
    if not repo_url or not branch:
        return None

    style = hosting_style_from_url( repo_url )
    blob_base = repository_blob_base( repo_url, branch, style )
    if not blob_base:
        return None

    relpath = repo_relative_path_for_link( path, env )
    if not relpath:
        return None
    return blob_base, relpath


def resolve_path_remote_link( path, env ):
    """Return ``(blob_base, repo_relative_path)`` for one source file, or ``None``."""
    if not path or not env:
        return None
    if _storage_root_for_path( path, env ):
        return _dependency_remote_link( path, env )
    return _project_remote_link( path, env )


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

    if link_style == 'remote':
        return ''

    url, repository, branch, remote, revision = vcs_info_from_location(
        env[ 'sconstruct_dir' ],
        env.get( 'current_branch' ),
        env.get( 'current_revision' ),
    )
    repo_url = repository or url
    if link_style in ( 'gitlab', 'github' ) and repo_url and branch:
        blob_base = repository_blob_base( repo_url, branch, link_style )
        if blob_base:
            return blob_base
    browse = normalize_repository_browse_url( repo_url )
    if browse:
        return browse
    return ''


def source_file_href( path, line, link_style, link_base, display_path, env=None ):
    """Build a clickable href for one source location in an HTML report."""
    if not path or link_style not in REPORT_LINK_STYLES:
        return None
    display = display_path if display_path is not None else path
    if link_style == 'local':
        if link_base:
            joined = os.path.join( link_base, display )
            return '{}#L{}'.format( joined, line ) if line else joined
        return None
    if link_style == 'remote':
        resolved = resolve_path_remote_link( path, env )
        if not resolved:
            return None
        blob_base, relpath = resolved
        href = '{}/{}'.format(
            blob_base.rstrip( '/' ),
            str( relpath ).lstrip( '/' ).replace( '\\', '/' ),
        )
        if line:
            href = '{}#L{}'.format( href, line )
        return href
    if link_style in ( 'gitlab', 'github' ) and link_base:
        href = '{}/{}'.format( link_base.rstrip( '/' ), display )
        if line:
            href = '{}#L{}'.format( href, line )
        return href
    return None
