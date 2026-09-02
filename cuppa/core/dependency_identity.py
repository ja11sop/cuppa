#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency identity — short names, stems, and display qualifiers
#-------------------------------------------------------------------------------

"""Derive human short names and stems for dependency trees on disk.

Used by ``--list-dependencies`` grouping (§4.8 / §4.9). Prefer live git remotes and
path-shape package names over decoding lossy folder stems.
"""

import os
import platform
import re
from urllib.parse import urlparse, unquote

from cuppa.core.dependency_storage import (
    looks_like_tool_variant_dir,
    split_location_folder_name,
)
from cuppa.scms import git as git_scm


# Boost source archive folders encoded from HTTPS URLs.


def short_name_from_git_url( url ):
    """Turn an origin URL into ``host/org/repo`` (no ``.git`` suffix)."""
    if not url:
        return None
    text = str( url ).strip()
    if not text:
        return None

    # git@host:path
    scp = re.match( r'^git@([^:]+):(.+)$', text )
    if scp:
        host, path = scp.group( 1 ), scp.group( 2 )
        return _host_path( host, path )

    # ssh://git@host/path or https://host/path
    if '://' in text:
        parsed = urlparse( text )
        host = parsed.hostname or parsed.netloc
        if '@' in ( host or '' ):
            host = host.split( '@', 1 )[-1]
        path = unquote( parsed.path or '' )
        return _host_path( host, path )

    return None


def _host_path( host, path ):
    if not host:
        return None
    path = ( path or '' ).lstrip( '/' )
    if path.endswith( '.git' ):
        path = path[:-4]
    path = path.rstrip( '/' )
    if not path:
        return host
    # Drop userinfo-style host leftovers.
    host = host.split( '@' )[-1]
    return '{}/{}'.format( host, path )


def short_name_from_git_tree( path ):
    """Read ``origin`` from a working copy and return a short name, or None."""
    try:
        _url, repository, _branch, _remote, _revision = git_scm.Git.info( path )
    except ( git_scm.Git.Error, OSError, TypeError, ValueError ):
        return None, None
    return short_name_from_git_url( repository ), repository


def wipe_token_leaf_name( name ):
    """Reduce a display/identity name to a ``name/@`` force-wipe leaf.

    Host/path short names (``gitlab.example/org/widget``) become the repo
    segment (``widget``) so Location hints match registry-style
    ``dependency`` / ``short_name`` candidates. Encoded folder stems
    (``git_https_…``) return ``None`` so callers can fall through.
    """
    text = ( name or '' ).strip()
    if not text:
        return None
    if '/' in text:
        text = text.rstrip( '/' ).rsplit( '/', 1 )[-1]
    if text.endswith( '.git' ):
        text = text[:-4]
    if not text or text.startswith(
            ( 'git_', 'https_', 'svn_', 'hg_', 'bzr_', 'http_' )
    ):
        return None
    return text


def boost_archive_from_folder( folder ):
    """Return ``(short_name, version)`` for a Boost source archive folder, or ``(None, None)``."""
    if not folder or 'boost' not in folder.lower():
        return None, None
    # Prefer boost_1_86_0 style (underscored).
    underscored = re.search( r'boost_(\d+)_(\d+)(?:_(\d+))?', folder, re.IGNORECASE )
    if underscored:
        major, minor, patch = underscored.group( 1 ), underscored.group( 2 ), underscored.group( 3 )
        version = '{}.{}'.format( major, minor )
        if patch is not None:
            version = '{}.{}'.format( version, patch )
        return 'boost', version
    dotted = re.search( r'release_(\d+\.\d+(?:\.\d+)?)', folder, re.IGNORECASE )
    if dotted:
        return 'boost', dotted.group( 1 )
    return None, None


