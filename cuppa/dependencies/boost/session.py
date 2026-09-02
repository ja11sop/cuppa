#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Session Boost (source vs package)
#-------------------------------------------------------------------------------

"""Resolve which Boost instance a session should use.

``env['dependencies']`` is the *factory registry*. The built-in source ``boost``
factory is always registered, even when the project only declared
``boost_package``. Calling that factory extracts ``archives.boost.io``.
"""


def session_boost( env ):
    """Return the Boost dependency for this env, or ``None``.

    Prefer a declared ``boost_package`` so package-only builds never instantiate
    source Boost. Fall back to the built-in ``boost`` factory.
    """
    factories = env.get( 'dependencies' ) or {}
    package = factories.get( 'boost_package' )
    if package is not None:
        return package( env )
    source = factories.get( 'boost' )
    if source is not None:
        return source( env )
    return None
