
#          Copyright Jamie Allsop 2012-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RecursiveGlob / GlobFiles — source discovery
#-------------------------------------------------------------------------------
#
#   RecursiveGlob: configure-time os.walk snapshot (disk only), with cuppa
#   exclude_dirs / discard_pattern — stand-in for a recursive Glob.
#
#   GlobFiles: single-directory discovery via SCons env.Glob after resolving
#   start= / #/ — same file set as Glob for that directory, including declared
#   File nodes that are not on disk yet (and Repository entries when used).
#
import os
import re

import cuppa.recursive_glob
from cuppa.log import logger
from cuppa.colourise import as_notice, colour_items
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


def _directory_glob_pattern( absolute_start, sconscript_dir, rel_start, pattern ):
    """Build a SCons Glob pattern for one directory after resolving Cuppa start=."""
    pattern = pattern.replace( '\\', '/' )
    if os.path.normpath( absolute_start ) == os.path.normpath( sconscript_dir ):
        return pattern
    if not rel_start.startswith( os.pardir ):
        rel = os.path.relpath( absolute_start, sconscript_dir ).replace( '\\', '/' )
        return rel + '/' + pattern
    return os.path.join( absolute_start, pattern ).replace( '\\', '/' )


def _file_nodes_only( nodes ):
    files = []
    for node in nodes:
        is_dir = getattr( node, 'isdir', None )
        if callable( is_dir ) and is_dir():
            continue
        files.append( node )
    return files


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
        absolute_start, rel_start, sconscript_dir = relative_glob_start(
                env, start, self.default
        )
        exclude_dirs_regex = _exclude_dirs_regex( env, exclude_dirs, self.default )
        matches = cuppa.recursive_glob.glob(
                absolute_start,
                pattern,
                exclude_dirs_pattern=exclude_dirs_regex,
                discard_pattern=discard_pattern,
        )
        logger.trace(
                "matches = [{}]."
                .format( colour_items( [ str( match ) for match in matches ] ) )
        )
        return _file_nodes_for_matches( env, matches, rel_start, sconscript_dir )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "RecursiveGlob", cls() )


class GlobFilesMethod:
    """Single-directory discovery (SCons Glob + Cuppa start= / #/ vocabulary)."""

    default = DEFAULT_START

    def __call__( self, env, pattern, start=default ):
        # Uses SCons Glob so declared File nodes (and Repository entries) under
        # the resolved directory are visible — not only os.listdir.
        absolute_start, rel_start, sconscript_dir = relative_glob_start(
                env, start, self.default
        )
        glob_pat = _directory_glob_pattern(
                absolute_start, sconscript_dir, rel_start, pattern
        )
        logger.trace( "GlobFiles -> env.Glob([{}])".format( as_notice( glob_pat ) ) )
        return _file_nodes_only( env.Glob( glob_pat ) )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "GlobFiles", cls() )