def boost_remote_from_folder( folder ):
    """Reconstruct a Boost download URL from an encoded folder name, or ``None``."""
    if not folder or 'boost' not in folder.lower():
        return None
    underscored = re.search( r'boost_(\d+)_(\d+)(?:_(\d+))?', folder, re.IGNORECASE )
    if not underscored:
        return None
    major, minor, patch = underscored.group( 1 ), underscored.group( 2 ), underscored.group( 3 )
    if patch is None:
        patch = '0'
    version = '{}.{}.{}'.format( major, minor, patch )
    stem = 'boost_{}_{}_{}'.format( major, minor, patch )
    extension = boost_archive_extension_from_folder( folder )
    # Prefer matching the host encoded in the folder.
    if 'archives.boost.io' in folder:
        return 'https://archives.boost.io/release/{}/source/{}{}'.format(
                version, stem, extension
        )
    if 'boostorg.jfrog.io' in folder:
        return (
            'https://boostorg.jfrog.io/artifactory/main/release/'
            '{}/source/{}{}'.format( version, stem, extension )
        )
    # Fallback to the current canonical host.
    return 'https://archives.boost.io/release/{}/source/{}{}'.format(
            version, stem, extension
    )


def boost_archive_extension_from_folder( folder ):
    """Archive suffix encoded in a Boost folder name, or the platform download default."""
    match = re.search( r'\.(zip|tar\.gz|tar\.bz2|7z)$', str( folder or '' ), re.IGNORECASE )
    if match:
        return '.' + match.group( 1 ).lower()
    if platform.system() == 'Windows':
        return '.zip'
    return '.tar.gz'


# Encoded GitHub archive downloads:
#   https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip
# → https_github.com__fmtlib_fmt_archive_refs_tags_11.1.4.zip
_GITHUB_ARCHIVE_FOLDER = re.compile(
        r'^https_github\.com__'
        r'(?P<owner>[A-Za-z0-9.-]+)_(?P<repo>[A-Za-z0-9.-]+)_'
        r'archive_'
        r'(?:(?P<kind>refs_tags|refs_heads)_)?'
        r'(?P<ref>.+?)'
        r'(?:\.(?P<ext>zip|tar\.gz|tgz|tar\.bz2|tar\.xz))?$',
        re.IGNORECASE,
)


def github_archive_from_folder( folder ):
    """Return ``(short_name, version, remote_url)`` for a GitHub archive folder.

    Returns ``(None, None, None)`` when the folder does not match the usual
    ``github.com/<owner>/<repo>/archive/...`` encoding.
    """
    if not folder:
        return None, None, None
    match = _GITHUB_ARCHIVE_FOLDER.match( folder )
    if not match:
        return None, None, None
    owner = match.group( 'owner' )
    repo = match.group( 'repo' )
    ref = match.group( 'ref' )
    kind = match.group( 'kind' )
    ext = match.group( 'ext' ) or 'zip'
    short_name = 'github.com/{}/{}'.format( owner, repo )
    if kind == 'refs_heads':
        remote = 'https://github.com/{}/{}/archive/refs/heads/{}.{}'.format(
                owner, repo, ref, ext
        )
    elif kind == 'refs_tags':
        remote = 'https://github.com/{}/{}/archive/refs/tags/{}.{}'.format(
                owner, repo, ref, ext
        )
    else:
        remote = 'https://github.com/{}/{}/archive/{}.{}'.format(
                owner, repo, ref, ext
        )
    return short_name, ref, remote


def display_qualifier( qualifier, storage_type='repository' ):
    """Normalise a qualifier for the tree: unspecified location → ``@``."""
    if storage_type in ( 'gitlab', 'conan', 'archive', 'toolchain' ):
        if not qualifier or qualifier == '-':
            return '-'
        return str( qualifier )
    if not qualifier or qualifier == '-' or qualifier == '':
        return '@'
    text = str( qualifier )
    if not text.startswith( '@' ):
        return '@' + text
    return text


_VCS_FOLDER_PREFIXES = ( 'git_', 'svn_', 'hg_', 'bzr_' )


def unqualified_default_branch_label(
        folder, default_branch, storage_type='repository', *,
        has_canonical_sibling=False,
):
    """Label an unqualified stem as ``@<default> (unqualified)``, or ``None``.

    Encoded VCS folder names (``git_…``) always qualify. On Windows, ``Location``
    hashes those names for MAX_PATH, so the stem loses the ``git_`` prefix; pass
    ``has_canonical_sibling=True`` when ``stem@<default>`` exists beside it.
    """
    if storage_type not in ( 'repository', 'location', 'unknown' ):
        return None
    if not folder or not default_branch:
        return None
    if not folder.startswith( _VCS_FOLDER_PREFIXES ) and not has_canonical_sibling:
        return None
    _stem, folder_qualifier = split_location_folder_name( folder )
    if folder_qualifier:
        return None
    return '@{} (unqualified)'.format( default_branch )


