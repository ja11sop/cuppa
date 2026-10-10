#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""GitLab package version bounds (exact / minimum / latest).

See ``design/plans/gitlab-package-version-ranges.md``. Not pip / PEP 440 —
one token per edge: ``1.28.0``, ``==1.28.0``, ``>=1.28.0``, or ``latest``.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

from cuppa.utility.types import is_string


SUPPORTED_SPELLINGS = (
        "exact (1.28.0 or ==1.28.0), minimum (>=1.28.0), or latest"
)


class VersionBoundError( ValueError ):
    """Unsupported or unusable version bound spelling."""


class VersionBoundConflict( ValueError ):
    """Two bounds on the same package identity cannot be intersected."""

    def __init__( self, message, *, left=None, right=None ):
        super().__init__( message )
        self.left = left
        self.right = right


class VersionBound:
    """Normalised bound for one package edge or pin-table entry."""

    __slots__ = ( "kind", "version", "token" )

    def __init__( self, kind: str, version: str | None, token: str ):
        self.kind = kind  # exact | minimum | latest
        self.version = version
        self.token = token

    def __repr__( self ):
        return "VersionBound({!r}, version={!r}, token={!r})".format(
                self.kind, self.version, self.token
        )

    def __eq__( self, other ):
        if not isinstance( other, VersionBound ):
            return NotImplemented
        return (
                self.kind == other.kind
                and self.version == other.version
                and self.token == other.token
        )

    def __hash__( self ):
        return hash( ( self.kind, self.version, self.token ) )

    @property
    def is_exact( self ) -> bool:
        return self.kind == "exact"

    @property
    def is_minimum( self ) -> bool:
        return self.kind == "minimum"

    @property
    def is_latest( self ) -> bool:
        return self.kind == "latest"

    @property
    def is_soft( self ) -> bool:
        return self.kind in ( "minimum", "latest" )

    def display( self ) -> str:
        """Canonical spelling for list / error messages."""
        if self.kind == "exact":
            return str( self.version )
        if self.kind == "minimum":
            return ">={}".format( self.version )
        return "latest"


_EXACT_EQ = re.compile( r"^==\s*(.+)$" )
_MINIMUM = re.compile( r"^>=\s*(.+)$" )
_UNSUPPORTED_MARKERS = re.compile(
        r"[,<>!~^]|<=|!=|~=|\*"
)


def parse_version_bound( token ) -> VersionBound:
    """Parse a version edge token into a :class:`VersionBound`.

    ``None`` / empty is not accepted here — callers map those to ``latest``
    (consume) or fill from BuildWith (publish) before parsing.
    """
    if token is None or ( is_string( token ) and str( token ).strip() == "" ):
        raise VersionBoundError(
                "version is missing; use {}.".format( SUPPORTED_SPELLINGS )
        )
    if not is_string( token ):
        raise VersionBoundError(
                "version must be a string ({}); got {!r}.".format(
                        SUPPORTED_SPELLINGS, token
                )
        )

    text = str( token ).strip()
    lowered = text.lower()

    if lowered == "latest":
        return VersionBound( "latest", None, "latest" )

    # Refuse pip-like / multi-clause spellings before accepting a bare version.
    if _UNSUPPORTED_MARKERS.search( text ) and not (
            _EXACT_EQ.match( text ) or _MINIMUM.match( text )
    ):
        raise VersionBoundError(
                "unsupported version spelling [{}]; supported: {}.".format(
                        text, SUPPORTED_SPELLINGS
                )
        )

    match = _EXACT_EQ.match( text )
    if match:
        version = match.group( 1 ).strip()
        if not version or _UNSUPPORTED_MARKERS.search( version ):
            raise VersionBoundError(
                    "unsupported version spelling [{}]; supported: {}.".format(
                            text, SUPPORTED_SPELLINGS
                    )
            )
        return VersionBound( "exact", version, "=={}".format( version ) )

    match = _MINIMUM.match( text )
    if match:
        version = match.group( 1 ).strip()
        if not version or _UNSUPPORTED_MARKERS.search( version ):
            raise VersionBoundError(
                    "unsupported version spelling [{}]; supported: {}.".format(
                            text, SUPPORTED_SPELLINGS
                    )
            )
        return VersionBound( "minimum", version, ">={}".format( version ) )

    if _UNSUPPORTED_MARKERS.search( text ) or " " in text:
        raise VersionBoundError(
                "unsupported version spelling [{}]; supported: {}.".format(
                        text, SUPPORTED_SPELLINGS
                )
        )

    return VersionBound( "exact", text, text )


def compare_versions( left, right ) -> int:
    """Return ``-1`` / ``0`` / ``1`` using ``package_version_sort_key``."""
    from cuppa.package_managers.gitlab_latest import package_version_sort_key

    a = package_version_sort_key( left )
    b = package_version_sort_key( right )
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def version_satisfies( bound: VersionBound, concrete ) -> bool:
    """True when ``concrete`` meets ``bound``."""
    if concrete is None or str( concrete ).strip() == "":
        return False
    text = str( concrete ).strip()
    if bound.is_latest:
        return True
    if bound.is_exact:
        return compare_versions( text, bound.version ) == 0
    if bound.is_minimum:
        return compare_versions( text, bound.version ) >= 0
    return False


