#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Delegate link-line append policy to the active toolchain (opt-in).

Call sites resolve what to put on the link line; they should not hard-code
``Append`` vs ``AppendUnique``. Toolchains that care expose
``append_static_libs`` / ``append_shared_libs`` / ``append_libpath``. When a
hook is absent, behaviour matches today's defaults (``AppendUnique``).

See ``design/archive/gitlab-package-lib-groups.md`` (link append policy).
"""

from __future__ import annotations

from SCons.Script import Flatten


def _toolchain( env ):
    """Return ``env['toolchain']`` when present (dict-like or mapping)."""
    getter = getattr( env, "get", None )
    if callable( getter ):
        return getter( "toolchain" )
    try:
        return env[ "toolchain" ]
    except ( KeyError, TypeError, AttributeError ):
        return None


def append_static_libs( env, libs ):
    """Append static archives using toolchain policy, else ``AppendUnique``."""
    libs = Flatten( [ libs ] )
    if not libs:
        return
    toolchain = _toolchain( env )
    append = getattr( toolchain, "append_static_libs", None ) if toolchain else None
    if append:
        append( env, libs )
    else:
        env.AppendUnique( STATICLIBS = libs )


def append_shared_libs( env, libs ):
    """Append shared library stems using toolchain policy, else ``AppendUnique``."""
    libs = Flatten( [ libs ] )
    if not libs:
        return
    toolchain = _toolchain( env )
    append = getattr( toolchain, "append_shared_libs", None ) if toolchain else None
    if append:
        append( env, libs )
    else:
        env.AppendUnique( SHAREDLIBS = libs )


def append_libpath( env, paths ):
    """Append library search paths using toolchain policy, else ``AppendUnique``."""
    paths = Flatten( [ paths ] )
    if not paths:
        return
    toolchain = _toolchain( env )
    append = getattr( toolchain, "append_libpath", None ) if toolchain else None
    if append:
        append( env, paths )
    else:
        env.AppendUnique( LIBPATH = paths )
