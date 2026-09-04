
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildWith dependency resolve (untyped precedence + type selectors)
#-------------------------------------------------------------------------------

"""Resolve ``BuildWith`` dependency tokens to a factory-registry name.

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

# Untyped short name → ordered (registry_name, role) candidates.
# role: 'gitlab' | 'archive' — used for availability and Conan refusal.
_UNTYPED_PRECEDENCE = {
    'boost': (
        ( 'boost_package', 'gitlab' ),  # legacy GitLab package registry name
        ( 'boost', 'archive' ),
    ),
}


def _as_name_set( value ):
    if not value:
        return set()
    return set( Flatten( [ value ] ) )


def is_project_available( env, registry_name ):
    """True when ``registry_name`` may be chosen for untyped / typed resolve.

    Declared (``default_dependencies``) or already ``BuildWith``'d this session
    counts. Always-on built-ins also require one of those — registry presence
    alone is not enough. Other factories (e.g. ``boost_package``) are treated as
    declared when present in ``env['dependencies']``.
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

    Untyped ``boost`` prefers project-available ``boost_package``, then falls
    back to built-in ``boost``. Explicit ``[gitlab]boost``, ``[archive]boost``,
    and ``boost_package`` bypass precedence. ``[conan]…`` is refused for now.

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

    if storage_type in ( 'archive', ):
        return _require_factory( factories, name, token, required )

    if storage_type == 'gitlab':
        if name == 'boost':
            # Canonical GitLab short name maps to legacy registry key today.
            if 'boost_package' in factories:
                return 'boost_package'
            return _missing( token, required )
        return _require_factory( factories, name, token, required )

    # Untyped (or repository/other selectors unused for BuildWith boost yet).
    if storage_type is not None and storage_type not in ( 'archive', 'gitlab' ):
        # Allow exact registry lookup for other typed tokens later; for now
        # require the bare name in the registry.
        return _require_factory( factories, name, token, required )

    precedence = _UNTYPED_PRECEDENCE.get( name )
    if precedence:
        archive_fallback = None
        for registry_name, role in precedence:
            if registry_name not in factories:
                continue
            if role == 'archive':
                archive_fallback = registry_name
                continue
            if is_project_available( env, registry_name ):
                return registry_name
        if archive_fallback is not None:
            # Built-in archive: final fallback even when not yet project-available
            # so BuildWith('boost') keeps working as an opt-in to the built-in.
            return archive_fallback
        return _missing( token, required )

    return _require_factory( factories, name, token, required )


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
