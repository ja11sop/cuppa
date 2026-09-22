#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Publish version tokens (latest → concrete for stage / registry)
#-------------------------------------------------------------------------------

"""Resolve floating publish versions for ``GitlabPackagePublisher``.

A publisher seed / tip ``cuppa-publish.json`` may keep ``"version": "latest"``
(matching source Boost / ``boost_package`` consume). The staged archive and
registry upload always record a concrete pin. See open question 10 in
``design/plans/package-build-publish-deps.md``.
"""

from __future__ import annotations

import SCons.Errors

from cuppa.colourise import as_error, as_info, as_notice
from cuppa.log import logger
from cuppa.utility.types import is_string


_FLOATING_TOKENS = frozenset( ( "latest", "current" ) )


def is_floating_publish_version( version ) -> bool:
    """True for ``None`` / ``\"latest\"`` / ``\"current\"`` (case-insensitive)."""
    if version is None:
        return True
    if not is_string( version ):
        return False
    return str( version ).strip().lower() in _FLOATING_TOKENS


def floating_seed_token( version ) -> str:
    """Canonical floating token written into a publisher-tree seed."""
    if version is None:
        return "latest"
    token = str( version ).strip().lower()
    if token in _FLOATING_TOKENS:
        return token
    return "latest"


def _boost_style_dot_version( version: str ) -> str:
    """``1_92`` / ``1.92.0`` → registry-style ``1.92`` (major.minor)."""
    text = str( version ).strip().replace( "_", "." )
    parts = [ part for part in text.split( "." ) if part != "" ]
    if len( parts ) >= 2:
        return "{}.{}".format( parts[0], parts[1] )
    return text


def _concrete_from_build_with( env, package: str ):
    """Return a concrete version from an active BuildWith, or ``None``."""
    from cuppa.package_managers.package_paths import package_version

    names = [ package ]
    if package == "boost":
        # Source Boost publisher: prefer BuildWith('boost') over boost_package.
        names = [ "boost", "boost_package" ]
    for name in names:
        try:
            ver = package_version( env, name )
        except Exception:
            continue
        if not ver:
            continue
        if name == "boost":
            return _boost_style_dot_version( ver )
        return str( ver )
    return None


def _concrete_from_boost_latest( env ):
    """Resolve upstream Boost latest to major.minor (registry Boost package form)."""
    try:
        from cuppa.dependencies.boost.version_and_location import (
                resolve_boost_latest_version,
        )
    except Exception:
        return None
    try:
        version, source = resolve_boost_latest_version( env, force_scrape=False )
    except Exception:
        return None
    if not version:
        return None
    concrete = _boost_style_dot_version( version )
    logger.info(
            "Resolved publish version latest for package [{}] from Boost latest "
            "[{}] ({})".format(
                    as_info( "boost" ),
                    as_info( concrete ),
                    as_notice( str( source ) ),
            )
    )
    return concrete


def _concrete_from_registry( env, registry, package, custom_token=None ):
    if not registry:
        return None
    from cuppa.package_managers.gitlab_latest import (
            GitlabLatestError,
            resolve_latest_package_version,
    )
    try:
        return resolve_latest_package_version(
                env,
                registry=registry,
                package=package,
                custom_token=custom_token,
        )
    except GitlabLatestError as error:
        raise SCons.Errors.StopError(
                "Cannot resolve publish version latest for package [{}]: {}".format(
                        package, error
                )
        )


def resolve_publisher_version(
        env,
        package,
        version,
        registry=None,
        custom_token=None,
):
    """Return ``(seed_version, concrete_version)`` for a publisher identity.

    When ``version`` is floating, ``seed_version`` is the floating token
    (``latest`` / ``current``) and ``concrete_version`` is resolved from
    BuildWith, Boost latest (package ``boost``), or the registry. When
    ``version`` is already concrete, both return values are that string.
    """
    package = str( package )
    if not is_floating_publish_version( version ):
        concrete = str( version )
        return concrete, concrete

    seed = floating_seed_token( version )
    concrete = _concrete_from_build_with( env, package )
    if concrete is None and package == "boost":
        concrete = _concrete_from_boost_latest( env )
    if concrete is None:
        concrete = _concrete_from_registry(
                env, registry, package, custom_token=custom_token
        )
    if not concrete:
        raise SCons.Errors.StopError(
                "Cannot resolve publish version [{}] for package [{}]: "
                "no BuildWith pin, no Boost latest, and no registry latest "
                "(pass a concrete version= or BuildWith the package first)".format(
                        as_error( seed ), as_error( package )
                )
        )
    concrete = str( concrete )
    logger.info(
            "Publish package [{}]: seed version [{}], staged/registry version [{}]"
            .format(
                    as_info( package ),
                    as_info( seed ),
                    as_info( concrete ),
            )
    )
    return seed, concrete