def enrich_described( path, described ):
    """Add ``short_name``, ``stem``, ``source_url`` to a ``describe_tree_path`` result.

    Mutates and returns ``described``.
    """
    storage_type = described.get( 'type' ) or 'unknown'
    dependency = described.get( 'dependency' ) or ''
    qualifier = described.get( 'qualifier' )
    folder = os.path.basename( path.rstrip( '\\/' ) )
    stem, folder_qualifier = split_location_folder_name( folder )

    described.setdefault( 'stem', None )
    described.setdefault( 'short_name', None )
    described.setdefault( 'source_url', None )

    if storage_type == 'gitlab':
        described['short_name'] = dependency
        described['stem'] = dependency
        return described

    if storage_type == 'conan':
        described['short_name'] = dependency
        described['stem'] = dependency
        return described

    if storage_type == 'toolchain':
        described['short_name'] = dependency
        described['stem'] = dependency
        return described

    if storage_type == 'archive':
        boost_name, boost_version = boost_archive_from_folder( folder )
        if boost_name:
            described['short_name'] = boost_name
            described['stem'] = folder
            if not qualifier and boost_version:
                described['qualifier'] = boost_version
            remote = boost_remote_from_folder( folder )
            if remote:
                described['source_url'] = remote
            return described
        gh_name, gh_version, gh_remote = github_archive_from_folder( folder )
        if gh_name:
            described['short_name'] = gh_name
            described['stem'] = folder
            if not qualifier and gh_version:
                described['qualifier'] = gh_version
            if gh_remote:
                described['source_url'] = gh_remote
            return described
        described['short_name'] = dependency or folder
        described['stem'] = folder
        return described

    # location (and unknown treated as location-like)
    described['stem'] = stem
    if not qualifier and folder_qualifier:
        described['qualifier'] = folder_qualifier

    if os.path.isdir( os.path.join( path, '.git' ) ):
        short, url = short_name_from_git_tree( path )
        if short:
            described['short_name'] = short
        if url:
            described['source_url'] = url
    if not described.get( 'short_name' ):
        # Fallback: keep encoded stem visible rather than inventing a path.
        described['short_name'] = stem or dependency or folder
    return described


def location_display( path, dependencies_root, source_url=None ):
    """Text for the LOCATION column: prefer URL, else path relative to the root."""
    if source_url:
        return source_url
    try:
        relative = os.path.relpath( path, os.path.realpath( dependencies_root ) )
        if not relative.startswith( '..' ):
            return relative
    except ValueError:
        pass
    return path


def strip_vcs_qualifier( url ):
    """Remove a pip-style ``@rev`` suffix from a VCS URL.

    Bare trailing ``@`` (unspecified revision) is preserved. ``git@host`` userinfo is
    not treated as a revision.
    """
    if not url:
        return url
    text = str( url )
    if text.endswith( '@' ):
        return text
    if '://' not in text:
        return text
    scheme, _, rest = text.partition( '://' )
    # Revision '@' only when a path separator appears before it (not git@host alone).
    match = re.match( r'^(.*[/:].+)@([^/@]+)$', rest )
    if not match:
        return text
    return '{}://{}'.format( scheme, match.group( 1 ) )


def with_vcs_qualifier( url, qualifier ):
    """Attach a branch/tag qualifier (``@master``, ``@``, …) to a repository URL."""
    if not url:
        return ''
    base = strip_vcs_qualifier( url ) or ''
    display = display_qualifier( qualifier, 'repository' )
    if display == '@':
        if base.endswith( '@' ):
            return base
        return base + '@'
    branch = display[1:] if display.startswith( '@' ) else display
    if base.endswith( '@' ):
        return base + branch
    return '{}@{}'.format( base, branch )


def gitlab_package_from_remote( remote_location ):
    """Return ``(package, version)`` from ``registry/package/version``, or ``(None, None)``."""
    if not remote_location:
        return None, None
    parts = [ p for p in str( remote_location ).rstrip( '/' ).split( '/' ) if p ]
    if len( parts ) < 2:
        return None, None
    return parts[-2], parts[-1]


