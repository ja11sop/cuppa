#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Fetch and register Clang / GCC installs as toolchain dependencies.

Public HTTPS / file archives (Clang tarballs, Debian ``gcc-snapshot`` ``.deb`` files)
and local ``--clang-root`` / ``--gcc-root`` prefixes. See
``design/plans/toolchains-as-dependencies.md``.
"""

from __future__ import print_function

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

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

METADATA_NAME = 'cuppa-toolchain.json'
FAMILY_CLANG = 'clang'
FAMILY_GCC = 'gcc'
CXX_NAMES = {
    FAMILY_CLANG: ( 'clang++', 'clang++.exe' ),
    FAMILY_GCC: ( 'g++', 'g++.exe' ),
}


def add_options( add_option ):
    add_option(
        '--toolchain-archive',
        dest='toolchain-archive',
        type='string',
        nargs=1,
        action='store',
        help="Public archive URL or local path to a Clang or GCC toolchain archive "
             "(e.g. a Clang GitHub Release tarball, or a Debian gcc-snapshot .deb). "
             "Family comes from 'clang'/'gcc' in the basename when present; otherwise "
             "cuppa probes archive contents (staging download if needed), then falls "
             "back to .deb→gcc / other→clang. Cached under downloads_root/toolchains/ "
             "and registered as clang{major}_{tag} or gcc{major}_{stem}.",
    )
    add_option(
        '--clang-root',
        dest='clang-root',
        type='string',
        nargs=1,
        action='store',
        help="Path to an existing Clang install prefix containing bin/clang++. "
             "Registers clang{major}_local_{hash} and persists a link under "
             "dependencies_root/toolchains/clang/ for later --toolchains= reuse.",
    )
    add_option(
        '--gcc-root',
        dest='gcc-root',
        type='string',
        nargs=1,
        action='store',
        help="Path to an existing GCC install prefix containing bin/g++. "
             "Registers gcc{major}_local_{hash} and persists a link under "
             "dependencies_root/toolchains/gcc/ for later --toolchains= reuse.",
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


def _family_token_index( asset, token ):
    """Index of ``token`` as a non-alnum-bounded name fragment, or None."""
    match = re.search(
            r'(?:^|[^a-z0-9]){}(?:[^a-z0-9]|$)'.format( re.escape( token ) ),
            asset,
    )
    return match.start() if match else None


def archive_family_from_name( spec ):
    """Return ``clang`` / ``gcc`` when the basename clearly names a family, else None."""
    asset = asset_name_from_spec( spec ).lower()
    clang_at = _family_token_index( asset, 'clang' )
    gcc_at = _family_token_index( asset, 'gcc' )
    if clang_at is None and gcc_at is None:
        return None
    if gcc_at is None or ( clang_at is not None and clang_at <= gcc_at ):
        return FAMILY_CLANG
    return FAMILY_GCC


def archive_family_from_extension( spec ):
    """Last-resort family: ``.deb`` → gcc, otherwise clang."""
    asset = asset_name_from_spec( spec ).lower()
    if asset.endswith( '.deb' ):
        return FAMILY_GCC
    return FAMILY_CLANG


def _family_from_member_names( names ):
    """Infer family from archive member paths that look like ``…/bin/clang++`` or ``…/bin/g++``."""
    clang_hit = False
    gcc_hit = False
    for name in names:
        base = os.path.basename( str( name ).rstrip( '/\\' ) ).lower()
        if base in ( 'clang++', 'clang++.exe' ):
            clang_hit = True
        elif base in ( 'g++', 'g++.exe' ):
            gcc_hit = True
    if clang_hit and not gcc_hit:
        return FAMILY_CLANG
    if gcc_hit and not clang_hit:
        return FAMILY_GCC
    if clang_hit and gcc_hit:
        logger.warn(
            "Archive lists both clang++ and g++; cannot infer family from contents alone"
        )
    return None


def probe_archive_family( archive_path ):
    """Inspect archive members (without a full toolchain extract) for clang++ / g++."""
    import tarfile
    import zipfile

    path = os.path.abspath( archive_path )
    lower = path.lower()
    if lower.endswith( '.deb' ):
        return _probe_deb_family( path )
    try:
        if tarfile.is_tarfile( path ):
            with tarfile.open( path ) as archive:
                return _family_from_member_names( archive.getnames() )
    except ( tarfile.TarError, IOError, OSError ) as error:
        logger.warn(
            "Could not list tar members in [{}]: {}".format( as_notice( path ), error )
        )
    try:
        if zipfile.is_zipfile( path ):
            with zipfile.ZipFile( path ) as archive:
                return _family_from_member_names( archive.namelist() )
    except ( zipfile.BadZipfile, IOError, OSError ) as error:
        logger.warn(
            "Could not list zip members in [{}]: {}".format( as_notice( path ), error )
        )
    return None


def _probe_deb_family( archive_path ):
    """List ``data.tar.*`` members via ``ar`` + ``tar -t`` (no full payload extract)."""
    _require_command( 'ar' )
    _require_command( 'tar' )
    staging = tempfile.mkdtemp( prefix='cuppa-deb-probe-' )
    try:
        if subprocess.call(
                [ 'ar', 'x', os.path.abspath( archive_path ) ], cwd=staging
        ) != 0:
            logger.warn(
                "ar failed while probing family for [{}]".format( as_notice( archive_path ) )
            )
            return None
        data_members = (
            glob.glob( os.path.join( staging, 'data.tar.*' ) )
            + glob.glob( os.path.join( staging, 'data.tar' ) )
        )
        if not data_members:
            return None
        try:
            listed = subprocess.check_output(
                    [ 'tar', '-tf', data_members[0] ],
                    stderr=subprocess.STDOUT,
            )
        except ( subprocess.CalledProcessError, OSError ) as error:
            logger.warn(
                "tar -tf failed while probing [{}]: {}".format(
                    as_notice( archive_path ), error
                )
            )
            return None
        if not isinstance( listed, str ):
            listed = listed.decode( 'utf-8', 'replace' )
        return _family_from_member_names( listed.splitlines() )
    finally:
        shutil.rmtree( staging, ignore_errors=True )


def resolve_archive_family( spec, archive_path=None ):
    """Name tokens, then archive contents, then extension.

    Use :func:`archive_family_from_name` alone when the path is not available yet.
    Pass ``archive_path`` (local file) so ambiguous basenames can be staged/probed.
    """
    named = archive_family_from_name( spec )
    if named:
        return named
    if archive_path and os.path.isfile( archive_path ):
        probed = probe_archive_family( archive_path )
        if probed:
            return probed
    return archive_family_from_extension( spec )


def archive_family( spec ):
    """Compatibility: name tokens then extension (no content probe)."""
    return resolve_archive_family( spec )


def qualifier_for_archive( spec ):
    tag = release_tag_from_url( spec ) if '://' in spec or spec.startswith( 'file:' ) else None
    if tag:
        return sanitise_token( tag )
    stem = asset_name_from_spec( spec )
    for suffix in ( '.tar.gz', '.tar.xz', '.tar.bz2', '.tgz', '.zip', '.deb' ):
        if stem.lower().endswith( suffix ):
            stem = stem[ : -len( suffix ) ]
            break
    return sanitise_token( stem )


def qualifier_for_root( root_path ):
    digest = hashlib.sha1( os.path.abspath( root_path ).encode( 'utf-8' ) ).hexdigest()[ : 8 ]
    return 'local_{}'.format( digest )


def toolchain_name( family, major, qualifier ):
    return '{}{}_{}'.format( family, int( major ), qualifier )


def find_bin_dir( root, family ):
    """Return the directory that contains the family driver under ``root``, or None."""
    names = CXX_NAMES.get( family )
    if not names:
        return None
    root = os.path.abspath( root )
    for name in names:
        direct = os.path.join( root, 'bin', name )
        if os.path.isfile( direct ):
            return os.path.join( root, 'bin' )
    for dirpath, _dirnames, filenames in os.walk( root ):
        if any( name in filenames for name in names ):
            return dirpath
    return None


def find_clang_bin_dir( root ):
    """Compatibility wrapper — prefer :func:`find_bin_dir`."""
    return find_bin_dir( root, FAMILY_CLANG )


def find_gcc_bin_dir( root ):
    return find_bin_dir( root, FAMILY_GCC )


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


def metadata_path( extract_root ):
    return os.path.join( extract_root, METADATA_NAME )


def read_registration( extract_root ):
    path = metadata_path( extract_root )
    if not os.path.isfile( path ):
        return None
    try:
        with open( path, 'r' ) as handle:
            return json.load( handle )
    except ( IOError, ValueError, TypeError ) as error:
        logger.warn(
            "Ignoring unreadable toolchain metadata [{}]: {}".format(
                as_notice( path ), error
            )
        )
        return None


def write_registration( extract_root, family, kind, prefix=None, source=None ):
    if not os.path.isdir( extract_root ):
        os.makedirs( extract_root )
    meta = {
        'family': family,
        'kind': kind,
    }
    if prefix:
        meta['prefix'] = os.path.abspath( prefix )
    if source:
        meta['source'] = source
    path = metadata_path( extract_root )
    with open( path, 'w' ) as handle:
        json.dump( meta, handle, indent=2, sort_keys=True )
        handle.write( '\n' )
    return meta


def is_external_registration( extract_root ):
    meta = read_registration( extract_root )
    return bool( meta and meta.get( 'kind' ) == 'external' )


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


def _require_command( name ):
    which = getattr( shutil, 'which', None )
    if which and which( name ):
        return
    raise ToolchainArchiveException(
        "cannot extract .deb toolchain archive: [{}] not found on PATH".format( name )
    )


def _extract_deb( archive_path, extract_root ):
    """Extract a Debian binary package into ``extract_root`` (data.tar payload)."""
    _require_command( 'ar' )
    _require_command( 'tar' )
    if os.path.isdir( extract_root ):
        shutil.rmtree( extract_root )
    os.makedirs( extract_root )
    staging = tempfile.mkdtemp( prefix='cuppa-deb-' )
    try:
        if subprocess.call( [ 'ar', 'x', os.path.abspath( archive_path ) ], cwd=staging ) != 0:
            raise ToolchainArchiveException(
                "ar failed to unpack [{}]".format( archive_path )
            )
        data_members = (
            glob.glob( os.path.join( staging, 'data.tar.*' ) )
            + glob.glob( os.path.join( staging, 'data.tar' ) )
        )
        if not data_members:
            raise ToolchainArchiveException(
                "[{}] has no data.tar.* member".format( archive_path )
            )
        data_tar = data_members[0]
        if subprocess.call(
                [ 'tar', '-xf', data_tar, '-C', extract_root ]
        ) != 0:
            raise ToolchainArchiveException(
                "tar failed to extract [{}] from [{}]".format( data_tar, archive_path )
            )
    finally:
        shutil.rmtree( staging, ignore_errors=True )


def _ensure_extracted( archive_path, extract_root, cuppa_env, family ):
    bin_dir = find_bin_dir( extract_root, family )
    if bin_dir:
        return bin_dir
    if os.path.isdir( extract_root ):
        shutil.rmtree( extract_root )
    if cuppa_env.get( 'dump' ) or cuppa_env.get( 'clean' ):
        return None
    if archive_path.lower().endswith( '.deb' ):
        _extract_deb( archive_path, extract_root )
    else:
        Location.extract( archive_path, extract_root )
    bin_dir = find_bin_dir( extract_root, family )
    if not bin_dir:
        driver = CXX_NAMES[family][0]
        raise ToolchainArchiveException(
            "extracted toolchain archive [{}] has no bin/{} under [{}]".format(
                archive_path, driver, extract_root
            )
        )
    return bin_dir


def prepare_from_archive( cuppa_env, spec ):
    downloads = cuppa_env['downloads_root']
    dependencies = cuppa_env['dependencies_root']
    qualifier = qualifier_for_archive( spec )
    asset = asset_name_from_spec( spec )
    named_family = archive_family_from_name( spec )

    if '://' in spec and not spec.startswith( 'file:' ):
        # Known family → final cache path. Ambiguous → download under _staging, then move.
        family_dir = named_family if named_family else '_staging'
        cache_dir = os.path.join( downloads, 'toolchains', family_dir, qualifier )
        archive_path = os.path.join( cache_dir, asset )
        _download_archive( spec, archive_path, cuppa_env )
    else:
        archive_path = _expand_local_path( spec, cuppa_env )
        if not os.path.isfile( archive_path ):
            raise ToolchainArchiveException(
                "toolchain archive path [{}] does not exist".format( archive_path )
            )

    family = resolve_archive_family( spec, archive_path=archive_path )
    if named_family is None and '://' in spec and not spec.startswith( 'file:' ):
        final_dir = os.path.join( downloads, 'toolchains', family, qualifier )
        final_path = os.path.join( final_dir, asset )
        if os.path.abspath( archive_path ) != os.path.abspath( final_path ):
            if not os.path.isdir( final_dir ):
                os.makedirs( final_dir )
            if os.path.isfile( final_path ):
                os.remove( final_path )
            shutil.move( archive_path, final_path )
            staging_parent = os.path.dirname( archive_path )
            try:
                if not os.listdir( staging_parent ):
                    os.rmdir( staging_parent )
            except OSError:
                pass
            archive_path = final_path

    extract_root = os.path.join( dependencies, 'toolchains', family, qualifier )
    bin_dir = _ensure_extracted( archive_path, extract_root, cuppa_env, family )
    if not bin_dir:
        return None
    write_registration(
            extract_root, family, 'archive', source=spec,
    )
    return {
        'family': family,
        'source': spec,
        'qualifier': qualifier,
        'bin_dir': bin_dir,
        'extract_root': extract_root,
        'kind': 'archive',
    }


def prepare_from_root( cuppa_env, root, family ):
    root_path = os.path.abspath( _expand_local_path( root, cuppa_env ) )
    bin_dir = find_bin_dir( root_path, family )
    if not bin_dir:
        names = CXX_NAMES[family]
        if any( os.path.isfile( os.path.join( root_path, name ) ) for name in names ):
            bin_dir = root_path
        else:
            raise ToolchainArchiveException(
                "{}-root [{}] does not contain bin/{}".format(
                    family, root_path, names[0]
                )
            )
    qualifier = qualifier_for_root( root_path )
    dependencies = cuppa_env['dependencies_root']
    extract_root = os.path.join( dependencies, 'toolchains', family, qualifier )
    write_registration(
            extract_root, family, 'external', prefix=root_path, source=root_path,
    )
    return {
        'family': family,
        'source': root_path,
        'qualifier': qualifier,
        'bin_dir': bin_dir,
        'extract_root': extract_root,
        'kind': 'external',
    }


def _entry_from_qualifier_dir( extract_root, family, qualifier ):
    meta = read_registration( extract_root )
    if meta and meta.get( 'kind' ) == 'external':
        prefix = meta.get( 'prefix' )
        if not prefix:
            return None
        bin_dir = find_bin_dir( prefix, family )
        if not bin_dir:
            names = CXX_NAMES[family]
            if any( os.path.isfile( os.path.join( prefix, name ) ) for name in names ):
                bin_dir = prefix
        if not bin_dir:
            logger.warn(
                "Skipping external toolchain [{}]; {} not found under [{}]".format(
                    as_notice( extract_root ),
                    CXX_NAMES[family][0],
                    as_notice( prefix ),
                )
            )
            return None
        return {
            'family': family,
            'source': prefix,
            'qualifier': qualifier,
            'bin_dir': bin_dir,
            'extract_root': extract_root,
            'kind': 'cached',
        }
    bin_dir = find_bin_dir( extract_root, family )
    if not bin_dir:
        return None
    return {
        'family': family,
        'source': extract_root,
        'qualifier': qualifier,
        'bin_dir': bin_dir,
        'extract_root': extract_root,
        'kind': 'cached',
    }


def discover_cached( cuppa_env, skip_keys=None, family=None ):
    """Find toolchain deps under ``dependencies_root/toolchains/{clang,gcc}/``.

    ``skip_keys`` is a set of ``(family, qualifier)`` pairs already prepared this session.
    """
    skip_keys = set( skip_keys or [] )
    dependencies = cuppa_env.get( 'dependencies_root' )
    if not dependencies:
        return []
    families = ( family, ) if family else ( FAMILY_CLANG, FAMILY_GCC )
    found = []
    for fam in families:
        base = os.path.join( dependencies, 'toolchains', fam )
        if not os.path.isdir( base ):
            continue
        for qualifier in sorted( os.listdir( base ) ):
            if ( fam, qualifier ) in skip_keys:
                continue
            extract_root = os.path.join( base, qualifier )
            if not os.path.isdir( extract_root ):
                continue
            entry = _entry_from_qualifier_dir( extract_root, fam, qualifier )
            if entry:
                found.append( entry )
    return found


def prepare( cuppa_env ):
    """Resolve archive / root options and discover cached toolchain deps."""
    prepared = []
    cuppa_env['toolchain_archive_names'] = []
    try:
        archive = cuppa_env.get_option( 'toolchain-archive' )
        clang_root = cuppa_env.get_option( 'clang-root' )
        gcc_root = cuppa_env.get_option( 'gcc-root' )
    except Exception:
        archive = None
        clang_root = None
        gcc_root = None

    if archive:
        entry = prepare_from_archive( cuppa_env, archive )
        if entry:
            prepared.append( entry )
    if clang_root:
        prepared.append( prepare_from_root( cuppa_env, clang_root, FAMILY_CLANG ) )
    if gcc_root:
        prepared.append( prepare_from_root( cuppa_env, gcc_root, FAMILY_GCC ) )

    skip = { ( entry['family'], entry['qualifier'] ) for entry in prepared }
    discovered = discover_cached( cuppa_env, skip_keys=skip )

    cuppa_env['prepared_toolchain_archives'] = prepared
    cuppa_env['discovered_toolchain_archives'] = discovered
    return prepared


class ToolchainArchive( object ):
    """Option registration only; prepare/register are invoked from Construct / toolchains."""

    @classmethod
    def add_options( cls, add_option ):
        add_options( add_option )

    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        return


def _cxx_path_for_entry( entry, family ):
    names = CXX_NAMES[family]
    for name in names:
        candidate = os.path.join( entry['bin_dir'], name )
        if os.path.isfile( candidate ):
            return candidate
    return os.path.join( entry['bin_dir'], names[0] )


def _attach_ownership( toolchain, entry ):
    toolchain._toolchain_dep_root = entry.get( 'extract_root' )


def _append_archive_names( cuppa_env, names ):
    existing = list( cuppa_env.get( 'toolchain_archive_names' ) or [] )
    for name in names:
        if name not in existing:
            existing.append( name )
    cuppa_env['toolchain_archive_names'] = existing


def _register_clang_entries(
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
        if entry.get( 'family', FAMILY_CLANG ) != FAMILY_CLANG:
            continue
        cxx = _cxx_path_for_entry( entry, FAMILY_CLANG )
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
        name = toolchain_name( FAMILY_CLANG, reported['major'], entry['qualifier'] )
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
        _attach_ownership( toolchain, entry )
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


def _register_gcc_entries(
        cuppa_env,
        entries,
        add_toolchain,
        add_to_supported,
        gcc_cls,
        skip_existing,
):
    names = []
    existing = cuppa_env.get( 'toolchains' ) or {}
    for entry in entries:
        if entry.get( 'family' ) != FAMILY_GCC:
            continue
        cxx = _cxx_path_for_entry( entry, FAMILY_GCC )
        reported = gcc_cls.version_from_command( cxx, 'gcc' )
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
        name = toolchain_name( FAMILY_GCC, reported['major'], entry['qualifier'] )
        if skip_existing and name in existing:
            logger.debug(
                "Skipping toolchain [{}]; already available".format( as_info( name ) )
            )
            continue
        reported = dict( reported )
        reported['name'] = name
        add_to_supported( name )
        toolchain = gcc_cls( name, '', reported, entry['bin_dir'] )
        _attach_ownership( toolchain, entry )
        add_toolchain( name, toolchain )
        existing[ name ] = toolchain
        names.append( name )
        logger.info(
            "Registered toolchain [{}] from [{}] at [{}] (gcc {})".format(
                as_info( name ),
                as_notice( entry['source'] ),
                as_notice( entry['bin_dir'] ),
                as_info( reported['version'] ),
            )
        )
    return names


def register_prepared( cuppa_env, add_toolchain, add_to_supported, clang_cls ):
    """Register explicit and cached Clang toolchain installs."""
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

    explicit_names = _register_clang_entries(
        cuppa_env, prepared, add_toolchain, add_to_supported, clang_cls,
        stdlib, suppress_debug_for_auto, skip_existing=False,
    )
    _register_clang_entries(
        cuppa_env, discovered, add_toolchain, add_to_supported, clang_cls,
        stdlib, suppress_debug_for_auto, skip_existing=True,
    )
    _append_archive_names( cuppa_env, explicit_names )
    return explicit_names


def register_prepared_gcc( cuppa_env, add_toolchain, add_to_supported, gcc_cls ):
    """Register explicit and cached GCC toolchain installs."""
    prepared = cuppa_env.get( 'prepared_toolchain_archives' ) or []
    discovered = cuppa_env.get( 'discovered_toolchain_archives' ) or []

    explicit_names = _register_gcc_entries(
        cuppa_env, prepared, add_toolchain, add_to_supported, gcc_cls,
        skip_existing=False,
    )
    _register_gcc_entries(
        cuppa_env, discovered, add_toolchain, add_to_supported, gcc_cls,
        skip_existing=True,
    )
    _append_archive_names( cuppa_env, explicit_names )
    return explicit_names


def remind_reuse_names( cuppa_env ):
    """Log shorthand ``--toolchains=`` names after a successful archive/root session."""
    names = cuppa_env.get( 'toolchain_archive_names' ) or []
    if not names:
        return
    for name in names:
        logger.info(
            "Reuse this toolchain next time with [{}]".format(
                as_info( "--toolchains={}".format( name ) )
            )
        )


def install_reuse_reminder( cuppa_env ):
    """Register a progress callback that prints reuse hints at sconstruct end."""
    names = cuppa_env.get( 'toolchain_archive_names' ) or []
    if not names:
        return

    from cuppa.progress import NotifyProgress

    def _on_progress( event, sconscript, variant, env, target, source ):
        if event == 'sconstruct_end':
            remind_reuse_names( cuppa_env )

    NotifyProgress.register_callback( None, _on_progress )
