#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Shared source-link styles for HTML reports (test, Profiles, future coverage)
#-------------------------------------------------------------------------------

import html
import os
from collections import namedtuple

try:
    from urlparse import urlparse, quote
except ImportError:
    from urllib.parse import urlparse, quote

from cuppa.log import logger

REPORT_LINK_STYLES = ( 'local', 'gitlab', 'github', 'remote' )

HOSTING_PROVIDERS = ( 'github', 'gitlab', 'bitbucket', 'gitea', 'azure_devops', 'unknown' )

DEFAULT_GITHUB_HOSTS = ( 'github.com', )
DEFAULT_GITLAB_HOSTS = ( 'gitlab.com', )
DEFAULT_BITBUCKET_HOSTS = ( 'bitbucket.org', )
DEFAULT_GITEA_HOSTS = ( 'codeberg.org', 'gitea.com', 'forgejo.org', )
DEFAULT_AZURE_DEVOPS_HOSTS = ( 'dev.azure.com', 'visualstudio.com', )

REPORTS_HOST_ENV_KEYS = {
    'github': 'reports_github_hosts',
    'gitlab': 'reports_gitlab_hosts',
    'bitbucket': 'reports_bitbucket_hosts',
    'gitea': 'reports_gitea_hosts',
    'azure_devops': 'reports_azure_devops_hosts',
}

PROVIDER_HINTS = (
    ( 'GH', 'github', 'GitHub' ),
    ( 'GL', 'gitlab', 'GitLab' ),
    ( 'BB', 'bitbucket', 'Bitbucket' ),
    ( 'GT', 'gitea', 'Gitea / Forgejo / Codeberg' ),
    ( 'AD', 'azure_devops', 'Azure DevOps' ),
)

RemoteLinkResolution = namedtuple(
    'RemoteLinkResolution',
    ( 'browse_url', 'ref', 'relpath', 'provider', 'source_url' ),
)

UNKNOWN_HOSTING_NOTES_KEY = '_reports_unknown_hosts'

_WORKING_DIR_MARKER = '/working/'
_UNQUALIFIED_SUFFIX = ' (unqualified)'


def normalize_host_suffix( raw ):
    """Return a lower-case host suffix for matching and log display.

    Accepts bare hostnames (``git.corp.example``) or URLs with a scheme
    (``https://git.corp.example/``); strips userinfo, paths, and leading dots.
    """
    if raw is None:
        return None
    text = str( raw ).strip()
    if not text:
        return None
    if '://' in text:
        parsed = urlparse( text )
        if parsed.netloc:
            text = parsed.netloc.split( '@' )[-1 ]
        elif parsed.path:
            text = parsed.path.split( '/' )[ 0 ]
    else:
        text = text.split( '@' )[-1 ].split( '/' )[ 0 ]
    text = text.lower().lstrip( '.' ).rstrip( '.' )
    return text or None


def parse_host_list( raw ):
    """Parse a comma-separated host suffix list or an existing sequence."""
    if raw is None:
        return None
    if isinstance( raw, ( list, tuple ) ):
        items = raw
    else:
        items = str( raw ).split( ',' )
    hosts = []
    for item in items:
        host = normalize_host_suffix( item )
        if host:
            hosts.append( host )
    return hosts or None


def reports_host_config( env=None ):
    """Return effective host suffix lists for each recognised provider."""
    env = env or {}
    config = {}
    defaults = {
        'github': DEFAULT_GITHUB_HOSTS,
        'gitlab': DEFAULT_GITLAB_HOSTS,
        'bitbucket': DEFAULT_BITBUCKET_HOSTS,
        'gitea': DEFAULT_GITEA_HOSTS,
        'azure_devops': DEFAULT_AZURE_DEVOPS_HOSTS,
    }
    for provider, default_hosts in defaults.items():
        key = REPORTS_HOST_ENV_KEYS[ provider ]
        custom = parse_host_list( env.get( key ) )
        config[ provider ] = tuple( custom ) if custom else default_hosts
    return config


def _hostname_from_browse_url( browse_url ):
    if not browse_url:
        return None
    parsed = urlparse( browse_url )
    if parsed.netloc:
        return parsed.netloc.split( '@' )[-1 ].lower()
    return None


def _host_matches( hostname, pattern ):
    if not hostname or not pattern:
        return False
    host = hostname.lower()
    suffix = str( pattern ).lower().lstrip( '.' )
    return host == suffix or host.endswith( '.{}'.format( suffix ) )


def detect_hosting_provider( repository_url, env=None ):
    """Return a recognised provider name, or ``unknown`` when unmapped."""
    browse = normalize_repository_browse_url( repository_url )
    hostname = _hostname_from_browse_url( browse )
    if not hostname:
        return 'unknown'
    for provider, hosts in reports_host_config( env ).items():
        for pattern in hosts:
            if _host_matches( hostname, pattern ):
                return provider
    return 'unknown'


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


def hosting_style_from_url( repository_url, env=None ):
    """Legacy helper: ``github`` or ``gitlab`` blob shape for tag/commit links."""
    provider = detect_hosting_provider( repository_url, env )
    if provider == 'github':
        return 'github'
    if provider in ( 'gitlab', 'bitbucket', 'gitea', 'azure_devops' ):
        return 'gitlab'
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


