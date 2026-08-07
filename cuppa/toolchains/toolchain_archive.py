#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Fetch and register Clang installs as toolchain dependencies.

Public HTTPS / file archives and local ``--clang-root`` prefixes. See
``design/plans/toolchains-as-dependencies.md``.
"""

from __future__ import print_function

import hashlib
import os
import re
import shutil

try:
    from urllib.request import urlretrieve
    from urllib.parse import urlparse, unquote
except ImportError:
    from urllib import urlretrieve, unquote
    from urlparse import urlparse

from cuppa.colourise import as_info, as_notice
from cuppa.log import logger
from cuppa.location import Location
from cuppa.utility.python2to3 import Exception as CuppaException


class ToolchainArchiveException( CuppaException ):
    def __init__( self, value ):
        self.parameter = value

    def __str__( self ):
        return repr( self.parameter )


_RELEASE_DOWNLOAD = re.compile(
    r'/releases/download/(?P<tag>[^/]+)/(?P<asset>[^/?#]+)\Z'
)


def add_options( add_option ):
    add_option(
        '--toolchain-archive',
        dest='toolchain-archive',
        type='string',
        nargs=1,
        action='store',
        help="Public archive URL or local path to a Clang toolchain tarball/zip "
             "(e.g. a GitHub Release asset). Downloaded under downloads_root/toolchains/ "
             "and registered as clang{major}_{release_tag}.",
    )
    add_option(
        '--clang-root',
        dest='clang-root',
        type='string',
        nargs=1,
        action='store',
        help="Path to an existing Clang install prefix containing bin/clang++. "
             "Registered as clang{major}_local_{hash} for this session.",
    )


def sanitise_token( text ):
    token = re.sub( r'[^A-Za-z0-9]+', '_', text or '' ).strip( '_' )
    return token or 'unknown'


def release_tag_from_url( url ):
    path = urlparse( url ).path
    match = _RELEASE_DOWNLOAD.search( path )
    if match:
        return unquote( match.group( 'tag' ) )
    return None


def asset_name_from_spec( spec ):
    path = urlparse( spec ).path if '://' in spec else spec
    return os.path.basename( path.rstrip( '/\\' ) ) or 'toolchain'


def qualifier_for_archive( spec ):
    tag = release_tag_from_url( spec ) if '://' in spec or spec.startswith( 'file:' ) else None
    if tag:
        return sanitise_token( tag )
    stem = asset_name_from_spec( spec )
    for suffix in ( '.tar.gz', '.tar.xz', '.tar.bz2', '.tgz', '.zip' ):
        if stem.lower().endswith( suffix ):
            stem = stem[ : -len( suffix ) ]
            break
    return sanitise_token( stem )


def qualifier_for_root( root_path ):
    digest = hashlib.sha1( os.path.abspath( root_path ).encode( 'utf-8' ) ).hexdigest()[ : 8 ]
    return 'local_{}'.format( digest )


def toolchain_name( major, qualifier ):
    return 'clang{}_{}'.format( int( major ), qualifier )


def find_clang_bin_dir( root ):
    """Return the directory that contains clang++ under ``root``, or None."""
    root = os.path.abspath( root )
    for name in ( 'clang++', 'clang++.exe' ):
        direct = os.path.join( root, 'bin', name )
        if os.path.isfile( direct ):
            return os.path.join( root, 'bin' )
    for dirpath, _dirnames, filenames in os.walk( root ):
        if 'clang++' in filenames or 'clang++.exe' in filenames:
            return dirpath
    return None


def _is_offline( cuppa_env ):
    return bool( cuppa_env.get( 'offline' ) )


def _expand_local_path( spec, cuppa_env ):
    path = spec
    if path.startswith( 'file://' ):
        path = urlparse( path ).path
        if os.name == 'nt' and path.startswith( '/' ) and len( path ) > 2 and path[2] == ':':
            path = path[1:]
    path = os.path.expanduser( path )
    if not os.path.isabs( path ):
        path = os.path.normpath( os.path.join( cuppa_env['sconstruct_dir'], path ) )
    return path


def _download_archive( url, dest_path, cuppa_env ):
    if os.path.isfile( dest_path ):
        return dest_path
    if _is_offline( cuppa_env ):
        raise ToolchainArchiveException(
            "toolchain archive [{}] is not cached and --offline is set".format( url )
        )
    parent = os.path.dirname( dest_path )
    if not os.path.isdir( parent ):
        os.makedirs( parent )
    logger.info( "Downloading toolchain archive [{}]...".format( as_info( url ) ) )
    tmp_path = dest_path + '.partial'
    try:
        urlretrieve( url, tmp_path )
        os.rename( tmp_path, dest_path )
    except Exception as error:
        if os.path.isfile( tmp_path ):
            os.remove( tmp_path )
        raise ToolchainArchiveException(
            "failed to download toolchain archive [{}]: {}".format( url, error )
        )
    return dest_path


def _ensure_extracted( archive_path, extract_root, cuppa_env ):
    bin_dir = find_clang_bin_dir( extract_root )
    if bin_dir:
        return bin_dir
    if os.path.isdir( extract_root ):
        shutil.rmtree( extract_root )
    if cuppa_env.get( 'dump' ) or cuppa_env.get( 'clean' ):
        return None
    Location.extract( archive_path, extract_root )
    bin_dir = find_clang_bin_dir( extract_root )
    if not bin_dir:
        raise ToolchainArchiveException(
            "extracted toolchain archive [{}] has no bin/clang++ under [{}]".format(
                archive_path, extract_root
            )
        )
    return bin_dir


def prepare_from_archive( cuppa_env, spec ):
    downloads = cuppa_env['downloads_root']
    dependencies = cuppa_env['dependencies_root']
    qualifier = qualifier_for_archive( spec )
    asset = asset_name_from_spec( spec )

    if '://' in spec and not spec.startswith( 'file:' ):
        cache_dir = os.path.join( downloads, 'toolchains', 'clang', qualifier )
        archive_path = os.path.join( cache_dir, asset )
        _download_archive( spec, archive_path, cuppa_env )
    else:
        archive_path = _expand_local_path( spec, cuppa_env )
        if not os.path.isfile( archive_path ):
            raise ToolchainArchiveException(
                "toolchain archive path [{}] does not exist".format( archive_path )
            )

    extract_root = os.path.join( dependencies, 'toolchains', 'clang', qualifier )
    bin_dir = _ensure_extracted( archive_path, extract_root, cuppa_env )
    if not bin_dir:
        return None
    return {
        'source': spec,
        'qualifier': qualifier,
        'bin_dir': bin_dir,
        'extract_root': extract_root,
        'kind': 'archive',
    }


def prepare_from_root( cuppa_env, root ):
    root_path = _expand_local_path( root, cuppa_env )
    bin_dir = find_clang_bin_dir( root_path )
    if not bin_dir:
        # Allow passing bin/ directly
        if os.path.isfile( os.path.join( root_path, 'clang++' ) ) or \
                os.path.isfile( os.path.join( root_path, 'clang++.exe' ) ):
            bin_dir = root_path
        else:
            raise ToolchainArchiveException(
                "clang-root [{}] does not contain bin/clang++".format( root_path )
            )
    qualifier = qualifier_for_root( root_path )
    return {
        'source': root_path,
        'qualifier': qualifier,
        'bin_dir': bin_dir,
        'extract_root': root_path,
        'kind': 'root',
    }


def discover_cached( cuppa_env, skip_qualifiers=None ):
    """Find previously extracted Clang toolchain deps under dependencies_root."""
    skip_qualifiers = set( skip_qualifiers or [] )
    dependencies = cuppa_env.get( 'dependencies_root' )
    if not dependencies:
        return []
    base = os.path.join( dependencies, 'toolchains', 'clang' )
    if not os.path.isdir( base ):
        return []
    found = []
    for qualifier in sorted( os.listdir( base ) ):
        if qualifier in skip_qualifiers:
            continue
        extract_root = os.path.join( base, qualifier )
        if not os.path.isdir( extract_root ):
            continue
        bin_dir = find_clang_bin_dir( extract_root )
        if not bin_dir:
            continue
        found.append( {
            'source': extract_root,
            'qualifier': qualifier,
            'bin_dir': bin_dir,
            'extract_root': extract_root,
            'kind': 'cached',
        } )
    return found


def prepare( cuppa_env ):
    """Resolve --toolchain-archive / --clang-root and discover cached toolchain deps."""
    prepared = []
    try:
        archive = cuppa_env.get_option( 'toolchain-archive' )
        clang_root = cuppa_env.get_option( 'clang-root' )
    except Exception:
        archive = None
        clang_root = None

    if archive:
        entry = prepare_from_archive( cuppa_env, archive )
        if entry:
            prepared.append( entry )
    if clang_root:
        prepared.append( prepare_from_root( cuppa_env, clang_root ) )

    skip = { entry['qualifier'] for entry in prepared }
    discovered = discover_cached( cuppa_env, skip_qualifiers=skip )

    cuppa_env['prepared_toolchain_archives'] = prepared
    cuppa_env['discovered_toolchain_archives'] = discovered
    return prepared


class ToolchainArchive( object ):
    """Option registration only; prepare/register are invoked from Construct / Clang."""

    @classmethod
    def add_options( cls, add_option ):
        add_options( add_option )

    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        return


def _register_entries(
        cuppa_env,
        entries,
        add_toolchain,
        add_to_supported,
        clang_cls,
        stdlib,
        suppress_debug_for_auto,
        skip_existing,
):
    names = []
    existing = cuppa_env.get( 'toolchains' ) or {}
    for entry in entries:
        cxx = os.path.join( entry['bin_dir'], 'clang++' )
        if os.name == 'nt' and not os.path.isfile( cxx ):
            cxx = os.path.join( entry['bin_dir'], 'clang++.exe' )
        reported = clang_cls.version_from_command( cxx )
        if not reported:
            if entry.get( 'kind' ) == 'cached':
                logger.warn(
                    "Skipping cached toolchain at [{}]; could not read version".format(
                        as_notice( entry['bin_dir'] )
                    )
                )
                continue
            raise ToolchainArchiveException(
                "could not read version from [{}]".format( cxx )
            )
        name = toolchain_name( reported['major'], entry['qualifier'] )
        if skip_existing and name in existing:
            logger.debug(
                "Skipping toolchain [{}]; already available".format( as_info( name ) )
            )
            continue
        reported = dict( reported )
        reported['name'] = name
        add_to_supported( name )
        toolchain = clang_cls(
            name,
            '',
            reported,
            entry['bin_dir'],
            stdlib,
            suppress_debug_for_auto,
        )
        add_toolchain( name, toolchain )
        existing[ name ] = toolchain
        names.append( name )
        logger.info(
            "Registered toolchain [{}] from [{}] at [{}] (clang {})".format(
                as_info( name ),
                as_notice( entry['source'] ),
                as_notice( entry['bin_dir'] ),
                as_info( reported['version'] ),
            )
        )
    return names


def register_prepared( cuppa_env, add_toolchain, add_to_supported, clang_cls ):
    """Register explicit and cached Clang toolchain installs.

    Cached extracts under ``dependencies_root/toolchains/clang/`` become available for
    ``--toolchains=clang24_profiles_…`` without re-passing ``--toolchain-archive``.
    Auto-select (when ``--toolchains`` is omitted) only applies to toolchains fetched
    this session via ``--toolchain-archive`` / ``--clang-root``.
    """
    try:
        stdlib = cuppa_env.get_option( 'clang-stdlib' )
        suppress_debug_for_auto = cuppa_env.get_option( 'clang-disable-debug-for-auto' )
    except Exception:
        stdlib = None
        suppress_debug_for_auto = False
    if not stdlib:
        stdlib = clang_cls.default_stdlib()

    prepared = cuppa_env.get( 'prepared_toolchain_archives' ) or []
    discovered = cuppa_env.get( 'discovered_toolchain_archives' ) or []

    explicit_names = _register_entries(
        cuppa_env, prepared, add_toolchain, add_to_supported, clang_cls,
        stdlib, suppress_debug_for_auto, skip_existing=False,
    )
    _register_entries(
        cuppa_env, discovered, add_toolchain, add_to_supported, clang_cls,
        stdlib, suppress_debug_for_auto, skip_existing=True,
    )

    cuppa_env['toolchain_archive_names'] = explicit_names
    return explicit_names