def gitlab_registry_base( remote_location ):
    """Return the registry prefix with ``/package/version`` stripped, or ``None``."""
    package, _version = gitlab_package_from_remote( remote_location )
    if not package:
        return None
    text = str( remote_location ).rstrip( '/' )
    parent, sep, _ = text.rpartition( '/' )  # drop version
    if not sep:
        return None
    parent, sep, _ = parent.rpartition( '/' )  # drop package
    if not sep:
        return None
    return parent


def gitlab_package_from_path( path ):
    """Return ``(package, version)`` from a ``…/<tool_variant>/<package>/<version>`` path."""
    if not path:
        return None, None
    parts = [ p for p in str( path ).replace( '\\', '/' ).split( '/' ) if p ]
    if len( parts ) < 2:
        return None, None
    return parts[-2], parts[-1]


def gitlab_family_name( row ):
    """Return the on-disk GitLab package folder that groups registry aliases.

    ``boost_package`` (registry) and ``…/<tool>/boost/<version>`` (folder) share
    family ``boost``, so unused sibling versions stay under one list identity.
    """
    folder = row.get( 'package_folder' )
    if folder:
        return folder
    path = row.get( 'path' ) or ''
    parts = [ p for p in str( path ).replace( '\\', '/' ).split( '/' ) if p ]
    # Extract: <tool_variant>/<package>/<version>
    if len( parts ) >= 3 and looks_like_tool_variant_dir( parts[-3] ):
        return parts[-2]
    # Download archive: packages/<package>/<version>/<archive>
    if len( parts ) >= 4 and parts[-4] == 'packages':
        return parts[-3]
    package, _version = gitlab_package_from_remote(
            row.get( 'remote_location' ) or row.get( 'source_url' ) or ''
    )
    if package:
        return package
    return None


def list_identity_key( row ):
    """Stable ``(type, family)`` key for list tree / ``--list-scope`` grouping."""
    storage_type = row.get( 'type' ) or row.get( 'kind' ) or 'unknown'
    if storage_type == 'gitlab':
        family = gitlab_family_name( row )
        if family:
            return ( storage_type, family )
    short = (
            row.get( 'short_name' )
            or row.get( 'stem' )
            or row.get( 'dependency' )
            or '-'
    )
    return ( storage_type, short )


def gitlab_remote_for_version( remote_location, version ):
    """Replace the version segment of a ``registry/package/version`` URL."""
    if not remote_location or version in ( None, '', '-' ):
        return remote_location
    text = str( remote_location ).rstrip( '/' )
    package, _old = gitlab_package_from_remote( text )
    if not package:
        return remote_location
    parent, sep, _ = text.rpartition( '/' )
    if not sep:
        return remote_location
    return '{}{}{}'.format( parent, sep, version )


def gitlab_remote_for_package_version( registry_base, package, version ):
    """Build ``registry/package/version`` from a registry prefix."""
    if not registry_base or not package or version in ( None, '', '-' ):
        return None
    return '{}/{}/{}'.format(
            str( registry_base ).rstrip( '/' ), package, version
    )


def gitlab_archive_name( package, tool_variant, system=None, extension=None, omit_os=False ):
    """Archive basename as published/downloaded for a GitLab generic package."""
    if not package or not tool_variant or tool_variant in ( '-', '' ):
        return None
    from cuppa.package_managers.gitlab import (
        os_release_id,
        package_archive_extension,
    )
    if extension is None:
        extension = package_archive_extension()
    if omit_os:
        return '{package}_{build}{ext}'.format(
                package=package,
                build=tool_variant,
                ext=extension,
        )
    if system is None:
        system = os_release_id()
    return '{package}_{system}_{build}{ext}'.format(
            package=package,
            system=system,
            build=tool_variant,
            ext=extension,
    )


# Verbose LOCATION prefix when a regenerating archive exists under downloads_root.
DOWNLOAD_MARK = '[D]'

# Extract / expanded tree under dependencies_root (used by --list-downloads).
EXTRACT_MARK = '[E]'


def with_download_mark( location, has_download ):
    """Prefix LOCATION with ``[D]`` when a downloads-root archive is present."""
    if not location or not has_download:
        return location or ''
    text = str( location )
    prefix = DOWNLOAD_MARK + ' '
    if text.startswith( prefix ) or text.startswith( DOWNLOAD_MARK ):
        return text
    return prefix + text


def with_extract_mark( label ):
    """Prefix an extract/product leaf label with ``[E]``."""
    if not label:
        return EXTRACT_MARK
    text = str( label )
    prefix = EXTRACT_MARK + ' '
    if text.startswith( prefix ) or text.startswith( EXTRACT_MARK ):
        return text
    return prefix + text


