#          Copyright Jamie Allsop 2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Subprocess environment helpers
#-------------------------------------------------------------------------------

import os

from cuppa.log import logger


def export_for_subprocess( env, **variables ):
    """Copy variables into ``env['ENV']`` for later Run/Test subprocesses.

    Prefer this (or returning a dict from a Run callable) over
    ``inherit_process_env``.
    """
    construction_env = env.get( 'ENV' )
    if construction_env is None:
        return

    for key, value in variables.items():
        if value is None:
            continue
        construction_env[key] = value


def merge_callable_exports( env, result ):
    """If a Run callable returned a mapping, merge it into ``env['ENV']``."""
    if isinstance( result, dict ):
        export_for_subprocess( env, **result )


def resolve_inherit_process_env( scons_env, per_run=None ):
    """Resolve whether a subprocess should inherit ``os.environ`` at spawn time."""
    if per_run is not None:
        return bool( per_run )
    return bool( scons_env.get( 'inherit_process_env' ) )


def build_subprocess_env( construction_env, scons_env, inherit_process_env=None ):
    """Build the ``env=`` dict for ``subprocess.Popen`` from SCons ``ENV``."""
    subprocess_env = {}
    for key, value in construction_env.items():
        if value is None:
            continue
        if isinstance( value, ( list, tuple ) ):
            value = os.pathsep.join( str( part ) for part in value if part is not None )
        else:
            value = str( value )
        subprocess_env[str( key )] = value

    if resolve_inherit_process_env( scons_env, inherit_process_env ):
        logger.warn(
            "inherit_process_env is enabled for a Run/Test subprocess: merging the"
            " current process environment. Prefer export_for_subprocess( env, ... ) or"
            " returning a dict from Run callables."
        )
        merged = os.environ.copy()
        merged.update( subprocess_env )
        return merged

    return subprocess_env
