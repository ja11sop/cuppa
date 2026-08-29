
#          Copyright Jamie Allsop 2012-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RecursiveGlob / GlobFiles — source discovery
#-------------------------------------------------------------------------------
#
#   RecursiveGlob: configure-time os.walk snapshot plus matching File nodes from
#   each visited directory's SCons Dir.entries (declared Files not on disk yet,
#   including nested declared paths). For each local directory visited, also
#   merges SCons Dir.glob matches so Repository files in those directories are
#   visible (shallow Repository parity with Glob). Repo-only subdirectory trees
#   are not walked — see design/plans/static-glob-rename.md.
#   exclude_dirs / discard_pattern apply to the local walk.
#
#   GlobFiles: single-directory discovery via SCons env.Glob after resolving
#   start= / #/ — same file set as Glob for that directory, including declared
#   File nodes that are not on disk yet (and Repository entries when used).
#
import fnmatch
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
from cuppa.utility.types import is_string


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


def _as_regex( pattern ):
    if pattern is None:
        return None
    if is_string( pattern ):
        return re.compile( fnmatch.translate( pattern ) )
    return pattern


def _start_dir_node( env, absolute_start, sconscript_dir ):
    """Dir node for ``absolute_start`` in the same FS tree as sconscript ``File`` decls.

    Prefer a path relative to ``sconscript_dir`` so VariantDir layouts share the
    node tree with ``env.File('src/…')``. Absolute ``env.Dir`` can resolve to a
    parallel node without those entries.
    """
    if os.path.normpath( absolute_start ) == os.path.normpath( sconscript_dir ):
        return env.Dir( '.' )
    rel = os.path.relpath( absolute_start, sconscript_dir )
    if rel == os.pardir or rel.startswith( os.pardir + os.sep ):
        return env.Dir( absolute_start )
    return env.Dir( rel )


def _is_dir_node( node ):
    # Dir.isdir() is False for directories that exist only as declared SCons nodes
    # (no disk path yet). Class check is required so we still recurse into them.
    try:
        from SCons.Node.FS import Dir, File
        if isinstance( node, Dir ):
            return True
        if isinstance( node, File ):
            return False
    except ImportError:
        pass
    is_dir = getattr( node, 'isdir', None )
    return callable( is_dir ) and is_dir()


def _source_node( node ):
    srcnode = getattr( node, 'srcnode', None )
    if callable( srcnode ):
        return srcnode()
    return node


def _node_exists( node ):
    exists = getattr( node, 'exists', None )
    return callable( exists ) and exists()


def _node_key( node ):
    src = _source_node( node )
    return getattr( src, 'abspath', None ) or str( src )


def _is_mergeable_declared_file( entry ):
    """True for declared Files not on disk and not Repository-backed.

    Under VariantDir, ``Dir.entries`` holds build-tree nodes whose ``exists()``
    is often False even when the source file is on disk — use ``srcnode()``.
    Repository lookups set ``rfile()`` to a path outside the source tree.
    """
    src = _source_node( entry )
    if _node_exists( src ):
        return False
    src_abs = getattr( src, 'abspath', None )
    if src_abs and os.path.isfile( src_abs ):
        return False
    rfile = getattr( entry, 'rfile', None )
    if callable( rfile ):
        remote = rfile()
        remote_abs = getattr( remote, 'abspath', None )
        if (
                remote_abs
                and remote_abs != src_abs
                and os.path.isfile( remote_abs )
        ):
            return False
    return True


