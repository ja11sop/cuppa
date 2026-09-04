
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Session Boost (source vs package)
#-------------------------------------------------------------------------------

"""Resolve which Boost instance a session should use.

Prefers project-available GitLab ``boost_package`` over built-in archive
``boost`` via ``cuppa.core.dependency_resolve`` (see
``design/plans/dependency-resolve.md``).
"""

from cuppa.core.dependency_resolve import resolve_registry_name


def session_boost( env ):
    """Return the Boost dependency for this env, or ``None``.

    Untyped resolve: ``boost_package`` when project-available, else built-in
    ``boost``. Does not instantiate source Boost when the package wins.
    """
    registry_name = resolve_registry_name( env, 'boost', required=False )
    if registry_name is None:
        return None
    factories = env.get( 'dependencies' ) or {}
    factory = factories.get( registry_name )
    if factory is None:
        return None
    return factory( env )
