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
    """Exports and imports found in one sconscript file."""

    __slots__ = ( 'path', 'exports', 'imports' )

    def __init__( self, path, exports=None, imports=None ):
        self.path = path
        self.exports = set( exports or () )
        self.imports = set( imports or () )


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


def scan_sconscript_source( source, path='<sconscript>' ):
    """Parse *source* and return :class:`ScriptCoupling` for string-literal names.

    Dynamic ``Import(variable)`` forms are ignored (spike bound). ``Import('*')``
    is recorded as the literal name ``*`` so callers can treat it specially.
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

    for node in ast.walk( tree ):
        if not isinstance( node, ast.Call ):
            continue
        func = node.func
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

    return ScriptCoupling( path, exports=exports, imports=imports )


def scan_sconscript_file( path ):
    """Read and scan a sconscript path."""
    with open( path, 'r', encoding='utf-8' ) as handle:
        source = handle.read()
    return scan_sconscript_source( source, path=path )


def _norm_path( path ):
    return os.path.normpath( path )


def _discover_sconscripts_under( root ):
    """Return normalised sconscript paths under *root* (non-recursive of nest constructs)."""
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
    return [ _norm_path( p ) for p in found ]


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
        return unique

    ordered_norms = _topo_order( norm_paths, edges )
    ordered = [ _original( n ) for n in ordered_norms ]
    if ordered != unique:
        logger.debug(
                "Sconscript Export/Import order [{}]".format(
                        as_notice( ", ".join( ordered ) )
                )
        )
    return ordered


# Session registry for Cuppa ``ExportShared`` / ``ImportShared`` (survives env.Clone).
_session_shared = {}


def clear_session_shared():
    """Reset Cuppa shared exports (call once per ``Construct.build``)."""
    _session_shared.clear()


def export_shared( env, name, value ):
    """Cuppa preferred export: publish *name* for later ``ImportShared`` / native ``Import``.

    Writes the Cuppa session registry and SCons ``Export`` so either import style works
    when exporters run first.
    """
    if not isinstance( name, str ) or not name or name in BUILTIN_EXPORT_NAMES:
        raise SCons.Errors.StopError(
                "cuppa: ExportShared name must be a non-built-in string, got {!r}".format( name )
        )
    _session_shared[name] = value
    SCons.Script.Export( { name: value } )
    return value


def import_shared( env, *names ):
    """Cuppa preferred import: read names from the session registry (and SCons Export).

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

    values = []
    for name in flat:
        if name in BUILTIN_EXPORT_NAMES:
            raise SCons.Errors.StopError(
                    "cuppa: ImportShared cannot request Cuppa built-in name '{}'".format( name )
            )
        if name not in _session_shared:
            raise SCons.Errors.StopError(
                    "cuppa: ImportShared('{}') failed — no matching ExportShared "
                    "(exporter must run first)".format( name )
            )
        values.append( _session_shared[name] )
    if len( values ) == 1:
        return values[0]
    return tuple( values )


def install_methods( env ):
    """Attach ``ExportShared`` / ``ImportShared`` to a construction environment."""
    env.AddMethod( export_shared, 'ExportShared' )
    env.AddMethod( import_shared, 'ImportShared' )
