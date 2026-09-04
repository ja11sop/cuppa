#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   GitLab registry package latest (list / select / remember)
#-------------------------------------------------------------------------------

"""Resolve ``version="latest"`` for GitLab generic packages from the Packages API.

``"latest"`` means newest version **published in that registry** for the package name,
not the newest upstream software release.

Remembered offline pin: after a successful list/select, store the concrete version string
under ``gitlab_package_latest_*`` (key suffix hashes ``registry|package``). Conf path
follows downloads-root scoping — project ``configure.conf`` when downloads live under the
project, else ``~/.cuppaconfig`` — same model as source Boost ``boost_latest_version``.
Offline replays that pin; missing archive fails (no silent older fallback).
"""

from __future__ import print_function

import hashlib
import json
import os
import re

try:
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:  # pragma: no cover - Python 2
    from urllib import urlencode
    from urllib2 import Request, urlopen, HTTPError, URLError

from cuppa.colourise import as_info, as_notice
from cuppa.configure import global_config_path, read_setting, upsert_setting
from cuppa.log import logger
from cuppa.package_managers.gitlab import registry_auth_headers


class GitlabLatestError( Exception ):
    """Configure-time failure resolving registry latest."""

    def __init__( self, message ):
        Exception.__init__( self, message )
        self.parameter = message


def package_version_sort_key( version ):
    """Comparable tuple for dotted / underscored package version strings."""
    if version is None:
        return ()
    text = str( version ).strip().replace( '_', '.' )
    parts = []
    for piece in text.split( '.' ):
        if piece.isdigit():
            parts.append( int( piece ) )
            continue
        match = re.match( r'(\d+)(.*)$', piece )
        if match:
            parts.append( int( match.group( 1 ) ) )
            suffix = match.group( 2 )
            if suffix:
                parts.append( suffix )
        else:
            parts.append( piece )
    return tuple( parts )


def project_packages_api_base( registry ):
    """Turn a Cuppa registry URL into ``…/api/v4/projects/…/packages``.

    Accepts either the project API root (``…/projects/ID``) or a generic-packages
    root that already ends with ``/packages/generic``.
    """
    text = str( registry ).rstrip( '/' )
    for suffix in ( '/packages/generic', '/packages' ):
        if text.endswith( suffix ):
            text = text[ : -len( suffix ) ]
            break
    if not text:
        raise GitlabLatestError( "Empty GitLab registry URL" )
    return text + '/packages'


def registry_latest_conf_key( registry, package ):
    """Stable conf key for remembered registry latest (not ``boost_latest_version``)."""
    digest = hashlib.sha256(
            "{}|{}".format( str( registry ).rstrip( '/' ), str( package ) ).encode( 'utf-8' )
    ).hexdigest()[ : 16 ]
    return 'gitlab_package_latest_' + digest


def registry_latest_conf_path( env ):
    """Project ``configure.conf`` when downloads_root is under the project; else ``~/.cuppaconfig``."""
    try:
        from cuppa.utility import storage as storage_util
    except Exception:
        storage_util = None

    downloads_root = None
    if hasattr( env, 'get' ):
        downloads_root = env.get( 'downloads_root' )
    if downloads_root is None:
        try:
            downloads_root = env[ 'downloads_root' ]
        except Exception:
            downloads_root = None

    sconstruct_dir = None
    for key in ( 'abs_sconstruct_dir', 'sconstruct_dir' ):
        try:
            sconstruct_dir = env[ key ] if key in env else None
        except Exception:
            sconstruct_dir = None
        if sconstruct_dir:
            break

    project_conf = None
    try:
        project_conf = env.get_option( 'use_conf' ) if hasattr( env, 'get_option' ) else None
    except Exception:
        project_conf = None
    if not project_conf:
        project_conf = 'configure.conf'
    if sconstruct_dir and not os.path.isabs( project_conf ):
        project_conf = os.path.join( os.path.abspath( sconstruct_dir ), project_conf )

    if (
            storage_util
            and downloads_root
            and sconstruct_dir
            and storage_util.is_contained(
                    os.path.abspath( downloads_root ),
                    os.path.abspath( sconstruct_dir ),
            )
    ):
        return project_conf

    return global_config_path()


def stored_registry_latest( env, registry, package ):
    return read_setting(
            registry_latest_conf_path( env ),
            registry_latest_conf_key( registry, package ),
    )