def find_cached_download(
        downloads_root,
        *,
        storage_type,
        path=None,
        package=None,
        version=None,
        tool_variant=None,
        package_archive=None,
        inventory_downloads=None,
):
    """Return an existing download path for this dependency tree, or ``None``.

    Archive / HTTP extracts use ``<downloads_root>/<encoded folder>``. GitLab packages
    use ``<downloads_root>/packages/<package>/<version>/<archive>.{zip,tar.gz}``.
    Toolchain archives use ``<downloads_root>/toolchains/<identity>/<qualifier>/<asset>``.
    """
    if inventory_downloads:
        for candidate in inventory_downloads:
            if candidate and os.path.isfile( candidate ):
                return candidate
    if not downloads_root or not os.path.isdir( downloads_root ):
        return None

    if storage_type == 'archive' and path:
        folder = os.path.basename( str( path ).rstrip( '\\/' ) )
        if not folder:
            return None
        direct = os.path.join( downloads_root, folder )
        if os.path.isfile( direct ):
            return direct
        # Match Location.get_cached_archive style (fnmatch on the folder pattern).
        try:
            for name in os.listdir( downloads_root ):
                if name == folder or (
                        folder and name.startswith( folder )
                ):
                    candidate = os.path.join( downloads_root, name )
                    if os.path.isfile( candidate ):
                        return candidate
        except OSError:
            return None
        return None

    if storage_type == 'gitlab':
        pkg = package
        ver = version
        if ( not pkg or not ver ) and path:
            pkg, ver = gitlab_package_from_path( path )
        if not pkg or not ver:
            return None
        package_dir = os.path.join( downloads_root, 'packages', pkg, str( ver ) )
        if not os.path.isdir( package_dir ):
            return None
        archive = package_archive
        if not archive:
            archive = gitlab_archive_name( pkg, tool_variant )
        if archive:
            candidate = os.path.join( package_dir, archive )
            if os.path.isfile( candidate ):
                return candidate
            # Preferred extension missing: try the alternate (.zip ↔ .tar.gz).
            from cuppa.package_managers.gitlab import (
                package_archive_extensions,
                strip_package_archive_extension,
            )
            stem = strip_package_archive_extension( archive )
            for extension in package_archive_extensions():
                alternate = stem + extension
                if alternate == archive:
                    continue
                candidate = os.path.join( package_dir, alternate )
                if os.path.isfile( candidate ):
                    return candidate
        try:
            for name in sorted( os.listdir( package_dir ) ):
                candidate = os.path.join( package_dir, name )
                if not os.path.isfile( candidate ):
                    continue
                if tool_variant and tool_variant not in name:
                    continue
                return candidate
        except OSError:
            return None
        return None

    if storage_type == 'toolchain':
        # downloads_root/toolchains/<identity>/<qualifier>/<asset>
        identity = package
        qualifier = version
        if ( not identity or not qualifier or qualifier == '-' ) and path:
            parts = [
                    part for part in str( path ).replace( '\\', '/' ).split( '/' ) if part
            ]
            try:
                idx = parts.index( 'toolchains' )
            except ValueError:
                idx = -1
            if idx >= 0 and len( parts ) >= idx + 3:
                identity = identity or parts[idx + 1]
                qualifier = qualifier if qualifier not in ( None, '', '-' ) else parts[idx + 2]
        if not identity or not qualifier or qualifier == '-':
            return None
        cache_dir = os.path.join( downloads_root, 'toolchains', identity, str( qualifier ) )
        if not os.path.isdir( cache_dir ):
            return None
        try:
            for name in sorted( os.listdir( cache_dir ) ):
                candidate = os.path.join( cache_dir, name )
                if os.path.isfile( candidate ):
                    return candidate
        except OSError:
            return None
        return None

    # Location trees: optional raw archive beside the working copy name.
    if storage_type in ( 'repository', 'location' ) and path:
        folder = os.path.basename( str( path ).rstrip( '\\/' ) )
        stem, _ = split_location_folder_name( folder )
        for name in ( folder, stem ):
            if not name:
                continue
            candidate = os.path.join( downloads_root, name )
            if os.path.isfile( candidate ):
                return candidate
    return None
