
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Shared path vocabulary for StaticGlob (and optional future Glob wrapper)
#-------------------------------------------------------------------------------
#
#   Input styles (same meaning for static and dynamic discovery):
#     #/… or #…   — from project / sconstruct root
#     start='src' — directory relative to the calling sconscript_dir
#     absolute    — last resort (packages / generated paths)
#
import os

from cuppa.log import logger
from cuppa.colourise import as_notice


# Sentinel: callers pass this (or omit) to mean "start at the sconscript directory".
DEFAULT_START = ()


def _strip_sconstruct_anchor( path ):
    """Return the path relative to the sconstruct root when ``path`` uses ``#`` / ``#/``."""
    if not path.startswith( '#' ):
        return None
    rest = path[1:]
    if rest.startswith( '/' ) or rest.startswith( os.sep ):
        rest = rest[1:]
    return rest


def resolve_glob_start( env, start=DEFAULT_START, default=DEFAULT_START ):
    """Resolve a StaticGlob / Glob ``start`` to an absolute directory.

    Returns ``(absolute_start, sconscript_dir)`` where ``sconscript_dir`` is the
    real path of the calling sconscript (used as the ``env.File`` base for
    project-relative nodes).
    """
    sconscript_dir = os.path.realpath( env['sconscript_dir'] )

    if start == default:
        return sconscript_dir, sconscript_dir

    start = os.path.expanduser( start )
    anchored = _strip_sconstruct_anchor( start )
    if anchored is not None:
        sconstruct_dir = os.path.realpath( env['sconstruct_dir'] )
        absolute = (
            os.path.join( sconstruct_dir, anchored ) if anchored else sconstruct_dir
        )
    elif not os.path.isabs( start ):
        absolute = os.path.join( sconscript_dir, start )
    else:
        absolute = start

    return os.path.realpath( absolute ), sconscript_dir


def relative_glob_start( env, start=DEFAULT_START, default=DEFAULT_START ):
    """Resolve ``start`` and compute how to express matches relative to the sconscript.

    Returns ``(absolute_start, rel_from_start_to_sconscript, sconscript_dir)``.
    ``rel_from_start_to_sconscript`` is ``os.path.relpath(sconscript_dir, absolute_start)``
    — used to decide whether match paths can be stored as sconscript-relative
    ``env.File`` nodes (when that relpath does not climb with ``..``).
    """
    absolute_start, sconscript_dir = resolve_glob_start( env, start, default )
    rel_start = os.path.relpath( sconscript_dir, absolute_start )

    logger.trace(
            "glob roots: start = [{}], sconscript_dir = [{}], rel_start = [{}]"
            .format(
                    as_notice( absolute_start ),
                    as_notice( sconscript_dir ),
                    as_notice( rel_start ),
            )
    )

    return absolute_start, rel_start, sconscript_dir