def remote_provider_hints_enabled( env ):
    if env is None:
        return True
    value = env.get( 'reports_remote_provider_hints' )
    if value is None:
        return True
    return bool( value )


def repository_blob_base( repository_url, branch, link_style, env=None ):
    """Return the repository blob URL prefix for a forced link style."""
    browse = normalize_repository_browse_url( repository_url )
    if not browse or not branch:
        return ''
    if link_style == 'remote':
        provider = detect_hosting_provider( browse, env )
        if provider == 'unknown':
            return browse
        return blob_base_for_provider( browse, branch, provider )
    if link_style in ( 'gitlab', 'github', 'bitbucket', 'gitea', 'azure_devops' ):
        return blob_base_for_provider( browse, branch, link_style )
    return ''


def blob_base_for_provider( browse_url, ref, provider ):
    """Return the URL prefix before the repo-relative file path."""
    browse = ( browse_url or '' ).rstrip( '/' )
    if not browse or not ref:
        return ''
    if provider == 'github':
        return '{}/blob/{}'.format( browse, ref )
    if provider == 'gitlab':
        return '{}/-/blob/{}'.format( browse, ref )
    if provider == 'bitbucket':
        return '{}/src/{}'.format( browse, ref )
    if provider == 'gitea':
        return '{}/src/branch/{}'.format( browse, ref )
    if provider == 'azure_devops':
        return browse
    return browse


def file_href_for_provider( browse_url, ref, relpath, line, provider ):
    """Build a provider-specific file URL, or ``None`` when unsupported."""
    browse = ( browse_url or '' ).rstrip( '/' )
    path = str( relpath or '' ).lstrip( '/' ).replace( '\\', '/' )
    if not browse or not ref or not path:
        return None
    if provider == 'github':
        href = '{}/blob/{}/{}'.format( browse, ref, path )
        if line:
            href = '{}#L{}'.format( href, line )
        return href
    if provider == 'gitlab':
        href = '{}/-/blob/{}/{}'.format( browse, ref, path )
        if line:
            href = '{}#L{}'.format( href, line )
        return href
    if provider == 'bitbucket':
        href = '{}/src/{}/{}'.format( browse, ref, path )
        if line:
            href = '{}#lines-{}'.format( href, line )
        return href
    if provider == 'gitea':
        href = '{}/src/branch/{}/{}'.format( browse, ref, path )
        if line:
            href = '{}#L{}'.format( href, line )
        return href
    if provider == 'azure_devops':
        path_param = path if path.startswith( '/' ) else '/{}'.format( path )
        href = '{}?path={}&version=GB{}'.format(
            browse,
            quote( path_param ),
            ref,
        )
        if line:
            href = '{}&line={}&lineEnd={}&lineStartColumn=1&lineEndColumn=1'.format(
                href,
                line,
                line,
            )
        return href
    return None


def _path_suffix_for_display( relpath, line ):
    path = str( relpath or '' ).lstrip( '/' ).replace( '\\', '/' )
    suffix = '/{}'.format( path ) if path else ''
    if line:
        suffix = '{}#L{}'.format( suffix, line )
    return suffix


def build_unmapped_remote_link_html( resolution, line, env ):
    """HTML display: linked repo root, plain path suffix, optional provider hints."""
    browse = resolution.browse_url
    if not browse:
        return None
    suffix = _path_suffix_for_display( resolution.relpath, line )
    parts = [
        '<a href="{}">{}</a>{}'.format(
            html.escape( browse, quote=True ),
            html.escape( browse ),
            html.escape( suffix ),
        )
    ]
    if remote_provider_hints_enabled( env ):
        hints = []
        for code, provider, title in PROVIDER_HINTS:
            hint_href = file_href_for_provider(
                browse,
                resolution.ref,
                resolution.relpath,
                line,
                provider,
            )
            if not hint_href:
                continue
            hints.append(
                '<a href="{}" title="{}">{}</a>'.format(
                    html.escape( hint_href, quote=True ),
                    html.escape( title ),
                    html.escape( code ),
                )
            )
        if hints:
            parts.append( ' ' )
            parts.append( ', '.join( hints ) )
    return ''.join( parts )


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


def reset_unknown_hosting_notes( env ):
    """Clear accumulated unmapped repository hosts before one report emission."""
    if env is not None:
        env[ UNKNOWN_HOSTING_NOTES_KEY ] = set()