def _files_from_dir_entries(
        dir_node,
        file_pattern,
        exclude_dirs_regex=None,
        discard_pattern=None,
        is_subdir=False,
):
    """Collect matching declared File nodes from Dir.entries, recursing into dirs.

    Includes Files that do not yet exist (intermediary / generated sources),
    including under declared-only directories. Skips on-disk sources and
    Repository-backed names — those are either found by the disk walk or
    intentionally invisible to RecursiveGlob.
    """
    entries = getattr( dir_node, 'entries', None )
    if not entries:
        return []

    names = [ name for name in entries if name not in ( '.', '..' ) ]
    if is_subdir and discard_pattern:
        # Same rule as os.walk: a matching *file* discards the whole subdirectory.
        for name in names:
            entry = entries[name]
            if _is_dir_node( entry ):
                continue
            if discard_pattern.match( name ):
                return []

    found = []
    for name in names:
        entry = entries[name]
        if _is_dir_node( entry ):
            if exclude_dirs_regex and exclude_dirs_regex.match( name ):
                continue
            found.extend(
                    _files_from_dir_entries(
                            entry,
                            file_pattern,
                            exclude_dirs_regex=exclude_dirs_regex,
                            discard_pattern=discard_pattern,
                            is_subdir=True,
                    )
            )
        elif file_pattern.match( name ) and _is_mergeable_declared_file( entry ):
            found.append( _source_node( entry ) )
    return found


def _merge_unique_nodes( primary, extra ):
    seen = { _node_key( node ) for node in primary }
    merged = list( primary )
    for node in extra:
        key = _node_key( node )
        if key not in seen:
            seen.add( key )
            merged.append( node )
    return merged


def _dir_child( dir_node, rel ):
    """Return ``dir_node`` or a child Dir for ``rel`` (``.`` means self)."""
    if not rel or rel == os.curdir:
        return dir_node
    child = getattr( dir_node, 'Dir', None )
    if callable( child ):
        return child( rel.replace( '\\', '/' ) )
    return dir_node


def _files_from_local_repository_globs(
        start_dir,
        absolute_start,
        pattern,
        exclude_dirs_regex=None,
        discard_pattern=None,
):
    """Shallow Repository parity: ``Dir.glob`` per *local* directory visited.

    Walks the same local tree as ``recursive_glob.glob`` (honouring exclude /
    discard). For each kept directory, calls SCons ``Dir.glob(pattern)``, which
    searches Repositories for that directory only. Does **not** descend into
    subdirectory trees that exist only in a Repository.
    """
    if not hasattr( start_dir, 'glob' ):
        return []

    # Top directory may exist only as a SCons node with Repository children.
    if not os.path.isdir( absolute_start ):
        return _file_nodes_only( start_dir.glob( pattern ) )

    discard = _as_regex( discard_pattern )
    found = []
    subdir = False

    for root, dirnames, filenames in os.walk( absolute_start ):
        if exclude_dirs_regex:
            dirnames[:] = [
                    name for name in dirnames
                    if not exclude_dirs_regex.match( name )
            ]

        if subdir and discard:
            if any( discard.match( name ) for name in filenames ):
                dirnames[:] = []
                continue

        rel = os.path.relpath( root, absolute_start )
        dir_node = _dir_child( start_dir, rel )
        globber = getattr( dir_node, 'glob', None )
        if callable( globber ):
            found.extend( _file_nodes_only( globber( pattern ) ) )

        subdir = True

    return found


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
        nodes = _file_nodes_for_matches( env, matches, rel_start, sconscript_dir )
        start_dir = _start_dir_node( env, absolute_start, sconscript_dir )
        declared = _files_from_dir_entries(
                start_dir,
                _as_regex( pattern ),
                exclude_dirs_regex=exclude_dirs_regex,
                discard_pattern=_as_regex( discard_pattern ),
        )
        if declared:
            logger.trace(
                    "Dir.entries matches = [{}]."
                    .format( colour_items( [ str( node ) for node in declared ] ) )
            )
            nodes = _merge_unique_nodes( nodes, declared )
        from_repos = _files_from_local_repository_globs(
                start_dir,
                absolute_start,
                pattern,
                exclude_dirs_regex=exclude_dirs_regex,
                discard_pattern=discard_pattern,
        )
        if from_repos:
            logger.trace(
                    "Repository Dir.glob matches = [{}]."
                    .format( colour_items( [ str( node ) for node in from_repos ] ) )
            )
            nodes = _merge_unique_nodes( nodes, from_repos )
        return nodes

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