def intersect_version_bounds( left: VersionBound, right: VersionBound ) -> VersionBound:
    """Return the tightest bound that satisfies both, or raise conflict."""
    if left == right:
        return left

    if left.is_latest:
        return right
    if right.is_latest:
        return left

    if left.is_exact and right.is_exact:
        if compare_versions( left.version, right.version ) == 0:
            return left
        raise VersionBoundConflict(
                "exact versions [{}] and [{}] disagree".format(
                        left.display(), right.display()
                ),
                left=left,
                right=right,
        )

    if left.is_exact and right.is_minimum:
        if version_satisfies( right, left.version ):
            return left
        raise VersionBoundConflict(
                "exact [{}] does not satisfy [{}]".format(
                        left.display(), right.display()
                ),
                left=left,
                right=right,
        )

    if left.is_minimum and right.is_exact:
        if version_satisfies( left, right.version ):
            return right
        raise VersionBoundConflict(
                "exact [{}] does not satisfy [{}]".format(
                        right.display(), left.display()
                ),
                left=left,
                right=right,
        )

    # minimum ∩ minimum → higher floor
    if compare_versions( left.version, right.version ) >= 0:
        return left
    return right


def select_highest_satisfying(
        bound: VersionBound, candidates: Iterable,
) -> str | None:
    """Highest candidate that satisfies ``bound``, or ``None``."""
    from cuppa.package_managers.gitlab_latest import package_version_sort_key

    matching = [
            str( item ).strip()
            for item in candidates
            if item is not None and str( item ).strip() and version_satisfies( bound, item )
    ]
    if not matching:
        return None
    return max( matching, key=package_version_sort_key )


def format_bound_with_resolved( bound: VersionBound, concrete=None ) -> str:
    """List-style ``bound → concrete`` when they differ; else bound alone."""
    display = bound.display()
    if concrete is None or str( concrete ).strip() == "":
        return display
    concrete_text = str( concrete ).strip()
    if bound.is_exact and compare_versions( bound.version, concrete_text ) == 0:
        return display
    return "{} → {}".format( display, concrete_text )


def cached_package_versions( downloads_root, package ) -> list[str]:
    """Version directory names under ``downloads_root/packages/<package>/``."""
    if not downloads_root or not package:
        return []
    root = os.path.join( str( downloads_root ), "packages", str( package ) )
    if not os.path.isdir( root ):
        return []
    versions = []
    for name in os.listdir( root ):
        path = os.path.join( root, name )
        if os.path.isdir( path ) and name not in ( ".", ".." ):
            versions.append( name )
    return versions


def resolve_bound_to_concrete(
        env,
        bound: VersionBound,
        *,
        registry,
        package,
        custom_token=None,
        opener=None,
        dependency_name=None,
        prefer_concrete=None,
        force_refresh=False,
) -> str:
    """Choose a concrete version for ``bound`` (cache / remember / registry).

    Policy (plan examples 2 / 9):

    - Exact → that version string (no registry list required).
    - Soft bound: keep ``prefer_concrete`` / on-disk / remembered when they still
      satisfy and ``force_refresh`` is false; otherwise pick the highest
      satisfying registry version (online). Offline only uses cache / remember.
    """
    import SCons.Errors
    from cuppa.package_managers.gitlab_latest import (
            GitlabLatestError,
            GitlabLatestNetworkError,
            list_generic_package_versions,
            remember_registry_latest,
            stored_registry_latest,
    )

    if bound.is_exact:
        return str( bound.version )

    if bound.is_latest:
        from cuppa.package_managers.gitlab_latest import resolve_latest_package_version

        return resolve_latest_package_version(
                env,
                registry=registry,
                package=package,
                custom_token=custom_token,
                opener=opener,
                dependency_name=dependency_name,
        )

    offline = False
    if hasattr( env, "__contains__" ) and "offline" in env:
        offline = bool( env["offline"] )
    elif hasattr( env, "get" ):
        offline = bool( env.get( "offline" ) )

    downloads_root = None
    if hasattr( env, "get" ):
        downloads_root = env.get( "downloads_root" )
    if downloads_root is None and hasattr( env, "__contains__" ) and "downloads_root" in env:
        downloads_root = env["downloads_root"]

    local: list[str] = []
    if prefer_concrete and version_satisfies( bound, prefer_concrete ):
        local.append( str( prefer_concrete ).strip() )
    local.extend( cached_package_versions( downloads_root, package ) )
    remembered = stored_registry_latest( env, registry, package )
    if remembered and version_satisfies( bound, remembered ):
        local.append( str( remembered ) )

    local_pick = select_highest_satisfying( bound, local )

    if offline:
        if local_pick:
            return local_pick
        raise SCons.Errors.StopError(
                "Offline: no cached or remembered version of package [{}] "
                "satisfies [{}] (registry [{}]).".format(
                        package, bound.display(), registry
                )
        )

    if local_pick and not force_refresh:
        return local_pick

    try:
        versions = list_generic_package_versions(
                registry, package, custom_token=custom_token, opener=opener
        )
    except GitlabLatestNetworkError as error:
        if local_pick:
            return local_pick
        raise SCons.Errors.StopError(
                "Cannot list registry versions for package [{}] to satisfy "
                "[{}]: {}".format( package, bound.display(), error )
        ) from error
    except GitlabLatestError as error:
        if local_pick:
            return local_pick
        raise SCons.Errors.StopError(
                "Cannot list registry versions for package [{}] to satisfy "
                "[{}]: {}".format( package, bound.display(), error )
        ) from error

    chosen = select_highest_satisfying( bound, versions )
    if not chosen:
        raise SCons.Errors.StopError(
                "No version of package [{}] in registry [{}] satisfies [{}].".format(
                        package, registry, bound.display()
                )
        )
    remember_registry_latest( env, registry, package, chosen )
    return chosen
