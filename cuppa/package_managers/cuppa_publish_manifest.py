#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   cuppa-publish.json — rebuild / cascade metadata
#-------------------------------------------------------------------------------

"""Read/write ``cuppa-publish.json`` staged beside package include/lib.

See ``design/plans/package-build-publish-deps.md``. Consume continues to use
``cuppa-dependency.json``; this file carries the same edges plus
``package_source`` for cascade discovery.
"""

from __future__ import annotations

import json
import os
from typing import Any

from cuppa.package_managers.cuppa_dependency_manifest import (
        fill_dependency_versions,
        normalise_dependency_entry,
        _normalise_default_use_libs,
        _normalise_link,
)


PUBLISH_FILENAME = "cuppa-publish.json"
PUBLISH_FORMAT = 1


def publish_manifest_path( package_dir: str ) -> str:
    return os.path.join( package_dir, PUBLISH_FILENAME )


def build_publish_document(
        package: str,
        version: Any,
        dependencies: list | None = None,
        default_use_libs: Any = None,
        link: Any = None,
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
    return document


def write_publish_manifest(
        package_dir: str,
        package: str,
        version: Any,
        dependencies: list | None = None,
        env=None,
        default_use_libs: Any = None,
        link: Any = None,
) -> str:
    """Write ``cuppa-publish.json`` under ``package_dir``. Returns the path.

    Skips rewriting when the on-disk document already matches, so archive
    freshness checks are not spuriously invalidated.
    """
    if env is not None:
        dependencies = fill_dependency_versions( env, dependencies )
    document = build_publish_document(
            package,
            version,
            dependencies=dependencies,
            default_use_libs=default_use_libs,
            link=link,
    )
    path = publish_manifest_path( package_dir )
    os.makedirs( package_dir, exist_ok=True )
    payload = json.dumps( document, indent=2, sort_keys=True ) + "\n"
    if os.path.isfile( path ):
        with open( path, encoding="utf-8" ) as handle:
            if handle.read() == payload:
                return path
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
    return document
