
#          Copyright Jamie Allsop 2012-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RecursiveGlob / GlobFiles — configure-time (snapshot) source discovery
#-------------------------------------------------------------------------------
#
#   Cuppa discovery is a *configure-time snapshot*: the file list is fixed when
#   the sconscript line runs. SCons env.Glob is a *directory Glob*: one path
#   segment per pattern, SCons-native File nodes, still not a tree walk.
#   Under Cuppa both re-run when the sconscript is re-read (every normal build),
#   so the recursion axis matters more than snapshot-vs-Glob for day-to-day use.
#
import os
import fnmatch
import re

import cuppa.recursive_glob
from cuppa.log import logger
from cuppa.colourise import as_notice, as_warning, colour_items
from cuppa.utility.glob_roots import (
        DEFAULT_START,
        relative_glob_start,
        resolve_glob_start,
)


# Kept for callers that imported the old helpers from this module.
def clean_start( env, start, default ):
    absolute, sconscript_dir = resolve_glob_start( env, start, default )
    return absolute, sconscript_dir


def relative_start( env, start, default ):
    return relative_glob_start( env, start, default )


_deprecated_glob_aliases = set()


def _warn_glob_alias_once( old_name, hint ):
    if old_name in _deprecated_glob_aliases:
        return
    _deprecated_glob_aliases.add( old_name )
    logger.warn(
            "env.{}() is deprecated; use {} (removed in cuppa 2.0)"
            .format( as_warning( old_name ), as_notice( hint ) )
    )


def _exclude_dirs_regex( env, exclude_dirs, default ):
    if exclude_dirs == default:
        exclude_dirs = [ env['dependencies_root'], env['build_root'] ]

    if not exclude_dirs:
        return None

    def up_dir( path ):
        element = next( e for e in path.split( os.path.sep ) if e )
        return element == ".."

    escaped = [
            re.escape( d ) for d in exclude_dirs
            if d and not os.path.isabs( d ) and not up_dir( d )
    ]
    # An empty alternation matches every folder. Absolute roots are already skipped above,
    # which is the common case now that dependencies live outside the project by default.
    return escaped and re.compile( "|".join( escaped ) ) or None


def _file_nodes_for_matches( env, matches, rel_start, sconscript_dir ):
    make_relative = not rel_start.startswith( os.pardir )
    logger.trace( "make_relative = [{}].".format( as_notice( str( make_relative ) ) ) )
    nodes = [
            env.File(
                    make_relative and os.path.relpath( match, sconscript_dir ) or match
            )
            for match in matches
    ]
    logger.trace(
            "nodes = [{}]."
            .format( colour_items( [ str( node ) for node in nodes ] ) )
    )
    return nodes


def snapshot_glob(
        env,
        pattern,
        start=DEFAULT_START,
        recursive=True,
        exclude_dirs=DEFAULT_START,
        discard_pattern=None,
):
    """Configure-time snapshot discovery shared by RecursiveGlob / GlobFiles / StaticGlob."""
    absolute_start, rel_start, sconscript_dir = relative_glob_start(
            env, start, DEFAULT_START
    )

    if recursive:
        exclude_dirs_regex = _exclude_dirs_regex( env, exclude_dirs, DEFAULT_START )
        matches = cuppa.recursive_glob.glob(
                absolute_start,
                pattern,
                exclude_dirs_pattern=exclude_dirs_regex,
                discard_pattern=discard_pattern,
        )
    else:
        matches = []
        for filename in os.listdir( absolute_start ):
            if fnmatch.fnmatch( filename, pattern ):
                matches.append( os.path.join( absolute_start, filename ) )

    logger.trace(
            "matches = [{}]."
            .format( colour_items( [ str( match ) for match in matches ] ) )
    )

    return _file_nodes_for_matches( env, matches, rel_start, sconscript_dir )


class RecursiveGlobMethod:
    """Recursive configure-time tree walk — Cuppa's stand-in for a recursive Glob."""

    default = DEFAULT_START

    def __call__(
            self,
            env,
            pattern,
            start=default,
            exclude_dirs=default,
            discard_pattern=None,
    ):
        # Discovery helper only: returns file nodes selected from the tree.
        # No build commands are emitted, so NotifyProgress is not applicable.
        return snapshot_glob(
                env,
                pattern,
                start=start,
                recursive=True,
                exclude_dirs=exclude_dirs,
                discard_pattern=discard_pattern,
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "RecursiveGlob", cls() )


class GlobFilesMethod:
    """Flat configure-time directory listing (one directory, no walk)."""

    default = DEFAULT_START

    def __call__( self, env, pattern, start=default ):
        return snapshot_glob( env, pattern, start=start, recursive=False )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "GlobFiles", cls() )


class StaticGlobMethod:
    """Deprecated umbrella name for snapshot discovery (prefer RecursiveGlob / GlobFiles)."""

    default = DEFAULT_START

    def __call__(
            self,
            env,
            pattern,
            start=default,
            recursive=True,
            exclude_dirs=default,
            discard_pattern=None,
    ):
        _warn_glob_alias_once(
                "StaticGlob",
                "env.RecursiveGlob(...) for trees or env.GlobFiles(...) for one directory",
        )
        return snapshot_glob(
                env,
                pattern,
                start=start,
                recursive=recursive,
                exclude_dirs=exclude_dirs,
                discard_pattern=discard_pattern,
        )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "StaticGlob", cls() )
