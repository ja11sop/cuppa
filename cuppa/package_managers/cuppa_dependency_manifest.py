#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Read/write ``cuppa-dependency.json`` for transitive Cuppa package edges.

See ``design/plans/gitlab-package-transitive.md``.
"""

from __future__ import annotations

import json
import os
from typing import Any


MANIFEST_FILENAME = "cuppa-dependency.json"
MANIFEST_FORMAT = 1


def manifest_path( package_dir: str ) -> str:
    return os.path.join( package_dir, MANIFEST_FILENAME )


def normalise_dependency_entry( entry: Any ) -> dict:
    """Accept a dict or an object with ``name()`` / attributes; return a manifest dict."""
    if isinstance( entry, dict ):
        name = entry.get( "name" )
        if not name:
            raise ValueError( "dependency entry missing 'name'" )
        out = {
            "name": str( name ),
            "package": str( entry.get( "package" ) or name ),
            "version": str( entry["version"] ) if entry.get( "version" ) is not None else None,
            "registry": entry.get( "registry", "same" ),
        }
        use_libs = entry.get( "use_libs" )
        if use_libs:
            out["use_libs"] = [ str( item ) for item in use_libs ]
        if out["version"] is None:
            raise ValueError(
                "dependency [{}] requires a concrete 'version' (MVP)".format( out["name"] )
            )
        return out

    name_fn = getattr( entry, "name", None )
    name = name_fn() if callable( name_fn ) else getattr( entry, "name", None )
    if not name:
        raise ValueError( "dependency entry has no usable name()" )
    package = getattr( entry, "package", None ) or getattr( entry, "_package", None ) or name
    version = getattr( entry, "version", None ) or getattr( entry, "_version", None )
    if callable( version ):
        version = version()
    registry = getattr( entry, "registry", None ) or getattr( entry, "_registry", None ) or "same"
    use_libs = getattr( entry, "use_libs", None )
    if callable( use_libs ) and not isinstance( use_libs, ( list, tuple ) ):
        use_libs = None
    normalised = {
        "name": str( name ),
        "package": str( package ),
        "version": str( version ) if version is not None else None,
        "registry": registry if registry is not None else "same",
    }
    if use_libs:
        normalised["use_libs"] = [ str( item ) for item in use_libs ]
    if normalised["version"] is None:
        raise ValueError(
            "dependency [{}] requires a concrete 'version' (MVP)".format( normalised["name"] )
        )
    return normalised


def build_manifest( dependencies: list | None ) -> dict | None:
    """Return a manifest document, or ``None`` when there are no dependencies."""
    if not dependencies:
        return None
    entries = [ normalise_dependency_entry( item ) for item in dependencies ]
    if not entries:
        return None
    return {
        "cuppa_dependency_format": MANIFEST_FORMAT,
        "dependencies": entries,
    }


def write_manifest( package_dir: str, dependencies: list | None ) -> str | None:
    """Write ``cuppa-dependency.json`` under ``package_dir`` when deps are non-empty.

    Returns the path written, or ``None`` if nothing was written.
    """
    document = build_manifest( dependencies )
    if document is None:
        return None
    path = manifest_path( package_dir )
    os.makedirs( package_dir, exist_ok=True )
    with open( path, "w", encoding="utf-8" ) as handle:
        json.dump( document, handle, indent=2, sort_keys=True )
        handle.write( "\n" )
    return path


def read_manifest( package_dir: str ) -> dict | None:
    """Load a manifest from ``package_dir``, or ``None`` if absent / empty."""
    path = manifest_path( package_dir )
    if not os.path.isfile( path ):
        return None
    with open( path, encoding="utf-8" ) as handle:
        document = json.load( handle )
    if not isinstance( document, dict ):
        raise ValueError( "{}: expected a JSON object".format( path ) )
    format_version = document.get( "cuppa_dependency_format" )
    if format_version not in ( None, MANIFEST_FORMAT, 1 ):
        raise ValueError(
            "{}: unsupported cuppa_dependency_format [{}]".format( path, format_version )
        )
    deps = document.get( "dependencies" ) or []
    if not deps:
        return None
    # Re-normalise for validation
    document["dependencies"] = [ normalise_dependency_entry( item ) for item in deps ]
    document["cuppa_dependency_format"] = format_version or MANIFEST_FORMAT
    return document
