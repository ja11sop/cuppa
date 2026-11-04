#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   GitLab package archive freshness (online HEAD + sidecar)
#-------------------------------------------------------------------------------

"""Conditional freshness for cached GitLab generic package archives.

Online consume HEADs the package file URL before reusing a cached archive.
Identity is stored beside the archive after a successful download. See
``design/plans/package-download-freshness.md``.
"""

from __future__ import annotations

import os

MATCH = "match"
STALE = "stale"
UNVERIFIED = "unverified"

SIDECAR_SUFFIX = ".cuppa-freshness"


def archive_freshness_sidecar_path( archive_path ):
    """Path of the freshness sidecar next to ``archive_path``."""
    return str( archive_path ) + SIDECAR_SUFFIX


def identity_from_headers( headers ):
    """Build a comparable identity string from HEAD/GET response headers.

    Prefers GitLab ``X-Checksum-Sha256``. Falls back to
    ``Last-Modified`` + ``Content-Length``. Returns ``None`` when neither is
    usable.
    """
    mapping = headers or {}
    checksum = mapping.get( "x-checksum-sha256" )
    if checksum:
        text = str( checksum ).strip().lower()
        if text:
            return "sha256:{}".format( text )
    last_modified = str( mapping.get( "last-modified" ) or "" ).strip()
    content_length = str( mapping.get( "content-length" ) or "" ).strip()
    if last_modified or content_length:
        return "meta:{}|{}".format( last_modified, content_length )
    return None


def read_archive_freshness( archive_path ):
    """Return the stored identity string, or ``None`` if missing/blank."""
    sidecar = archive_freshness_sidecar_path( archive_path )
    if not os.path.isfile( sidecar ):
        return None
    try:
        with open( sidecar, "r", encoding="utf-8" ) as handle:
            text = handle.read().strip()
    except OSError:
        return None
    return text or None


def write_archive_freshness( archive_path, identity ):
    """Write ``identity`` beside ``archive_path``. No-op when identity is empty."""
    text = str( identity or "" ).strip()
    if not text:
        return False
    sidecar = archive_freshness_sidecar_path( archive_path )
    parent = os.path.dirname( sidecar )
    if parent and not os.path.isdir( parent ):
        os.makedirs( parent )
    with open( sidecar, "w", encoding="utf-8" ) as handle:
        handle.write( text )
        handle.write( "\n" )
    return True


def remove_archive_freshness( archive_path ):
    """Delete the sidecar if present."""
    sidecar = archive_freshness_sidecar_path( archive_path )
    if os.path.isfile( sidecar ):
        try:
            os.remove( sidecar )
        except OSError:
            pass


def url_for_cached_archive( candidates, archive_path ):
    """Return the registry URL for ``archive_path`` from consume candidates.

    ``candidates`` is a sequence of ``(stem, filename, url, token)``.
    """
    name = os.path.basename( str( archive_path or "" ) )
    if not name:
        return None
    for item in candidates or ():
        if len( item ) < 3:
            continue
        filename = item[1]
        url = item[2]
        if filename == name and url:
            return url
    return None


def check_cached_archive_freshness(
        url,
        archive_path,
        custom_token=None,
        head=None,
        auth_headers=None,
):
    """Compare the cached archive to a registry HEAD.

    Returns ``(outcome, identity, detail)`` where ``outcome`` is
    ``match``, ``stale``, or ``unverified``. ``identity`` is the remote
    identity when HEAD succeeded with usable headers. ``detail`` is a short
    reason for ``unverified`` / logging.
    """
    from cuppa.utility.download import DownloadError, http_head

    if head is None:
        head = http_head
    if auth_headers is None:
        from cuppa.package_managers.gitlab import registry_auth_headers
        auth_headers = registry_auth_headers( custom_token )

    stored = read_archive_freshness( archive_path )
    try:
        status, headers = head( url, headers=auth_headers or None )
    except DownloadError as error:
        return UNVERIFIED, None, str( getattr( error, "parameter", error ) )
    except Exception as error:
        return UNVERIFIED, None, str( error )

    status = int( status or 0 )
    if status == 404:
        return STALE, None, "HTTP 404"
    if status < 200 or status >= 400:
        return UNVERIFIED, None, "HTTP {}".format( status )

    identity = identity_from_headers( headers )
    if identity is None:
        return UNVERIFIED, None, "no freshness headers"

    if stored is None:
        # First online check after this feature (or purged sidecar): establish
        # currency by re-fetching once.
        return STALE, identity, "missing sidecar"

    if stored == identity:
        return MATCH, identity, None
    return STALE, identity, "identity changed"


def record_archive_freshness_from_head(
        url,
        archive_path,
        custom_token=None,
        head=None,
        auth_headers=None,
):
    """HEAD ``url`` and write the sidecar for ``archive_path``. Returns identity or None."""
    from cuppa.utility.download import DownloadError, http_head

    if head is None:
        head = http_head
    if auth_headers is None:
        from cuppa.package_managers.gitlab import registry_auth_headers
        auth_headers = registry_auth_headers( custom_token )
    try:
        status, headers = head( url, headers=auth_headers or None )
    except ( DownloadError, Exception ):
        return None
    if int( status or 0 ) < 200 or int( status or 0 ) >= 400:
        return None
    identity = identity_from_headers( headers )
    if not identity:
        return None
    write_archive_freshness( archive_path, identity )
    return identity
