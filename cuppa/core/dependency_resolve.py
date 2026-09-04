
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildWith dependency resolve (untyped precedence + type selectors)
#-------------------------------------------------------------------------------

"""Resolve ``BuildWith`` dependency tokens to a factory-registry name.

Rules are **name-general**, not Boost-specific. Untyped ``BuildWith('widget_lib')``
prefers a project-available GitLab candidate over an archive/built-in short name.

See ``design/plans/dependency-resolve.md``. Storage list/remove tokens share
selector spelling via ``cuppa.core.dependency_tokens``.
"""

from SCons.Script import Flatten

from cuppa.core.dependency_tokens import parse_dependency_token
from cuppa.utility.types import is_string


class DependencyResolveException( Exception ):

    def __init__( self, value ):
        self.parameter = value

    def __str__( self ):
        return repr( self.parameter )


# Always-on built-in short names: present in the factory registry even when the
# project did not declare them. Registry presence alone is not project-available.
_ALWAYS_ON_BUILTINS = frozenset( {
    'boost',
} )


def _as_name_set( value ):
    if not value:
        return set()
    return set( Flatten( [ value ] ) )


def _legacy_package_name( name ):
    """Historical GitLab registry key when the short name was already taken."""
    return '{}_package'.format( name )


def _gitlab_registry_candidates( name ):
    """Ordered registry keys that may identify a GitLab package for ``name``."""
    return (
        '[gitlab]{}'.format( name ),  # future typed registration
        _legacy_package_name( name ),  # legacy: boost_package, widget_lib_package, …
    )


def _archive_registry_candidates( name ):
    """Ordered registry keys that may identify an archive / built-in for ``name``."""
    return (
        '[archive]{}'.format( name ),
        '[source]{}'.format( name ),
        name,
    )


def is_project_available( env, registry_name ):
    """True when ``registry_name`` may be chosen for untyped / typed resolve.

    Declared (``default_dependencies``) or already ``BuildWith``'d this session
    counts. Always-on built-ins also require one of those — registry presence
    alone is not enough. Other factories (e.g. ``widget_lib_package``) are
    treated as declared when present in ``env['dependencies']``.
    """
    factories = env.get( 'dependencies' ) or {}
    if registry_name not in factories:
        return False
    if registry_name in _as_name_set( env.get( 'BUILD_WITH' ) ):
        return True
    if registry_name in _as_name_set( env.get( 'default_dependencies' ) ):
        return True
    if registry_name in _ALWAYS_ON_BUILTINS:
        return False
    return True


def resolve_registry_name( env, token, required=True ):
    """Map a ``BuildWith`` token to an ``env['dependencies']`` factory key.

    Untyped ``name`` prefers project-available GitLab candidates
    (``[gitlab]name``, then legacy ``name_package``), then the short name /
    archive keys. Explicit ``[gitlab]…`` / ``[archive]…`` pin the supply chain.
    ``[conan]…`` is refused for now.

    Returns the registry name, or ``None`` when ``required`` is false and nothing
    matches. Raises ``DependencyResolveException`` when ``required`` and resolve
    fails.
    """
    if not is_string( token ):
        raise DependencyResolveException(
                "dependency resolve expects a string token, got {!r}".format( token )
        )

    parsed, error = parse_dependency_token( token )
    if error:
        raise DependencyResolveException( error )

    storage_type, name, qualifier = parsed
    if qualifier is not None:
        raise DependencyResolveException(
                "BuildWith does not accept a /qualifier in dependency token [{}] "
                "(got qualifier [{}])".format( token, qualifier )
        )

    if storage_type == 'conan':
        raise DependencyResolveException(
                "BuildWith does not support [conan] dependencies yet "
                "(token [{}]); use an explicit Conan BuildWith name when ready"
                .format( token )
        )

    factories = env.get( 'dependencies' ) or {}

    if storage_type == 'archive':
        return _resolve_archive( factories, name, token, required )

    if storage_type == 'gitlab':
        return _resolve_gitlab( factories, name, token, required )

    if storage_type is not None:
        # Other typed tokens: exact registry name for now.
        return _require_factory( factories, name, token, required )

    return _resolve_untyped( env, factories, name, token, required )


def _resolve_gitlab( factories, name, token, required ):
    for registry_name in _gitlab_registry_candidates( name ):
        if registry_name in factories:
            return registry_name
    # Short name only if it is not an always-on archive built-in.
    if name in factories and name not in _ALWAYS_ON_BUILTINS:
        return name
    return _missing( token, required )


def _resolve_archive( factories, name, token, required ):
    for registry_name in _archive_registry_candidates( name ):
        if registry_name in factories:
            return registry_name
    return _missing( token, required )


def _resolve_untyped( env, factories, name, token, required ):
    for registry_name in _gitlab_registry_candidates( name ):
        if registry_name in factories and is_project_available( env, registry_name ):
            return registry_name

    if name in factories and is_project_available( env, name ):
        return name

    for registry_name in ( '[archive]{}'.format( name ), '[source]{}'.format( name ) ):
        if registry_name in factories and is_project_available( env, registry_name ):
            return registry_name

    # Final fallback: short name in the registry (always-on built-in opt-in, or
    # the only registered identity for this name).
    if name in factories:
        return name

    return _missing( token, required )


def _require_factory( factories, registry_name, token, required ):
    if registry_name in factories:
        return registry_name
    return _missing( token, required )


def _missing( token, required ):
    if required:
        raise DependencyResolveException(
                "dependency [{}] is not available for BuildWith".format( token )
        )
    return None
