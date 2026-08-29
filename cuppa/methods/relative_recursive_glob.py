
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
#   including nested declared paths). Also walks logical directories that exist
#   locally and/or in SCons Repositories (Dir.glob per logical dir, including
#   repo-only subdirectory trees). exclude_dirs / discard_pattern apply across
#   the union of local and remote names.
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


def _listdir_dirs_and_files( abspath ):
    """Return ``(dir_names, file_names)`` for an on-disk directory, or empty sets."""
    dirs = set()
    files = set()
    if not abspath or not os.path.isdir( abspath ):
        return dirs, files
    try:
        for name in os.listdir( abspath ):
            path = os.path.join( abspath, name )
            if os.path.isdir( path ):
                dirs.add( name )
            elif os.path.isfile( path ):
                files.add( name )
    except OSError:
        pass
    return dirs, files


def _entry_dir_names( dir_node ):
    names = set()
    entries = getattr( dir_node, 'entries', None ) or {}
    for name, entry in entries.items():
        if name in ( '.', '..' ):
            continue
        if _is_dir_node( entry ):
            names.add( name )
    return names


def _repository_peer_dirs( dir_node ):
    """Peer directories from ``get_all_rdirs()`` excluding ``dir_node`` itself."""
    get_all = getattr( dir_node, 'get_all_rdirs', None )
    if not callable( get_all ):
        return []
    peers = []
    for rdir in get_all():
        if rdir is dir_node:
            continue
        peers.append( rdir )
    return peers


def _logical_child_dir_names( dir_node, local_abs ):
    """Union of subdirectory basenames from local disk, entries, and Repositories."""
    names, _files = _listdir_dirs_and_files( local_abs )
    names |= _entry_dir_names( dir_node )
    for rdir in _repository_peer_dirs( dir_node ):
        r_abs = getattr( rdir, 'abspath', None )
        r_dirs, _r_files = _listdir_dirs_and_files( r_abs )
        names |= r_dirs
        names |= _entry_dir_names( rdir )
    return names


def _logical_file_names( dir_node, local_abs ):
    """Union of file basenames from local disk and Repository peers (for discard)."""
    _dirs, names = _listdir_dirs_and_files( local_abs )
    for rdir in _repository_peer_dirs( dir_node ):
        r_abs = getattr( rdir, 'abspath', None )
        _r_dirs, r_files = _listdir_dirs_and_files( r_abs )
        names |= r_files
    return names


def _files_from_repository_tree(
        start_dir,
        absolute_start,
        pattern,
        exclude_dirs_regex=None,
        discard_pattern=None,
):
    """Full Repository parity: ``Dir.glob`` at each logical directory.

    Walks the union of local and Repository subdirectory names under
    ``start_dir``, so repo-only trees (no local ``nested/``) are included.
    ``exclude_dirs`` / ``discard_pattern`` use the union of local and remote
    basenames at each logical path. Local on-disk files are also returned by
    ``Dir.glob`` and are deduped by the caller against the disk-walk merge.
    """
    if not hasattr( start_dir, 'glob' ):
        return []

    discard = _as_regex( discard_pattern )
    found = []
    visited = set()

    def walk( dir_node, local_abs, rel, is_subdir ):
        rel_key = ( rel or os.curdir ).replace( '\\', '/' )
        if rel_key in visited:
            return
        visited.add( rel_key )

        if is_subdir and discard:
            if any( discard.match( name ) for name in _logical_file_names( dir_node, local_abs ) ):
                return

        globber = getattr( dir_node, 'glob', None )
        if callable( globber ):
            found.extend( _file_nodes_only( globber( pattern ) ) )

        for name in sorted( _logical_child_dir_names( dir_node, local_abs ) ):
            if exclude_dirs_regex and exclude_dirs_regex.match( name ):
                continue
            child_rel = name if rel_key in ( os.curdir, '.' ) else os.path.join( rel, name )
            child_local = (
                    os.path.join( local_abs, name ) if local_abs is not None else None
            )
            walk( _dir_child( dir_node, name ), child_local, child_rel, True )

    local_abs = absolute_start if os.path.isdir( absolute_start ) else None
    walk( start_dir, local_abs, os.curdir, False )
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
        from_repos = _files_from_repository_tree(
                start_dir,
                absolute_start,
                pattern,
                exclude_dirs_regex=exclude_dirs_regex,
                discard_pattern=discard_pattern,
        )
        if from_repos:
            logger.trace(
                    "Repository tree Dir.glob matches = [{}]."
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