def log_unknown_hosting_summary( env ):
    """Emit one console note listing unmapped repository hosts for this report run."""
    from cuppa.colourise import as_emphasised, as_info

    if not env:
        return
    unknown = env.get( UNKNOWN_HOSTING_NOTES_KEY ) or set()
    if not unknown:
        return
    hostnames = sorted( unknown )
    host_list = '[{}]'.format(
        ', '.join( as_info( hostname ) for hostname in hostnames ),
    )
    logger.info(
        'Unmapped repository hosts for remotes: {}. '
        'The HTML report includes GH/GL/BB/GT/AD provider hint links for these sources. '
        'Map a host to a provider blob URL shape with '
        '{}, {}, or the matching '
        '{}, {}, or {} host flags (same keys in configure.conf). '
        'See the CLI reference and Configuration docs.'.format(
            host_list,
            as_emphasised( '--reports-github-hosts=HOST' ),
            as_emphasised( '--reports-gitlab-hosts=HOST' ),
            as_emphasised( 'bitbucket' ),
            as_emphasised( 'gitea' ),
            as_emphasised( 'azure-devops' ),
        ),
    )


def _record_unknown_hosting( browse, env ):
    if not browse or not env:
        return
    hostname = _hostname_from_browse_url( browse )
    if not hostname:
        return
    notes = env.setdefault( UNKNOWN_HOSTING_NOTES_KEY, set() )
    if hostname in notes:
        return
    notes.add( hostname )
    logger.debug(
        'reports: unknown hosting for %s; using repository URL with provider hints',
        hostname,
    )


def _resolve_remote_metadata( browse, ref, source_url, env ):
    if not browse or not ref:
        return None
    provider = detect_hosting_provider( browse, env )
    if provider == 'unknown':
        _record_unknown_hosting( browse, env )
    return RemoteLinkResolution(
        browse_url=browse,
        ref=ref,
        relpath=None,
        provider=provider,
        source_url=source_url,
    )


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
            source_url = source_url or git_url
        if not ref:
            from cuppa.scms import git as git_scm

            try:
                _url, _repository, branch, _remote, _revision = git_scm.Git.info(
                    dependency_root,
                )
                ref = branch or ref
            except ( git_scm.Git.Error, OSError, TypeError, ValueError ):
                pass

    resolution = _resolve_remote_metadata( browse, ref, source_url, env )
    if not resolution:
        return None
    return resolution._replace( relpath=remainder )


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

    browse = normalize_repository_browse_url( repo_url )
    resolution = _resolve_remote_metadata( browse, branch, repo_url, env )
    if not resolution:
        return None

    relpath = repo_relative_path_for_link( path, env )
    if not relpath:
        return None
    return resolution._replace( relpath=relpath )


def resolve_path_remote_link( path, env ):
    """Return remote link metadata for one source file, or ``None``."""
    if not path or not env:
        return None
    if _storage_root_for_path( path, env ):
        return _dependency_remote_link( path, env )
    return _project_remote_link( path, env )


def source_link_display( path, line, link_style, link_base, display_path, env=None ):
    """Return ``href``, plain ``label``, and optional ``label_html`` for one source location."""
    env = env or {}
    display = display_path if display_path is not None else path
    if link_style not in REPORT_LINK_STYLES:
        return {
            'href': None,
            'label': display,
            'label_html': None,
        }
    if link_style == 'local':
        href = None
        if link_base:
            joined = os.path.join( link_base, display )
            href = '{}#L{}'.format( joined, line ) if line else joined
        return {
            'href': href,
            'label': display_path_on_disk( path ),
            'label_html': None,
        }
    if link_style == 'remote':
        resolution = resolve_path_remote_link( path, env )
        if not resolution:
            return {
                'href': None,
                'label': display,
                'label_html': None,
            }
        if resolution.provider != 'unknown':
            mapped_href = file_href_for_provider(
                resolution.browse_url,
                resolution.ref,
                resolution.relpath,
                line,
                resolution.provider,
            )
            return {
                'href': mapped_href,
                'label': mapped_href,
                'label_html': None,
            }
        browse = resolution.browse_url
        suffix = _path_suffix_for_display( resolution.relpath, line )
        label = '{}{}'.format( browse, suffix )
        return {
            'href': browse,
            'label': label,
            'label_html': build_unmapped_remote_link_html( resolution, line, env ),
        }
    if link_style in ( 'gitlab', 'github' ) and link_base:
        href = '{}/{}'.format( link_base.rstrip( '/' ), display )
        if line:
            href = '{}#L{}'.format( href, line )
        return {
            'href': href,
            'label': href,
            'label_html': None,
        }
    return {
        'href': None,
        'label': display,
        'label_html': None,
    }


def display_path_on_disk( path ):
    """Shorten an on-disk path with a leading ``~/`` when under the home directory."""
    if not path:
        return path
    try:
        real_path = os.path.realpath( path )
        home = os.path.realpath( os.path.expanduser( '~' ) )
        if os.path.commonpath( [ real_path, home ] ) == home:
            return '~' + real_path[ len( home ): ].replace( '\\', '/' )
    except ( OSError, ValueError ):
        pass
    return path.replace( '\\', '/' )


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
        blob_base = repository_blob_base( repo_url, branch, link_style, env )
        if blob_base:
            return blob_base
    browse = normalize_repository_browse_url( repo_url )
    if browse:
        return browse
    return ''


def source_file_href( path, line, link_style, link_base, display_path, env=None ):
    """Build a clickable href for one source location in an HTML report."""
    display = source_link_display(
        path,
        line,
        link_style,
        link_base,
        display_path,
        env=env,
    )
    return display.get( 'href' )
