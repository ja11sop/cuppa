#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Sconscript Export/Import coupling: scan, widen, and execution order.

Discovery (which scripts exist) stays separate. This module builds a dependency
graph from static ``Export`` / ``Import`` (and Cuppa ``ExportShared`` /
``ImportShared``) names so exporters run before importers.
"""

from __future__ import annotations

import ast
import os
from collections import defaultdict

import SCons.Errors
import SCons.Script

from cuppa.log import logger
from cuppa.colourise import as_notice


# Names Cuppa already injects via ``SConscript(..., exports=...)`` each invoke.
# Importing only these does not create coupling edges between project scripts.
BUILTIN_EXPORT_NAMES = frozenset( {
        'env',
        'sconscript_env',
        'build_root',
        'artefacts_root',
        'abs_artefacts_root',
        'artifacts_root',
        'abs_artifacts_root',
        'build_dir',
        'abs_build_dir',
        'final_dir',
        'abs_final_dir',
        'common_variant_final_dir',
        'common_project_final_dir',
        'project',
} )

_CUPPA_EXPORT_METHODS = frozenset( { 'ExportShared', 'export_shared' } )
_CUPPA_IMPORT_METHODS = frozenset( { 'ImportShared', 'import_shared' } )


class ScriptCoupling( object ):
    """Exports, imports, and nested ``SConscript`` targets found in one file."""

    __slots__ = ( 'path', 'exports', 'imports', 'nested' )

    def __init__( self, path, exports=None, imports=None, nested=None ):
        self.path = path
        self.exports = set( exports or () )
        self.imports = set( imports or () )
        # Relative path strings passed to ``SConscript(...)`` (first arg), as written.
        self.nested = set( nested or () )


def _string_names_from_ast_value( node ):
    """Yield export/import names from a string Constant (or legacy Str)."""
    if isinstance( node, ast.Constant ) and isinstance( node.value, str ):
        for part in node.value.split():
            if part:
                yield part
        return
    # Python < 3.8
    if hasattr( ast, 'Str' ) and isinstance( node, ast.Str ):  # pragma: no cover
        for part in node.s.split():
            if part:
                yield part


def _names_from_call_args( args ):
    names = []
    for arg in args:
        names.extend( _string_names_from_ast_value( arg ) )
    return names


def _is_name( node, expected ):
    return isinstance( node, ast.Name ) and node.id == expected


def _method_name( node ):
    if isinstance( node, ast.Attribute ) and isinstance( node.attr, str ):
        return node.attr
    return None


def _is_sconscript_call( func ):
    """True for ``SConscript(...)`` or ``….SConscript(...)``."""
    if _is_name( func, 'SConscript' ):
        return True
    return _method_name( func ) == 'SConscript'


def _string_from_ast( node ):
    if isinstance( node, ast.Constant ) and isinstance( node.value, str ):
        return node.value
    if hasattr( ast, 'Str' ) and isinstance( node, ast.Str ):  # pragma: no cover
        return node.s
    return None


def _sconscript_target_strings( call_node ):
    """Yield string-literal script paths from the first positional ``SConscript`` arg."""
    if not call_node.args:
        return
    first = call_node.args[0]
    text = _string_from_ast( first )
    if text is not None:
        yield text
        return
    if isinstance( first, ( ast.List, ast.Tuple ) ):
        for elt in first.elts:
            text = _string_from_ast( elt )
            if text is not None:
                yield text


def scan_sconscript_source( source, path='<sconscript>' ):
    """Parse *source* and return :class:`ScriptCoupling` for string-literal names.

    Dynamic ``Import(variable)`` forms are ignored (spike bound). ``Import('*')``
    is recorded as the literal name ``*`` so callers can treat it specially.
    Literal ``SConscript('…')`` / ``SConscript(['…'])`` targets are recorded in
    ``nested`` so discovery can avoid double-running those paths.
    """
    try:
        tree = ast.parse( source, filename=path )
    except SyntaxError as exc:
        raise SCons.Errors.StopError(
                "cuppa: cannot parse sconscript [{}] for Export/Import scan: {}".format(
                        path, exc
                )
        )

    exports = set()
    imports = set()
    nested = set()

    for node in ast.walk( tree ):
        if not isinstance( node, ast.Call ):
            continue
        func = node.func
        if _is_sconscript_call( func ):
            nested.update( _sconscript_target_strings( node ) )
            continue
        names = _names_from_call_args( node.args )
        if not names:
            continue
        if _is_name( func, 'Export' ):
            exports.update( names )
        elif _is_name( func, 'Import' ):
            imports.update( names )
        else:
            method = _method_name( func )
            if method in _CUPPA_EXPORT_METHODS:
                exports.update( names )
            elif method in _CUPPA_IMPORT_METHODS:
                imports.update( names )

    return ScriptCoupling( path, exports=exports, imports=imports, nested=nested )


def scan_sconscript_file( path ):
    """Read and scan a sconscript path."""
    with open( path, 'r', encoding='utf-8' ) as handle:
        source = handle.read()
    return scan_sconscript_source( source, path=path )


def _norm_path( path ):
    return os.path.normpath( path )


def _as_project_relative( path, base_dir=None ):
    """Return a path Cuppa can use as a discovered sconscript (``./…`` form).

    Widen search often yields absolute paths from ``recursive_glob`` when
    ``search_root`` is absolute. Absolute sconscript paths produce a different
    ``sconstruct_offset_path`` / ``_build`` layout than ``./sconscript``, so a
    later ``--clean`` with ``--scripts=`` would not remove artefacts built under
    the relative path. Rebase to *base_dir* (default: cwd) and prefer a ``./``
    prefix to match Construct's discovery shape.
    """
    base_dir = base_dir if base_dir is not None else os.getcwd()
    abs_path = os.path.abspath( path )
    abs_base = os.path.abspath( base_dir )
    try:
        rel = os.path.relpath( abs_path, abs_base )
    except ValueError:
        return path
    if rel.startswith( '..' ):
        return abs_path
    if not rel.startswith( '.' + os.sep ) and rel != '.':
        rel = os.path.join( '.', rel )
    return rel


def resolve_nested_sconscript_target( caller_path, target, base_dir=None ):
    """Resolve a ``SConscript('target')`` string relative to the calling script.

    Returns a project-relative path (``./…``) when possible so it can match
    discovered sconscript entries.
    """
    if os.path.isabs( target ):
        return _as_project_relative( target, base_dir=base_dir )
    caller_dir = os.path.dirname( caller_path )
    if not caller_dir:
        caller_dir = '.'
    joined = os.path.normpath( os.path.join( caller_dir, target ) )
    return _as_project_relative( joined, base_dir=base_dir )


def nested_targets_in_set( paths, couplings_by_norm, base_dir=None ):
    """Return normpaths of *paths* that another script in the set will ``SConscript``.

    Used to drop those paths from Cuppa's outer discovery invoke list so the
    nested call (with the parent's ``exports=``) is the only evaluation.
    """
    path_norms = { _norm_path( p ) for p in paths }
    nested = set()
    for path in paths:
        coupling = couplings_by_norm.get( _norm_path( path ) )
        if coupling is None:
            continue
        for target in coupling.nested:
            resolved = resolve_nested_sconscript_target( path, target, base_dir=base_dir )
            resolved_norm = _norm_path( resolved )
            if resolved_norm in path_norms:
                nested.add( resolved_norm )
            # SCons accepts a directory meaning ``…/SConscript`` / ``…/sconscript``.
            for suffix in ( 'sconscript', 'SConscript' ):
                as_file = _norm_path( os.path.join( resolved, suffix ) )
                if as_file in path_norms:
                    nested.add( as_file )
    return nested


def exclude_nested_sconscripts( paths, couplings_by_norm, base_dir=None ):
    """Filter *paths* so scripts nested by another entry are not invoked twice."""
    if not paths:
        return paths
    nested_norms = nested_targets_in_set( paths, couplings_by_norm, base_dir=base_dir )
    if not nested_norms:
        return paths
    kept = []
    for path in paths:
        if _norm_path( path ) in nested_norms:
            logger.info(
                    "Skipping discovery invoke for [{}] — nested via SConscript "
                    "from another sconscript in this set".format( as_notice( path ) )
            )
            continue
        kept.append( path )
    return kept


def _discover_sconscripts_under( root ):
    """Return project-relative sconscript paths under *root*."""
    # Local import avoids a circular import with construct during module load.
    import re
    from cuppa import recursive_glob

    file_regex = re.compile( r'([^.]+[.])?sconscript$', re.IGNORECASE )
    discard_if_subdir_contains_regex = re.compile( r'(SC|Sc|sc)onstruct' )
    found = recursive_glob.glob(
            root,
            file_regex,
            exclude_dirs_pattern=None,
            discard_pattern=discard_if_subdir_contains_regex,
    )
    return [ _as_project_relative( p ) for p in found ]


def _coupling_edges( couplings_by_path ):
    """Return (edges, exporters, unsatisfied, collisions).

    *edges* is a list of (importer_path, exporter_path).
    *exporters* maps name -> exporter path (single).
    *unsatisfied* is a set of (importer_path, name).
    *collisions* maps name -> list of exporter paths (len > 1).
    """
    exporters = defaultdict( list )
    for path, coupling in couplings_by_path.items():
        for name in coupling.exports:
            if name in BUILTIN_EXPORT_NAMES:
                continue
            exporters[name].append( path )

    collisions = {
            name: paths for name, paths in exporters.items() if len( paths ) > 1
    }
    single = {
            name: paths[0] for name, paths in exporters.items() if len( paths ) == 1
    }

    edges = []
    unsatisfied = set()
    for path, coupling in couplings_by_path.items():
        for name in coupling.imports:
            if name in BUILTIN_EXPORT_NAMES or name == '*':
                continue
            exporter = single.get( name )
            if exporter is None:
                if name in collisions:
                    continue  # reported separately
                unsatisfied.add( ( path, name ) )
            elif exporter != path:
                edges.append( ( path, exporter ) )

    return edges, single, unsatisfied, collisions


def _topo_order( paths, edges ):
    """Stable topological order: exporters before importers; else input order."""
    index = { path: i for i, path in enumerate( paths ) }
    path_set = set( paths )
    dependents = defaultdict( set )  # exporter -> importers that need it
    indegree = { path: 0 for path in paths }

    for importer, exporter in edges:
        if importer not in path_set or exporter not in path_set:
            continue
        if importer in dependents[exporter]:
            continue
        dependents[exporter].add( importer )
        indegree[importer] += 1

    ready = sorted(
            ( path for path in paths if indegree[path] == 0 ),
            key=lambda p: index[p],
    )
    ordered = []
    while ready:
        path = ready.pop( 0 )
        ordered.append( path )
        for dependent in sorted( dependents[path], key=lambda p: index[p] ):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append( dependent )
                ready.sort( key=lambda p: index[p] )

    if len( ordered ) != len( paths ):
        remaining = [ path for path in paths if path not in set( ordered ) ]
        raise SCons.Errors.StopError(
                "cuppa: cycle in sconscript Export/Import coupling involving [{}]".format(
                        ", ".join( remaining )
                )
        )
    return ordered


def order_sconscripts( paths, search_root=None, widen=True ):
    """Return *paths* reordered so exporters run before importers.

    When an import is not satisfied by the current set and *widen* is true with a
    *search_root*, discover additional sconscripts under that root and include any
    that export a missing name (repeat until fixed point — so A→B→C chains work
    under ``--scripts=`` that named only the importer). With *widen* false (or no
    *search_root*), missing exporters raise ``StopError`` without leaving the
    current set.

    Multiple exporters for one name raise ``StopError`` (stricter than SCons
    last-wins).
    """
    if not paths:
        return []

    # Keep caller path strings (e.g. ``./sconscript``). Normpaths are only keys —
    # stripping ``./`` breaks Cuppa's sconstruct_offset_path / final_dir layout.
    unique = []
    norm_to_original = {}
    for path in paths:
        norm = _norm_path( path )
        if norm not in norm_to_original:
            norm_to_original[norm] = path
            unique.append( path )

    couplings = {}
    for path in unique:
        if os.path.isfile( path ):
            couplings[_norm_path( path )] = scan_sconscript_file( path )
        else:
            couplings[_norm_path( path )] = ScriptCoupling( path )

    def _original( norm ):
        return norm_to_original.get( norm, norm )

    edges, _single, unsatisfied, collisions = _coupling_edges( couplings )

    if widen and search_root and unsatisfied:
        search_root = _norm_path( search_root )
        candidates = _discover_sconscripts_under( search_root )
        # Fixed-point widen: newly pulled exporters may Import further names.
        while unsatisfied:
            needed_names = { name for _path, name in unsatisfied }
            added = False
            for candidate in candidates:
                candidate = _as_project_relative( candidate )
                candidate_norm = _norm_path( candidate )
                if candidate_norm in couplings:
                    continue
                if not os.path.isfile( candidate ):
                    continue
                coupling = scan_sconscript_file( candidate )
                if not ( coupling.exports & needed_names ):
                    continue
                couplings[candidate_norm] = coupling
                norm_to_original[candidate_norm] = candidate
                unique.append( candidate )
                added = True
                logger.info(
                        "Widened sconscript set to exporter [{}] for Import of [{}]".format(
                                as_notice( candidate ),
                                as_notice( ", ".join( sorted( coupling.exports & needed_names ) ) ),
                        )
                )
            if not added:
                break
            edges, _single, unsatisfied, collisions = _coupling_edges( couplings )

    if collisions:
        parts = []
        for name, exporters in sorted( collisions.items() ):
            parts.append(
                    "'{}' from [{}]".format(
                            name,
                            ", ".join( sorted( _original( p ) for p in exporters ) ),
                    )
            )
        raise SCons.Errors.StopError(
                "cuppa: multiple sconscripts Export the same name (Cuppa refuses "
                "SCons last-wins under discovery): {}".format( "; ".join( parts ) )
        )

    if unsatisfied:
        parts = [
                "{} imports '{}'".format( _original( path ), name )
                for path, name in sorted( unsatisfied )
        ]
        if widen:
            hint = "project tree under the sconstruct"
        else:
            hint = (
                    "current sconscript set "
                    "(omit --strict-sconscript-exports to widen and pull exporters)"
            )
        raise SCons.Errors.StopError(
                "cuppa: sconscript Import not satisfied by any Export in the "
                "{}: {}".format( hint, "; ".join( parts ) )
        )

    norm_paths = [ _norm_path( p ) for p in unique ]
    if not edges:
        ordered = unique
    else:
        ordered_norms = _topo_order( norm_paths, edges )
        ordered = [ _original( n ) for n in ordered_norms ]
        if ordered != unique:
            logger.debug(
                    "Sconscript Export/Import order [{}]".format(
                            as_notice( ", ".join( ordered ) )
                    )
            )

    # Drop paths another script in this set will nest via SConscript(...), so
    # discovery does not evaluate them a second time without the parent's exports.
    return exclude_nested_sconscripts( ordered, couplings )


# Session registry for Cuppa ``ExportShared`` / ``ImportShared``.
# Keyed by toolchain/variant/arch/abi scope so dbg and rel (and multi-toolchain)
# exports of the same name do not overwrite each other. This is a primary reason
# the Cuppa API exists above native SCons Export/Import (global last-wins pool).
_session_shared = {}

# Paths already evaluated for a given invoke scope (tool_variant_dir). Used so a
# dynamic ``SConscript(...)`` that the static scan missed still suppresses a
# second Cuppa discovery invoke for the same path.
_invoked_sconscripts = set()
_invoke_scope_stack = []
_original_sconscript = None
_dedupe_project_root = None


def shared_export_scope( env ):
    """Return the scope key for shared exports on *env* (tool_variant_dir when set)."""
    key = env.get( 'tool_variant_dir' )
    if key:
        return key
    variant = env.get( 'variant' )
    if hasattr( variant, 'name' ):
        variant_name = variant.name()
    else:
        variant_name = str( variant or '' )
    toolchain = env.get( 'active_toolchain' )
    if toolchain is not None and hasattr( toolchain, 'name' ):
        toolchain_name = toolchain.name()
    else:
        toolchain_name = ''
    return os.path.join(
            str( toolchain_name ),
            str( variant_name ),
            str( env.get( 'target_arch' ) or '' ),
            str( env.get( 'abi' ) or '' ),
    )


def clear_session_shared():
    """Reset all Cuppa shared exports (call once per ``Construct.build``)."""
    _session_shared.clear()


def clear_invoked_sconscripts():
    """Reset the per-build invoked-path registry (call once per ``Construct.build``)."""
    global _dedupe_project_root
    _invoked_sconscripts.clear()
    _invoke_scope_stack[:] = []
    _dedupe_project_root = None


def set_dedupe_project_root( root ):
    """Project root used to resolve nested ``SConscript`` targets for dedupe."""
    global _dedupe_project_root
    _dedupe_project_root = root


def push_invoke_scope( scope ):
    _invoke_scope_stack.append( scope )


def pop_invoke_scope():
    if _invoke_scope_stack:
        _invoke_scope_stack.pop()


def current_invoke_scope():
    if _invoke_scope_stack:
        return _invoke_scope_stack[-1]
    return ''


def mark_sconscript_invoked( path, scope=None ):
    """Record that *path* has been evaluated for *scope* (default: current)."""
    if scope is None:
        scope = current_invoke_scope()
    _invoked_sconscripts.add( ( scope, _norm_path( path ) ) )


def was_sconscript_invoked( path, scope=None ):
    """True if *path* was already evaluated for *scope* this build."""
    if scope is None:
        scope = current_invoke_scope()
    return ( scope, _norm_path( path ) ) in _invoked_sconscripts


def _paths_from_sconscript_call_args( args, kwargs ):
    """Best-effort extract of script path strings from a live ``SConscript`` call."""
    targets = []
    if args:
        first = args[0]
        if isinstance( first, str ):
            targets.append( first )
        elif isinstance( first, ( list, tuple ) ):
            targets.extend( part for part in first if isinstance( part, str ) )
    for key in ( 'dirs', 'name' ):
        value = kwargs.get( key )
        if isinstance( value, str ):
            targets.append( value )
        elif isinstance( value, ( list, tuple ) ):
            targets.extend( part for part in value if isinstance( part, str ) )
    return targets


def _mark_live_sconscript_target( target, scope ):
    """Mark a live ``SConscript`` target using the project root, not VariantDir cwd."""
    root = _dedupe_project_root or os.getcwd()
    candidates = []
    if os.path.isabs( target ):
        candidates.append( target )
    else:
        candidates.append( os.path.join( root, target ) )
        candidates.append( os.path.abspath( target ) )
    marked_any = False
    for cand in candidates:
        if os.path.isfile( cand ):
            mark_sconscript_invoked( _as_project_relative( cand, base_dir=root ), scope=scope )
            marked_any = True
            break
        if os.path.isdir( cand ):
            for suffix in ( 'sconscript', 'SConscript' ):
                as_file = os.path.join( cand, suffix )
                if os.path.isfile( as_file ):
                    mark_sconscript_invoked(
                            _as_project_relative( as_file, base_dir=root ),
                            scope=scope,
                    )
                    marked_any = True
            if marked_any:
                break
    if not marked_any:
        mark_sconscript_invoked(
                _as_project_relative( os.path.join( root, target ), base_dir=root ),
                scope=scope,
        )


def _wrapped_sconscript( *args, **kwargs ):
    """SCons ``SConscript`` wrapper that records nested targets for dedupe."""
    scope = current_invoke_scope()
    for target in _paths_from_sconscript_call_args( args, kwargs ):
        _mark_live_sconscript_target( target, scope )
    return _original_sconscript( *args, **kwargs )


def install_sconscript_dedupe_wrapper():
    """Install the ``SCons.Script.SConscript`` wrapper once for this process."""
    global _original_sconscript
    if _original_sconscript is not None:
        return
    _original_sconscript = SCons.Script.SConscript
    SCons.Script.SConscript = _wrapped_sconscript


def export_shared( env, name, value ):
    """Cuppa preferred export: publish *name* for this toolchain/variant scope.

    Values are stored per ``tool_variant_dir`` so ``--dbg`` and ``--rel`` (and
    multiple toolchains) keep distinct bindings for the same name. Also updates
    SCons ``Export`` for best-effort native ``Import`` — that global pool is
    **not** variant-safe; prefer ``ImportShared``.
    """
    if not isinstance( name, str ) or not name or name in BUILTIN_EXPORT_NAMES:
        raise SCons.Errors.StopError(
                "cuppa: ExportShared name must be a non-built-in string, got {!r}".format( name )
        )
    scope = shared_export_scope( env )
    _session_shared.setdefault( scope, {} )[name] = value
    SCons.Script.Export( { name: value } )
    return value


def import_shared( env, *names ):
    """Cuppa preferred import: read names for this toolchain/variant scope.

    Returns one value, or a tuple when multiple names are requested.
    """
    flat = []
    for name in names:
        if isinstance( name, str ):
            flat.extend( part for part in name.split() if part )
        else:
            raise SCons.Errors.StopError(
                    "cuppa: ImportShared names must be strings, got {!r}".format( name )
            )
    if not flat:
        raise SCons.Errors.StopError( "cuppa: ImportShared requires at least one name" )

    scope = shared_export_scope( env )
    bucket = _session_shared.get( scope ) or {}
    values = []
    for name in flat:
        if name in BUILTIN_EXPORT_NAMES:
            raise SCons.Errors.StopError(
                    "cuppa: ImportShared cannot request Cuppa built-in name '{}'".format( name )
            )
        if name not in bucket:
            raise SCons.Errors.StopError(
                    "cuppa: ImportShared('{}') failed for scope [{}] — no matching "
                    "ExportShared (exporter must run first for this toolchain/variant)".format(
                            name, scope
                    )
            )
        values.append( bucket[name] )
    if len( values ) == 1:
        return values[0]
    return tuple( values )


def install_methods( env ):
    """Attach ``ExportShared`` / ``ImportShared`` to a construction environment."""
    env.AddMethod( export_shared, 'ExportShared' )
    env.AddMethod( import_shared, 'ImportShared' )
