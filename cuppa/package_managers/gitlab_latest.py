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
Online consume: a failed check (DNS, connection, HTTP 401/403/5xx) with a
remembered pin whose extract is on disk warns and reuses that pin. The pin
is not updated. 404, a missing extract, and publish stay hard stops.
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

from cuppa.colourise import as_info, as_notice, as_warning, colouriser
from cuppa.configure import global_config_path, read_setting, upsert_setting
from cuppa.log import logger
from cuppa.package_managers.gitlab import registry_auth_headers


class GitlabLatestError( Exception ):
    """Configure-time failure resolving registry latest."""

    def __init__( self, message, status=None, reason=None ):
        Exception.__init__( self, message )
        self.parameter = message
        self.status = status
        self.reason = reason


class GitlabLatestNetworkError( GitlabLatestError ):
    """Registry list failed because the network was unreachable."""
    pass


def registry_failure_is_unverified( error ):
    """True when the list did not run, as opposed to a definite registry answer.

    401 and 403 are an expired or under-scoped token. 5xx and a connection
    failure are the host. 404 is a real answer (wrong project or package name)
    and is not unverified.
    """
    if isinstance( error, GitlabLatestNetworkError ):
        return True
    status = getattr( error, "status", None )
    try:
        status = int( status )
    except ( TypeError, ValueError ):
        return False
    if status in ( 401, 403 ):
        return True
    return status >= 500


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
            status = getattr( error, 'code', None )
            reason = getattr( error, 'msg', None ) or getattr( error, 'reason', None )
            raise GitlabLatestError(
                    "GitLab Packages API failed for [{}] (HTTP {}): {}".format(
                            package_name,
                            status if status is not None else '?',
                            error,
                    ),
                    status=status,
                    reason=reason,
            )
        except URLError as error:
            raise GitlabLatestNetworkError(
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


def package_pin_tree_exists( env, package, version ):
    """True when an extract of this pin exists under the dependencies root.

    Extracts are ``<dependencies>/<toolchain_variant>/<package>/<version>``.
    Latest is often resolved before a variant env exists, so any toolchain's
    non-empty extract of that pin counts. A conf pin whose directory was
    removed does not.
    """
    root = None
    if hasattr( env, "get" ):
        root = env.get( "dependencies_root" )
    if not root or not package or not version:
        return False
    root = os.path.abspath( str( root ) )
    if not os.path.isdir( root ):
        return False
    package = str( package )
    version = str( version )
    downloads = env.get( "downloads_root" )
    downloads = os.path.abspath( str( downloads ) ) if downloads else None
    try:
        names = os.listdir( root )
    except OSError:
        return False
    for name in names:
        if name in ( "packages", ".", ".." ):
            continue
        candidate = os.path.join( root, name, package, version )
        if not os.path.isdir( candidate ):
            continue
        if downloads and _path_within( candidate, downloads ):
            continue
        try:
            if os.listdir( candidate ):
                return True
        except OSError:
            continue
    return False


def _path_within( path, root ):
    try:
        return os.path.commonpath( [ os.path.abspath( path ), root ] ) == root
    except ValueError:
        return False


def _unverified_detail( error ):
    status = getattr( error, "status", None )
    if not status:
        return "registry unreachable"
    reason = getattr( error, "reason", None )
    if reason is not None:
        text = str( reason ).strip().lower()
        if text and not text.isdigit():
            return "HTTP {} - {}".format( status, text )
    return "HTTP {}".format( status )


def _unverified_label():
    """``unverified`` on the warning background, in the terminal's own ink.

    Not a bold chip: no bright style, and no forced white foreground.
    """
    text = "unverified"
    if not colouriser.use_colour:
        return text
    import colorama
    return colorama.Back.MAGENTA + text + colorama.Style.RESET_ALL


def reuse_unverified_pin( env, token, package, stored, error ):
    """Warn and reuse ``stored``. Does not write a new pin.

    ``--terse-output`` already prints a durable ``[version]`` row. The logger
    warning is the normal-output form of that same decision, not a second note.
    """
    detail = _unverified_detail( error )
    if not _terse_version_row(
            env, token, "",
            status="warn",
            fields=(
                    _unverified_label(),
                    as_warning( "using remembered {}".format( stored ) ),
            ),
    ):
        logger.warn(
                "Asked for latest version for [{}] but the registry was not verified: "
                "error was [{}]. This build is using the remembered version [{}], "
                "which might not be the latest.".format(
                        as_warning( str( token ) ),
                        as_warning( detail ),
                        as_warning( str( stored ) ),
                )
        )
    return str( stored )


def _terse_version_row( env, token, remark, status="ok", fields=() ):
    """``→ [version]  <boost_package> · latest · retrieved as 1.92``."""
    if not token:
        return False
    import cuppa.progress
    return cuppa.progress.write_terse_resolve_child(
            env, "version", token, "latest", *fields,
            status=status, remark=remark,
    )


def resolve_latest_package_version(
        env, registry, package, custom_token=None, opener=None,
        allow_remembered_on_network_error=True, dependency_name=None,
):
    """Resolve registry latest for ``package``; remember on success; offline uses cache.

    Raises :class:`GitlabLatestError` when no version can be chosen. A failed
    check (DNS, connection, HTTP 401/403/5xx) warns and reuses a remembered pin
    when that pin's extract is on disk, unless
    ``allow_remembered_on_network_error`` is false (publish). The pin is not
    updated. HTTP 404 stays a hard error.
    """
    token = dependency_name or package
    offline = bool( env[ 'offline' ] ) if hasattr( env, '__contains__' ) and 'offline' in env else False
    if not offline and hasattr( env, 'get' ):
        offline = bool( env.get( 'offline' ) )

    if offline:
        stored = stored_registry_latest( env, registry, package )
        if stored:
            if not _terse_version_row(
                    env, token, "using remembered {}".format( stored ),
            ):
                logger.info(
                        "Offline: using remembered registry latest [{}] for package [{}]".format(
                                as_info( str( stored ) ),
                                as_info( str( package ) ),
                        )
                )
            return str( stored )
        _terse_version_row(
                env, token, "error: retrieve failed, no version available",
                status="error",
        )
        raise GitlabLatestError(
                "Offline and no remembered registry latest for package [{}] "
                "(registry [{}])".format( package, registry )
        )

    try:
        versions = list_generic_package_versions(
                registry, package, custom_token=custom_token, opener=opener
        )
    except GitlabLatestError as error:
        stored = stored_registry_latest( env, registry, package )
        if (
                allow_remembered_on_network_error
                and registry_failure_is_unverified( error )
                and stored
                and package_pin_tree_exists( env, package, stored )
        ):
            return reuse_unverified_pin( env, token, package, stored, error )
        _terse_version_row(
                env, token, "error: retrieve failed, no version available",
                status="error",
        )
        raise

    latest = select_latest_version( versions )
    if not latest:
        _terse_version_row(
                env, token, "error: retrieve failed, no version available",
                status="error",
        )
        raise GitlabLatestError(
                "No versions found in GitLab registry for package [{}] "
                "(registry [{}])".format( package, registry )
        )

    if not _terse_version_row(
            env, token, "retrieved as {}".format( latest ),
    ):
        logger.info(
                "Resolved registry latest for package [{}] to [{}]".format(
                        as_info( str( package ) ),
                        as_info( str( latest ) ),
                )
        )
    remember_registry_latest( env, registry, package, latest )
    return latest
