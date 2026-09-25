#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   cuppa-publish.json — rebuild / cascade metadata
#-------------------------------------------------------------------------------

"""Read/write ``cuppa-publish.json`` staged beside package include/lib.

See ``design/plans/package-build-publish-deps.md``. This is the single traveling
package SoT (identity, dependency edges including ``package_source``,
optional ``default_use_libs`` / ``link``, and optional ``payload_sha256`` for
tip consume refresh). Legacy ``cuppa-dependency.json`` is read only as a
fallback for extracts published before Phase 2d.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from cuppa.package_managers.cuppa_dependency_manifest import (
        MANIFEST_FILENAME as LEGACY_DEPENDENCY_FILENAME,
        fill_dependency_versions,
        normalise_dependency_entry,
        read_manifest as read_legacy_dependency_manifest,
        _normalise_default_use_libs,
        _normalise_link,
)


PUBLISH_FILENAME = "cuppa-publish.json"
PUBLISH_FORMAT = 1
PAYLOAD_SHA256_KEY = "payload_sha256"

# Root-level traveling metadata — excluded from payload digests.
_TRAVELING_METADATA_NAMES = frozenset( {
        PUBLISH_FILENAME,
        LEGACY_DEPENDENCY_FILENAME,
} )


def publish_manifest_path( package_dir: str ) -> str:
    return os.path.join( package_dir, PUBLISH_FILENAME )


def compute_payload_sha256( package_dir: str ) -> str | None:
    """Stable SHA-256 of non-metadata files under ``package_dir``.

    Returns ``None`` when there is no staged payload (no ``include/`` or
    ``lib/``), so publisher-tree seeds omit the field. Traveling JSON at the
    package root is excluded so metadata-only amends keep the same digest.
    """
    from cuppa.package_managers.package_amend import package_stage_has_payload

    if not package_dir or not package_stage_has_payload( package_dir ):
        return None
    digest = hashlib.sha256()
    file_count = 0
    for dirpath, dirnames, filenames in os.walk( package_dir ):
        dirnames.sort()
        for filename in sorted( filenames ):
            full = os.path.join( dirpath, filename )
            rel = os.path.relpath( full, package_dir ).replace( os.sep, "/" )
            if "/" not in rel and filename in _TRAVELING_METADATA_NAMES:
                continue
            if not os.path.isfile( full ):
                continue
            digest.update( rel.encode( "utf-8" ) )
            digest.update( b"\0" )
            try:
                with open( full, "rb" ) as handle:
                    for chunk in iter( lambda: handle.read( 1024 * 1024 ), b"" ):
                        digest.update( chunk )
            except OSError:
                continue
            digest.update( b"\0" )
            file_count += 1
    if file_count == 0:
        # Empty include/lib trees still count as a known empty payload.
        digest.update( b"empty-payload\0" )
    return digest.hexdigest()


def build_publish_document(
        package: str,
        version: Any,
        dependencies: list | None = None,
        default_use_libs: Any = None,
        link: Any = None,
        payload_sha256: str | None = None,
) -> dict:
    """Return a publish document (always includes package identity)."""
    entries = []
    if dependencies:
        entries = [
                normalise_dependency_entry( item, include_package_source=True )
                for item in dependencies
        ]
    document: dict = {
        "cuppa_publish_format": PUBLISH_FORMAT,
        "package": str( package ),
        "version": str( version ),
        "dependencies": entries,
    }
    defaults = _normalise_default_use_libs( default_use_libs )
    link_mode = _normalise_link( link )
    if defaults is not None:
        document["default_use_libs"] = defaults
    if link_mode is not None:
        document["link"] = link_mode
    if payload_sha256:
        document[PAYLOAD_SHA256_KEY] = str( payload_sha256 )
    return document


def _publish_documents_equal( left: dict, right: dict ) -> bool:
    """True when two publish documents are semantically equal.

    Key order and whitespace do not matter — cascade must not rewrite a tracked
    ``cuppa-publish.json`` solely because ``json.dumps(sort_keys=True)`` differs
    from the author's insertion order.
    """
    return left == right


def write_publish_manifest(
        package_dir: str,
        package: str,
        version: Any,
        dependencies: list | None = None,
        env=None,
        default_use_libs: Any = None,
        link: Any = None,
        payload_sha256: str | None = None,
) -> str:
    """Write ``cuppa-publish.json`` under ``package_dir``. Returns the path.

    Skips rewriting when the on-disk document already matches semantically, so
    archive freshness checks and publisher-tree git status are not spuriously
    invalidated by key-order-only differences.

    When ``payload_sha256`` is omitted, computes it from staged ``include/`` /
    ``lib/`` under ``package_dir`` (publisher seeds without payload omit the
    field).
    """
    if env is not None:
        dependencies = fill_dependency_versions( env, dependencies )
    if payload_sha256 is None:
        payload_sha256 = compute_payload_sha256( package_dir )
    document = build_publish_document(
            package,
            version,
            dependencies=dependencies,
            default_use_libs=default_use_libs,
            link=link,
            payload_sha256=payload_sha256,
    )
    path = publish_manifest_path( package_dir )
    os.makedirs( package_dir, exist_ok=True )
    if os.path.isfile( path ):
        try:
            with open( path, encoding="utf-8" ) as handle:
                existing = json.load( handle )
            if isinstance( existing, dict ) and _publish_documents_equal(
                    existing, document
            ):
                return path
        except ( OSError, ValueError, TypeError, json.JSONDecodeError ):
            pass
    # Insertion order from build_publish_document (not sort_keys) so new seeds
    # match the usual authored shape: package / version / dependencies first.
    payload = json.dumps( document, indent=2 ) + "\n"
    with open( path, "w", encoding="utf-8" ) as handle:
        handle.write( payload )
    return path


def read_publish_manifest( package_dir: str ) -> dict | None:
    """Load ``cuppa-publish.json`` from ``package_dir``, or ``None`` if absent."""
    path = publish_manifest_path( package_dir )
    if not os.path.isfile( path ):
        return None
    with open( path, encoding="utf-8" ) as handle:
        document = json.load( handle )
    if not isinstance( document, dict ):
        raise ValueError( "{}: expected a JSON object".format( path ) )
    format_version = document.get( "cuppa_publish_format" )
    if format_version not in ( None, PUBLISH_FORMAT, 1 ):
        raise ValueError(
            "{}: unsupported cuppa_publish_format [{}]".format( path, format_version )
        )
    if not document.get( "package" ) or document.get( "version" ) is None:
        raise ValueError( "{}: requires 'package' and 'version'".format( path ) )
    deps = document.get( "dependencies" ) or []
    document["dependencies"] = [
            normalise_dependency_entry( item, include_package_source=True )
            for item in deps
    ]
    document["cuppa_publish_format"] = format_version or PUBLISH_FORMAT
    document["package"] = str( document["package"] )
    document["version"] = str( document["version"] )
    defaults = _normalise_default_use_libs( document.get( "default_use_libs" ) )
    link_mode = _normalise_link( document.get( "link" ) )
    if defaults is not None:
        document["default_use_libs"] = defaults
    if link_mode is not None:
        document["link"] = link_mode
    payload_hash = document.get( PAYLOAD_SHA256_KEY )
    if payload_hash:
        document[PAYLOAD_SHA256_KEY] = str( payload_hash )
    elif PAYLOAD_SHA256_KEY in document:
        del document[PAYLOAD_SHA256_KEY]
    return document


def read_traveling_manifest( package_dir: str ) -> dict | None:
    """Load the traveling package document: publish first, else legacy dependency.

    Prefer ``cuppa-publish.json``. Fall back to ``cuppa-dependency.json`` only for
    extracts that predate Phase 2d. When both exist, publish wins.
    """
    document = read_publish_manifest( package_dir )
    if document is not None:
        return document
    return read_legacy_dependency_manifest( package_dir )


def remove_legacy_dependency_manifest( package_dir: str ) -> bool:
    """Delete ``cuppa-dependency.json`` under ``package_dir`` if present.

    Returns True when a file was removed. New archives must not keep the twin.
    """
    from cuppa.package_managers.cuppa_dependency_manifest import manifest_path

    path = manifest_path( package_dir )
    if not os.path.isfile( path ):
        return False
    os.remove( path )
    return True


def package_default_use_libs( package_dir: str ) -> list[str] | None:
    """Return ``default_use_libs`` from the traveling manifest, or ``None``."""
    document = read_traveling_manifest( package_dir )
    if not document:
        return None
    if "default_use_libs" not in document:
        return None
    return list( document.get( "default_use_libs" ) or [] )


def package_link_mode( package_dir: str ) -> str | None:
    """Return the package ``link`` preference from the traveling manifest, if any."""
    document = read_traveling_manifest( package_dir )
    if not document:
        return None
    return document.get( "link" )
