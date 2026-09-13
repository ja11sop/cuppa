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

from cuppa.utility.types import is_string


MANIFEST_FILENAME = "cuppa-dependency.json"
MANIFEST_FORMAT = 1


def manifest_path( package_dir: str ) -> str:
    return os.path.join( package_dir, MANIFEST_FILENAME )


def package_slug_from_name( name: str ) -> str:
    """GitLab package slug from a Cuppa BuildWith name (``_`` → ``-``)."""
    return str( name ).replace( '_', '-' )


def package_name_from_slug( package: str ) -> str:
    """Cuppa BuildWith name from a GitLab package slug (``-`` → ``_``)."""
    return str( package ).replace( '-', '_' )


def coerce_dependency_entry( entry: Any ) -> dict:
    """Expand a bare string, partial dict, or object into a dependency dict.

    Name ↔ package convention when only one is given:

    - ``name`` only → ``package = name.replace('_', '-')``
    - ``package`` only → ``name = package.replace('-', '_')``
    - both → unchanged
    - bare string → treated as **name**, then derive package

    Empty / missing ``registry`` becomes ``"same"``. Does **not** require
    ``version`` (filled later via :func:`fill_dependency_versions`).
    """
    if is_string( entry ):
        name = str( entry )
        return {
            "name": name,
            "package": package_slug_from_name( name ),
            "registry": "same",
        }

    if isinstance( entry, dict ):
        name = entry.get( "name" )
        package = entry.get( "package" )
        if name is None and package is None:
            raise ValueError(
                "dependency entry needs 'name' and/or 'package' "
                "(or pass a bare BuildWith name string)"
            )
        if name is None:
            name = package_name_from_slug( package )
        else:
            name = str( name )
        if package is None:
            package = package_slug_from_name( name )
        else:
            package = str( package )
        out = dict( entry )
        out["name"] = name
        out["package"] = package
        registry = out.get( "registry", "same" )
        if registry is None or registry == "":
            out["registry"] = "same"
        else:
            out["registry"] = registry
        return out

    name_fn = getattr( entry, "name", None )
    name = name_fn() if callable( name_fn ) else getattr( entry, "name", None )
    if not name:
        raise ValueError( "dependency entry has no usable name()" )
    package_attr = getattr( entry, "package", None )
    if callable( package_attr ) and not isinstance( package_attr, ( list, tuple ) ):
        # callable package() on BuildWith wrappers returns the package *object*
        package_attr = getattr( entry, "_package", None )
    if package_attr is None:
        package_attr = getattr( entry, "_package", None )
    if package_attr is None:
        package = package_slug_from_name( name )
    else:
        package = str( package_attr )
    version = getattr( entry, "version", None ) or getattr( entry, "_version", None )
    if callable( version ):
        version = version()
    registry = getattr( entry, "registry", None ) or getattr( entry, "_registry", None )
    if registry is None or registry == "":
        registry = "same"
    use_libs = getattr( entry, "use_libs", None )
    if callable( use_libs ) and not isinstance( use_libs, ( list, tuple ) ):
        use_libs = None
    out = {
        "name": str( name ),
        "package": package,
        "registry": registry,
    }
    if version is not None:
        out["version"] = version
    if use_libs:
        out["use_libs"] = [ str( item ) for item in use_libs ]
    return out


def fill_dependency_versions( env, dependencies: list | None ) -> list | None:
    """Fill missing ``version`` keys from ``BuildWith`` package pins.

    Coerces bare strings / partial dicts first. Explicit ``version`` values win.
    """
    if not dependencies:
        return dependencies
    from cuppa.package_managers.package_paths import package_version

    filled: list = []
    for entry in dependencies:
        coerced = coerce_dependency_entry( entry )
        if coerced.get( "version" ) is None:
            coerced = dict( coerced )
            coerced["version"] = package_version( env, coerced["name"] )
        filled.append( coerced )
    return filled


def normalise_dependency_entry( entry: Any ) -> dict:
    """Accept a string, dict, or object; return a concrete manifest dict.

    Dict / string entries may omit ``version`` only when a caller has already
    run :func:`fill_dependency_versions` (``write_manifest(..., env=…)`` does).
    """
    coerced = coerce_dependency_entry( entry )
    out = {
        "name": str( coerced["name"] ),
        "package": str( coerced["package"] ),
        "version": (
            str( coerced["version"] ) if coerced.get( "version" ) is not None else None
        ),
        "registry": coerced.get( "registry" ) or "same",
    }
    use_libs = coerced.get( "use_libs" )
    if use_libs:
        out["use_libs"] = [ str( item ) for item in use_libs ]
    if out["version"] is None:
        raise ValueError(
            "dependency [{}] requires a concrete 'version' "
            "(set it explicitly or pass env= to write_manifest / "
            "GitlabPackagePublisher so Cuppa can fill from BuildWith)"
            .format( out["name"] )
        )
    return out


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


def write_manifest(
        package_dir: str,
        dependencies: list | None,
        env=None,
) -> str | None:
    """Write ``cuppa-dependency.json`` under ``package_dir`` when deps are non-empty.

    When ``env`` is set, bare strings / partial dicts are coerced and missing
    ``version`` fields are filled from the active ``BuildWith`` package pin
    before normalisation.

    Returns the path written, or ``None`` if nothing was written.
    """
    if env is not None:
        dependencies = fill_dependency_versions( env, dependencies )
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