def remember_registry_latest( env, registry, package, version ):
    if not version:
        return
    conf_path = registry_latest_conf_path( env )
    key = registry_latest_conf_key( registry, package )
    # Quote so configure.conf literal_eval keeps ``1.10`` as a string (not float 1.1).
    upsert_setting( conf_path, key, repr( str( version ) ) )
    logger.info(
            "Stored {} = [{}] in [{}]".format(
                    as_notice( key ),
                    as_info( str( version ) ),
                    as_info( conf_path ),
            )
    )
    try:
        options = env[ 'configured_options' ]
        if isinstance( options, dict ):
            options[ key ] = str( version )
    except Exception:
        pass


def select_latest_version( versions ):
    """Return the newest version string from ``versions``, or ``None`` if empty."""
    concrete = [ v for v in versions if v ]
    if not concrete:
        return None
    return max( concrete, key=package_version_sort_key )


def _open_json( url, headers ):
    request = Request( url )
    for name, value in ( headers or {} ).items():
        if name is None or value is None:
            continue
        request.add_header( str( name ), str( value ) )
    response = urlopen( request )
    try:
        body = response.read()
    finally:
        try:
            response.close()
        except Exception:
            pass
    if isinstance( body, bytes ):
        body = body.decode( 'utf-8' )
    return json.loads( body )


def list_generic_package_versions( registry, package_name, custom_token=None, opener=None ):
    """List version strings for a GitLab generic package (exact name match).

    Uses ``GET …/packages?package_type=generic&package_name=…`` with pagination.
    ``opener`` is an optional ``(url, headers) -> list|dict`` for tests.
    """
    base = project_packages_api_base( registry )
    headers = registry_auth_headers( custom_token )
    fetch = opener or _open_json
    versions = []
    page = 1
    per_page = 100
    max_pages = 100

    while page <= max_pages:
        query = urlencode( {
                'package_type': 'generic',
                'package_name': str( package_name ),
                'order_by': 'version',
                'sort': 'desc',
                'per_page': per_page,
                'page': page,
        } )
        url = '{}?{}'.format( base, query )
        try:
            payload = fetch( url, headers )
        except HTTPError as error:
            raise GitlabLatestError(
                    "GitLab Packages API failed for [{}] (HTTP {}): {}".format(
                            package_name,
                            getattr( error, 'code', '?' ),
                            error,
                    )
            )
        except URLError as error:
            raise GitlabLatestError(
                    "GitLab Packages API failed for [{}]: {}".format( package_name, error )
            )
        except ( TypeError, ValueError ) as error:
            raise GitlabLatestError(
                    "GitLab Packages API returned invalid JSON for [{}]: {}".format(
                            package_name, error
                    )
            )

        if not isinstance( payload, list ):
            raise GitlabLatestError(
                    "GitLab Packages API returned unexpected payload for [{}]".format(
                            package_name
                    )
            )
        if not payload:
            break

        for item in payload:
            if not isinstance( item, dict ):
                continue
            if item.get( 'name' ) != package_name:
                continue
            version = item.get( 'version' )
            if version:
                versions.append( str( version ) )

        if len( payload ) < per_page:
            break
        page += 1
    else:
        raise GitlabLatestError(
                "GitLab Packages API pagination exceeded {} pages for [{}]".format(
                        max_pages, package_name
                )
        )

    return versions


def resolve_latest_package_version( env, registry, package, custom_token=None, opener=None ):
    """Resolve registry latest for ``package``; remember on success; offline uses cache.

    Raises :class:`GitlabLatestError` when no version can be chosen.
    """
    offline = bool( env[ 'offline' ] ) if hasattr( env, '__contains__' ) and 'offline' in env else False
    if not offline and hasattr( env, 'get' ):
        offline = bool( env.get( 'offline' ) )

    if offline:
        stored = stored_registry_latest( env, registry, package )
        if stored:
            logger.info(
                    "Offline: using remembered registry latest [{}] for package [{}]".format(
                            as_info( str( stored ) ),
                            as_info( str( package ) ),
                    )
            )
            return str( stored )
        raise GitlabLatestError(
                "Offline and no remembered registry latest for package [{}] "
                "(registry [{}])".format( package, registry )
        )

    versions = list_generic_package_versions(
            registry, package, custom_token=custom_token, opener=opener
    )
    latest = select_latest_version( versions )
    if not latest:
        raise GitlabLatestError(
                "No versions found in GitLab registry for package [{}] "
                "(registry [{}])".format( package, registry )
        )

    logger.info(
            "Resolved registry latest for package [{}] to [{}]".format(
                    as_info( str( package ) ),
                    as_info( str( latest ) ),
            )
    )
    remember_registry_latest( env, registry, package, latest )
    return latest
