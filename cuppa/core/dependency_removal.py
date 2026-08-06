#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency removal — --remove-dependencies / --purge-dependencies / --wipe-*
#-------------------------------------------------------------------------------

"""Remove or wipe selected dependency trees under ``dependencies_root``.

``--purge-*`` also deletes matching archives under ``downloads_root``. ``--wipe-*`` clears
the whole extract (bypassing ``storage_clean`` product-only behaviour) plus matching
downloads. ``--force-wipe-dependencies=name/qualifier`` targets list-tree leaves regardless
of referenced state; ``--force-wipe-unreferenced-dependencies`` clears orphan trees and
downloads. Develop working copies stay put. See
``design/plans/removal-options.md`` §4.13 / Phase 4 / #146.
"""

from __future__ import annotations

import fnmatch
import os
import sys
from collections import namedtuple

from cuppa.colourise import (
    as_emphasised,
    as_info,
    as_remove_error,
    as_remove_notice,
    as_subdued,
    as_warning,
)
from cuppa.core import dependency_inventory, dependency_storage
from cuppa.core.storage_actions import dry_run
from cuppa.log import logger
from cuppa.utility import storage


INDENT = '  '
RULE = '-'
SIZE_WIDTH = 8
# Long enough for ``relative_age`` ("10 months ago" … "24 months ago" are 13 chars).
AGE_WIDTH = 13
REMARK_WIDTH = 9

RemovalTarget = namedtuple(
    'RemovalTarget',
    [
        'dependency', 'path', 'qualifier', 'tool_variant', 'storage_type',
        'size_bytes', 'label', 'extra_paths',
    ],
)

Leftover = namedtuple(
    'Leftover',
    [
        'dependency', 'path', 'qualifier', 'tool_variant', 'size_bytes', 'label',
        'storage_type',
    ],
)
Leftover.__new__.__defaults__ = ( None, )

DevelopSkip = namedtuple(
    'DevelopSkip',
    [ 'dependency', 'path', 'reason' ],
)

UnknownDependencyNames = namedtuple(
    'UnknownDependencyNames',
    [ 'unknown', 'project_used' ],
)

DownloadTarget = namedtuple(
    'DownloadTarget',
    [
        'dependency', 'path', 'qualifier', 'tool_variant', 'storage_type',
        'size_bytes', 'label', 'missing',
    ],
)


def wants_remove( cuppa_env ):
    return bool(
            cuppa_env.get( 'remove_dependencies' ) or cuppa_env.get( 'remove_all_dependencies' )
    )


def wants_purge( cuppa_env ):
    return bool( cuppa_env.get( 'purge_dependencies' ) or cuppa_env.get( 'purge_all_dependencies' ) )


def wants_wipe( cuppa_env ):
    """Selection wipe: named ``--wipe-dependencies`` or ``--force-wipe-all-dependencies``."""
    return bool(
            cuppa_env.get( 'wipe_dependencies' )
            or cuppa_env.get( 'force_wipe_all_dependencies' )
    )


def wants_force_wipe( cuppa_env ):
    return bool( cuppa_env.get( 'force_wipe_dependencies' ) )


def wants_force_wipe_unreferenced( cuppa_env ):
    return bool( cuppa_env.get( 'force_wipe_unreferenced_dependencies' ) )


def conflicting_dependency_modes( cuppa_env ):
    """Return mode names when more than one of remove/purge/wipe/force-wipe is set."""
    modes = []
    if wants_remove( cuppa_env ):
        modes.append( 'remove' )
    if wants_purge( cuppa_env ):
        modes.append( 'purge' )
    if wants_wipe( cuppa_env ):
        modes.append( 'wipe' )
    if wants_force_wipe( cuppa_env ):
        modes.append( 'force-wipe' )
    if wants_force_wipe_unreferenced( cuppa_env ):
        modes.append( 'force-wipe-unreferenced' )
    if len( modes ) > 1:
        return modes
    return None


def purge_and_remove_combined( cuppa_env ):
    """True when any purge flag is combined with any remove flag."""
    return bool(
            wants_purge( cuppa_env ) and wants_remove( cuppa_env )
    )


def parse_dependency_names( spec ):
    """Split a comma-separated remove / purge / wipe dependency name list."""
    if not spec:
        return []
    if isinstance( spec, ( list, tuple ) ):
        spec = spec[0] if spec else ''
    names = []
    for part in str( spec ).split( ',' ):
        name = part.strip()
        if name:
            names.append( name )
    return names


def known_dependency_names( cuppa_env ):
    """Registry keys available for instantiation (built-ins + project + plugins)."""
    factories = cuppa_env.get( 'dependencies' ) or {}
    return sorted( factories.keys() )


def project_dependency_names( cuppa_env ):
    """Names this sconstruct uses: ``default_dependencies`` ∪ ``declared_dependencies``.

    Auto-scanned built-ins (``boost``, ``qt4``, …) appear in the full registry but are only
    removable when the project names them in defaults or in ``dependencies=[…]``.
    """
    names = []
    seen = set()
    for source in (
            cuppa_env.get( 'default_dependencies' ) or [],
            cuppa_env.get( 'declared_dependencies' ) or [],
    ):
        for name in source:
            if name and name not in seen:
                seen.add( name )
                names.append( name )
    return names


def resolve_requested_names( cuppa_env ):
    """Return ``(names, error)`` for the current remove, purge, or wipe flags.

    ``error`` is ``None`` on success, a string for empty input, or
    :class:`UnknownDependencyNames` when names are not project-used.
    ``--*-all-dependencies`` with no project-used names yields an empty list.

    Accepts shared ``[selector]name[/qualifier]`` tokens (§4.15). Selectors and
    leaf qualifiers are stored on ``cuppa_env['dependency_tokens']`` for later
    filtering; this function still returns the resolved project-used **names**.
    """
    from cuppa.core import dependency_tokens

    project_used = project_dependency_names( cuppa_env )
    project_set = set( project_used )

    if (
            cuppa_env.get( 'remove_all_dependencies' )
            or cuppa_env.get( 'purge_all_dependencies' )
            or cuppa_env.get( 'force_wipe_all_dependencies' )
    ):
        cuppa_env['dependency_tokens'] = [
                ( None, name, None ) for name in project_used
        ]
        return list( project_used ), None

    spec = (
            cuppa_env.get( 'wipe_dependencies' )
            or cuppa_env.get( 'purge_dependencies' )
            or cuppa_env.get( 'remove_dependencies' )
    )
    tokens, error = dependency_tokens.parse_dependency_tokens( spec )
    if error:
        if error == "no dependency tokens given":
            return [], (
                    "no dependency names given (use --remove-dependencies=name, "
                    "--purge-dependencies=name, --wipe-dependencies=name, "
                    "--remove-all-dependencies, --purge-all-dependencies, or "
                    "--force-wipe-all-dependencies)"
            )
        return [], error

    resolved_tokens = []
    unknown = []
    ordered_names = []
    seen_names = set()
    for storage_type, name, qualifier in tokens:
        if dependency_tokens.is_wildcard_pattern( name ):
            matched = [
                    project for project in project_used
                    if dependency_tokens.name_matches( name, project )
            ]
            if not matched:
                unknown.append( name )
                continue
            for project in matched:
                resolved_tokens.append( ( storage_type, project, qualifier ) )
                if project not in seen_names:
                    seen_names.add( project )
                    ordered_names.append( project )
            continue
        if name not in project_set:
            unknown.append( name )
            continue
        resolved_tokens.append( ( storage_type, name, qualifier ) )
        if name not in seen_names:
            seen_names.add( name )
            ordered_names.append( name )

    if unknown:
        return [], UnknownDependencyNames(
                unknown=tuple( unknown ),
                project_used=tuple( project_used ),
        )

    cuppa_env['dependency_tokens'] = resolved_tokens
    return ordered_names, None


def _dependencies_root( cuppa_env ):
    root = cuppa_env.get( 'dependencies_root' )
    if not root:
        raise storage.StorageError( "dependencies_root is not set" )
    return os.path.abspath( os.path.expanduser( root ) )


def _downloads_root( cuppa_env ):
    root = cuppa_env.get( 'downloads_root' ) or cuppa_env.get( 'cache_root' )
    if not root:
        return None
    if not os.path.isabs( root ):
        root = os.path.abspath(
                os.path.join( cuppa_env.get( 'sconstruct_dir' ) or os.getcwd(), root )
        )
    return os.path.abspath( os.path.expanduser( root ) )


def _download_file_size( path ):
    try:
        return int( os.lstat( path ).st_size )
    except OSError:
        return 0


def _refuse_suspicious_dependencies_root( root, sconstruct_dir ):
    if storage.is_suspicious_root( root ):
        raise storage.StorageError(
            "refusing to remove under suspicious dependencies root [{}]".format( root )
        )
    if sconstruct_dir and storage.real_path( root ) == storage.real_path( sconstruct_dir ):
        raise storage.StorageError(
            "refusing to remove under the sconstruct directory [{}]".format( root )
        )


def _measure_bytes( path ):
    if not os.path.isdir( path ):
        return 0
    try:
        return int( storage.directory_stats( path ).bytes )
    except ( OSError, storage.StorageError ):
        return 0


def _path_label( dependency, qualifier, tool_variant ):
    parts = [ dependency ]
    if qualifier:
        parts.append( str( qualifier ) )
    if tool_variant:
        parts.append( str( tool_variant ) )
    return ' / '.join( parts )


def _sibling_leftovers( root, target, remove_reals ):
    """Other on-disk trees for the same identity that the current selection did not hit."""
    leftovers = []
    real = storage.real_path( target.path )
    try:
        relative = os.path.relpath( real, root )
    except ValueError:
        return leftovers
    parts = [ p for p in relative.split( os.sep ) if p and p != '.' ]
    if not parts:
        return leftovers

    if target.storage_type == 'gitlab' and len( parts ) >= 3:
        package, version = parts[1], parts[2]
        try:
            top_names = os.listdir( root )
        except OSError:
            return leftovers
        for name in sorted( top_names ):
            if not dependency_storage.looks_like_tool_variant_dir( name ):
                continue
            candidate = os.path.join( root, name, package, version )
            if not os.path.isdir( candidate ):
                continue
            cand_real = storage.real_path( candidate )
            if cand_real in remove_reals or cand_real == real:
                continue
            leftovers.append( Leftover(
                dependency=target.dependency,
                path=candidate,
                qualifier=version,
                tool_variant=name,
                size_bytes=_measure_bytes( candidate ),
                label=_path_label( target.dependency, version, name ),
                storage_type=target.storage_type,
            ) )
        return leftovers

    if target.storage_type == 'conan' and len( parts ) >= 3 and parts[0] == 'conan':
        # conan/<name>/<fingerprint> — leave other fingerprints for the same name.
        dep_name = parts[1]
        parent = os.path.join( root, 'conan', dep_name )
        if not os.path.isdir( parent ):
            return leftovers
        try:
            fingerprints = os.listdir( parent )
        except OSError:
            return leftovers
        for fingerprint in sorted( fingerprints ):
            candidate = os.path.join( parent, fingerprint )
            if not os.path.isdir( candidate ):
                continue
            cand_real = storage.real_path( candidate )
            if cand_real in remove_reals or cand_real == real:
                continue
            leftovers.append( Leftover(
                dependency=target.dependency,
                path=candidate,
                qualifier=fingerprint[:16],
                tool_variant=None,
                size_bytes=_measure_bytes( candidate ),
                label=_path_label( target.dependency, fingerprint[:16], None ),
                storage_type=target.storage_type,
            ) )
        return leftovers

    # Location / archive (and unknown top-level): siblings share the stem (name before @).
    if dependency_storage.looks_like_tool_variant_dir( parts[0] ):
        return leftovers
    top = parts[0]
    stem, _qual = dependency_storage.split_location_folder_name( top )
    try:
        top_names = os.listdir( root )
    except OSError:
        return leftovers
    for name in sorted( top_names ):
        other_stem, other_qual = dependency_storage.split_location_folder_name( name )
        if other_stem != stem:
            continue
        candidate = os.path.join( root, name )
        if not os.path.isdir( candidate ):
            continue
        cand_real = storage.real_path( candidate )
        if cand_real in remove_reals or cand_real == real:
            continue
        # Product clean inside an extract: the extract root itself is not a leftover sibling.
        if real.startswith( cand_real + os.sep ):
            continue
        if cand_real.startswith( real + os.sep ):
            continue
        leftovers.append( Leftover(
            dependency=target.dependency,
            path=candidate,
            qualifier=other_qual,
            tool_variant=None,
            size_bytes=_measure_bytes( candidate ),
            label=_path_label( target.dependency, other_qual or '@', None ),
            storage_type=target.storage_type,
        ) )
    return leftovers


def enumerate_archive_product_dirs( home ):
    """List b2 stage leaves and folded ``bin.*`` toolset units under a Boost home.

    Stage products remain one leaf per ``build…/<toolchain>/<variant>/<arch>``.
    Bin products are one unit per ``bin.<abi>/<toolset-token>`` (nested Boost.Build
    dirs for that toolset folded together for leftovers / reporting). Empty ``bin.<abi>``
    directories with no toolset children are omitted.
    """
    from cuppa.dependencies.boost.library_naming import (
        b2_toolset_family_label,
        b2_toolset_family_token,
        enumerate_b2_build_dir_toolset_products,
        is_b2_toolset_dir_name,
    )

    products = []
    if not home or not os.path.isdir( home ):
        return products
    try:
        names = os.listdir( home )
    except OSError:
        return products
    for name in sorted( names ):
        path = os.path.join( home, name )
        if not os.path.isdir( path ):
            continue
        if name.startswith( 'bin.' ):
            by_family = {}
            for product in enumerate_b2_build_dir_toolset_products( path ):
                token = os.path.basename( product )
                if token in ( 'debug', 'release' ):
                    token = os.path.basename( os.path.dirname( product ) )
                if not is_b2_toolset_dir_name( token ):
                    token = os.path.basename( product )
                family = b2_toolset_family_token( token )
                by_family.setdefault( family, [] ).append( product )
            if by_family:
                for family in sorted( by_family ):
                    products.append( {
                        'path': path,
                        'paths': by_family[family],
                        'tool_variant': b2_toolset_family_label( family ),
                        'kind': 'bin_toolset',
                    } )
            # Empty bin.<abi> husks stay on disk but are not leftover rows.
            continue
        if not name.startswith( 'build' ):
            continue
        try:
            toolchains = os.listdir( path )
        except OSError:
            continue
        for toolchain_name in sorted( toolchains ):
            tpath = os.path.join( path, toolchain_name )
            if not os.path.isdir( tpath ):
                continue
            try:
                variants = os.listdir( tpath )
            except OSError:
                continue
            for variant in sorted( variants ):
                vpath = os.path.join( tpath, variant )
                if not os.path.isdir( vpath ):
                    continue
                try:
                    arches = os.listdir( vpath )
                except OSError:
                    continue
                for arch in sorted( arches ):
                    apath = os.path.join( vpath, arch )
                    if os.path.isdir( apath ):
                        products.append( {
                            'path': path,
                            'paths': [ os.path.abspath( apath ) ],
                            'tool_variant': '{}/{}/{}'.format(
                                    toolchain_name, variant, arch
                            ),
                            'kind': 'stage',
                        } )
    return products


def _collect_storage_clean( construct, cuppa_env, names, selections ):
    """Call optional ``storage_clean`` on each named dependency for each selection.

    Returns ``{ name: { 'paths', 'targets', 'extract', 'supported', ... } }``
    only for dependencies that implement ``storage_clean`` (even when empty).
    """
    factories = cuppa_env.get( 'dependencies' ) or {}
    by_name = {}
    for name in names:
        factory = factories.get( name )
        if factory is None:
            continue
        for selection in selections:
            env = dependency_storage._scons_env_from_selection( selection )
            if env is None:
                continue
            try:
                instance = factory( env )
            except Exception:
                continue
            if instance is None:
                continue
            method = getattr( instance, 'storage_clean', None )
            if not callable( method ):
                for attr in ( '_package', '_location' ):
                    inner = getattr( instance, attr, None )
                    if inner is None:
                        continue
                    method = getattr( inner, 'storage_clean', None )
                    if callable( method ):
                        break
                else:
                    continue
            try:
                result = method( env, selection )
            except Exception:
                continue
            if result is None:
                continue
            entry = by_name.setdefault( name, {
                'paths': [],
                'targets': [],
                'extract': None,
                'supported': True,
                'storage_type': 'archive',
                'qualifier': None,
            } )
            if result.get( 'extract' ):
                entry['extract'] = os.path.abspath( os.path.expanduser( result['extract'] ) )

            structured = list( result.get( 'targets' ) or [] )
            if not structured and result.get( 'paths' ):
                # Compat: plain path list → one target per path.
                structured = [
                        { 'paths': [ path ], 'label': None, 'tool_variant': None }
                        for path in result['paths']
                ]

            for spec in structured:
                paths = []
                for path in spec.get( 'paths' ) or []:
                    if not path:
                        continue
                    abs_path = os.path.abspath( os.path.expanduser( path ) )
                    if abs_path not in paths:
                        paths.append( abs_path )
                    if abs_path not in entry['paths']:
                        entry['paths'].append( abs_path )
                if not paths:
                    continue
                entry['targets'].append( {
                    'paths': paths,
                    'label': spec.get( 'label' ),
                    'tool_variant': spec.get( 'tool_variant' ),
                } )

            qualifier = getattr( instance, 'storage_qualifier', None )
            if callable( qualifier ):
                try:
                    entry['qualifier'] = qualifier()
                except Exception:
                    pass
            storage_type = dependency_storage.storage_type_for_owned_path(
                    instance,
                    entry.get( 'extract' ) or ( entry['paths'][0] if entry['paths'] else '' ),
                    cuppa_env.get( 'dependencies_root' ),
            )
            if storage_type and storage_type != 'unknown':
                entry['storage_type'] = storage_type
    return by_name


def _product_leftovers( dependency, extract, home, remove_reals, storage_type, qualifier, root=None ):
    """Muted leftovers: other stage/bin product units under the same extract home."""
    leftovers = []
    for candidate in enumerate_archive_product_dirs( home ):
        if isinstance( candidate, dict ):
            paths = candidate.get( 'paths' ) or [ candidate['path'] ]
            display_path = candidate['path']
            tool_variant = candidate.get( 'tool_variant' )
            kind = candidate.get( 'kind' )
        else:
            paths = [ candidate ]
            display_path = candidate
            tool_variant = None
            kind = None
        remaining = []
        for path in paths:
            cand_real = storage.real_path( path )
            if cand_real in remove_reals:
                continue
            if any(
                    cand_real == remove
                    or cand_real.startswith( remove + os.sep )
                    or remove.startswith( cand_real + os.sep )
                    for remove in remove_reals
            ):
                continue
            remaining.append( path )
        if not remaining:
            continue
        size_bytes = sum( _measure_bytes( path ) for path in remaining )
        try:
            label = os.path.relpath( display_path, extract or home )
        except ValueError:
            label = os.path.basename( display_path )
        label = label.replace( '\\', '/' )
        if tool_variant and kind in ( 'bin_toolset', 'stage' ):
            label = "{} [{}]".format( label, tool_variant )
        if root and extract:
            extract_rel = _relative_removal_path( extract, root )
            if extract_rel and not label.startswith( extract_rel + '/' ) and label != extract_rel:
                label = "{}/{}".format( extract_rel, label )
        leftovers.append( Leftover(
            dependency=dependency,
            path=remaining[0],
            qualifier=qualifier,
            tool_variant=( tool_variant or label ).replace( '\\', '/' ),
            size_bytes=size_bytes,
            label=label,
            storage_type='archive',
        ) )
    return leftovers


def collect_removal_plan( construct, cuppa_env, names, wipe=False ):
    """Build remove targets, leftovers, develop skips, and resolve skips for ``names``.

    When ``wipe`` is True, archive extracts are queued for full deletion even when the
    dependency implements ``storage_clean`` (product-only clean is skipped).
    """
    root = _dependencies_root( cuppa_env )
    selections = dependency_storage.selection_build_envs( construct, cuppa_env )
    owned, skips = dependency_storage.resolve_named_dependencies(
            construct, cuppa_env, names, selections=selections
    )
    # Wipe clears the extract; do not consult storage_clean product-only paths.
    clean_by_name = (
            {} if wipe else _collect_storage_clean( construct, cuppa_env, names, selections )
    )

    develop_skips = []
    targets = []
    seen_remove = set()
    # Extract roots skipped because storage_clean owns product removal for this name.
    clean_extract_reals = set()
    for name, clean in clean_by_name.items():
        extract = clean.get( 'extract' )
        if extract and os.path.isdir( extract ):
            clean_extract_reals.add( storage.real_path( extract ) )

    for item in owned:
        if item.category == 'develop' or item.develop:
            develop_skips.append( DevelopSkip(
                dependency=item.dependency,
                path=item.path,
                reason='develop working copy is never removed',
            ) )
            continue
        if item.category not in ( 'dependencies', 'cached' ):
            continue
        if not item.path:
            continue
        path = os.path.abspath( os.path.expanduser( item.path ) )
        if not os.path.lexists( path ):
            continue
        real = storage.real_path( path )
        # When storage_clean is supported, leave the archive extract in place.
        if item.dependency in clean_by_name and item.category == 'dependencies':
            if real in clean_extract_reals or (
                    clean_by_name[item.dependency].get( 'extract' )
                    and real == storage.real_path( clean_by_name[item.dependency]['extract'] )
            ):
                continue
        if real in seen_remove:
            continue
        # Containment before we measure or delete.
        storage.ensure_contained( path, root, what="dependency path" )
        if os.path.islink( path ):
            raise storage.StorageError(
                "refusing to remove through symlink [{}]".format( path )
            )
        seen_remove.add( real )
        targets.append( RemovalTarget(
            dependency=item.dependency,
            path=path,
            qualifier=item.qualifier,
            tool_variant=item.tool_variant,
            storage_type=item.storage_type,
            size_bytes=_measure_bytes( path ),
            label=None,
            extra_paths=(),
        ) )

    # Selection-scoped product dirs from storage_clean (possibly multi-path targets).
    from cuppa.dependencies.boost.library_naming import _prune_nested_paths
    for name, clean in clean_by_name.items():
        extract = clean.get( 'extract' )
        specs = list( clean.get( 'targets' ) or [] )
        if not specs and clean.get( 'paths' ):
            specs = [
                    { 'paths': [ path ], 'label': None, 'tool_variant': None }
                    for path in clean['paths']
            ]
        for spec in specs:
            paths = [
                    path for path in ( spec.get( 'paths' ) or [] )
                    if path and os.path.lexists( path )
            ]
            if not paths:
                continue
            paths = _prune_nested_paths( paths )
            if not paths:
                continue
            primary = paths[0]
            extra = tuple( paths[1:] )
            real = storage.real_path( primary )
            if real in seen_remove:
                # Still register extras for containment/removal if primary already queued.
                continue
            if extract:
                for path in paths:
                    storage.ensure_contained( path, extract, what="dependency product path" )
            for path in paths:
                storage.ensure_contained( path, root, what="dependency path" )
                if os.path.islink( path ):
                    raise storage.StorageError(
                        "refusing to remove through symlink [{}]".format( path )
                    )
            seen_remove.add( real )
            for path in extra:
                seen_remove.add( storage.real_path( path ) )

            label = spec.get( 'label' )
            tool_variant = spec.get( 'tool_variant' )
            if not label:
                try:
                    label = os.path.relpath( primary, extract or primary )
                except ValueError:
                    label = os.path.basename( primary )
                label = label.replace( '\\', '/' )
            # Report paths relative to the dependencies root (include extract folder).
            if extract:
                extract_rel = _relative_removal_path( extract, root )
                if extract_rel and not label.startswith( extract_rel + '/' ) and label != extract_rel:
                    label = "{}/{}".format( extract_rel, label )
            if tool_variant and '[{}]'.format( tool_variant ) not in label:
                display = "{} [{}]".format( label, tool_variant )
            else:
                display = label

            size_bytes = sum( _measure_bytes( path ) for path in paths )
            targets.append( RemovalTarget(
                dependency=name,
                path=primary,
                qualifier=clean.get( 'qualifier' ),
                tool_variant=tool_variant or label,
                storage_type=clean.get( 'storage_type' ) or 'archive',
                size_bytes=size_bytes,
                label=display,
                extra_paths=extra,
            ) )

    leftovers = []
    leftover_seen = set()
    for target in targets:
        for leftover in _sibling_leftovers( root, target, seen_remove ):
            real = storage.real_path( leftover.path )
            if real in leftover_seen:
                continue
            leftover_seen.add( real )
            leftovers.append( leftover )

    # Other variant products left under the same extract home.
    for name, clean in clean_by_name.items():
        extract = clean.get( 'extract' )
        if not extract:
            continue
        # Boost products live under clean/ or patched/ inside the extract.
        homes = []
        for sub in ( 'clean', 'patched' ):
            candidate = os.path.join( extract, sub )
            if os.path.isdir( candidate ):
                homes.append( candidate )
        if not homes and os.path.isdir( extract ):
            homes.append( extract )
        for home in homes:
            for leftover in _product_leftovers(
                    name,
                    extract,
                    home,
                    seen_remove,
                    clean.get( 'storage_type' ) or 'archive',
                    clean.get( 'qualifier' ),
                    root=root,
            ):
                real = storage.real_path( leftover.path )
                if real in leftover_seen or real in seen_remove:
                    continue
                leftover_seen.add( real )
                leftovers.append( leftover )

    # Deepest paths first so parents prune cleanly.
    targets.sort( key=lambda item: item.path.count( os.sep ), reverse=True )

    archives = _archive_contexts( root, clean_by_name, targets, leftovers )
    return {
        'root': root,
        'targets': targets,
        'leftovers': leftovers,
        'archives': archives,
        'develop_skips': develop_skips,
        'skips': skips,
        'owned': owned,
    }


def collect_purge_downloads( construct, cuppa_env, names, owned=None ):
    """Queue selection-scoped download files and leftover sibling archives.

    Missing archives are recorded (``missing=True``) and are not a failure.
    Develop working copies are never deleted; downloads for that name may still purge.
    """
    from cuppa.core import dependency_downloads, dependency_identity

    downloads_root = _downloads_root( cuppa_env )
    if not downloads_root:
        return [], [], None

    if owned is None:
        selections = dependency_storage.selection_build_envs( construct, cuppa_env )
        owned, _skips = dependency_storage.resolve_named_dependencies(
                construct, cuppa_env, names, selections=selections
        )

    targets = []
    seen = set()

    def queue_download( path, dependency, qualifier, tool_variant, storage_type, missing=False ):
        path = os.path.abspath( os.path.expanduser( path ) )
        key = storage.real_path( path ) if os.path.lexists( path ) else path
        if key in seen:
            return
        seen.add( key )
        exists = os.path.lexists( path )
        if exists:
            storage.ensure_contained( path, downloads_root, what="download path" )
            if os.path.islink( path ):
                raise storage.StorageError(
                    "refusing to remove through symlink [{}]".format( path )
                )
        is_missing = missing or not exists
        targets.append( DownloadTarget(
            dependency=dependency,
            path=path,
            qualifier=qualifier,
            tool_variant=tool_variant,
            storage_type=storage_type,
            size_bytes=0 if is_missing else _download_file_size( path ),
            label=os.path.basename( path.rstrip( '\\/' ) ),
            missing=is_missing,
        ) )

    queued_any_for = set()
    for item in owned:
        if item.category != 'downloads' or not item.path:
            continue
        queue_download(
                item.path, item.dependency, item.qualifier, item.tool_variant,
                item.storage_type, missing=not os.path.lexists( item.path ),
        )
        queued_any_for.add( item.dependency )

    for item in owned:
        if item.category not in ( 'dependencies', 'cached' ) or not item.path:
            continue
        found = dependency_identity.find_cached_download(
                downloads_root,
                storage_type=item.storage_type,
                path=item.path,
                version=item.qualifier,
                tool_variant=item.tool_variant,
        )
        if found:
            queue_download(
                    found, item.dependency, item.qualifier, item.tool_variant,
                    item.storage_type,
            )
            queued_any_for.add( item.dependency )
        elif (
                item.storage_type in ( 'gitlab', 'archive' )
                and item.dependency not in queued_any_for
        ):
            placeholder = os.path.join(
                    downloads_root, '.absent',
                    item.dependency,
                    str( item.tool_variant or item.qualifier or 'selected' ),
            )
            queue_download(
                    placeholder, item.dependency, item.qualifier, item.tool_variant,
                    item.storage_type, missing=True,
            )
            queued_any_for.add( item.dependency )

    leftovers = []
    leftover_seen = set()
    for target in targets:
        if target.missing or not os.path.isfile( target.path ):
            continue
        meta = dependency_downloads.describe_download_file( target.path, downloads_root )
        if meta.get( 'type' ) != 'gitlab':
            continue
        package_dir = os.path.dirname( target.path )
        try:
            names_on_disk = sorted( os.listdir( package_dir ) )
        except OSError:
            continue
        for name in names_on_disk:
            candidate = os.path.join( package_dir, name )
            if not os.path.isfile( candidate ):
                continue
            real = storage.real_path( candidate )
            if real in seen or real in leftover_seen:
                continue
            leftover_seen.add( real )
            sibling_meta = dependency_downloads.describe_download_file(
                    candidate, downloads_root
            )
            leftovers.append( DownloadTarget(
                dependency=target.dependency,
                path=candidate,
                qualifier=target.qualifier or sibling_meta.get( 'qualifier' ),
                tool_variant=sibling_meta.get( 'tool_variant' ) or name,
                storage_type=target.storage_type or 'gitlab',
                size_bytes=_download_file_size( candidate ),
                label=name,
                missing=False,
            ) )

    return targets, leftovers, downloads_root


def _infer_item_storage_type( item ):
    storage_type = getattr( item, 'storage_type', None )
    if storage_type:
        return storage_type
    tool_variant = str( getattr( item, 'tool_variant', None ) or '' ).split( '/' )[0]
    if tool_variant and dependency_storage.looks_like_tool_variant_dir( tool_variant ):
        return 'gitlab'
    return 'unknown'


def _product_dicts_for_pairing( items ):
    products = []
    for item in items:
        if not item or not getattr( item, 'path', None ):
            continue
        products.append( {
            'path': item.path,
            'type': _infer_item_storage_type( item ),
            'dependency': item.dependency,
            'short_name': item.dependency,
            'qualifier': item.qualifier,
            'tool_variant': item.tool_variant,
            'item': item,
        } )
    return products


def _pair_downloads_to_items( download_items, extract_items, downloads_root ):
    """Map download identity key → paired extract items using list-downloads matching."""
    from cuppa.core import dependency_downloads

    if not downloads_root or not download_items:
        return {}, set()

    products = _product_dicts_for_pairing( extract_items )
    paired = {}
    used = set()
    for download in download_items:
        if os.path.lexists( download.path ):
            meta = dependency_downloads.describe_download_file( download.path, downloads_root )
        else:
            meta = {
                'type': getattr( download, 'storage_type', None ) or 'archive',
                'dependency': download.dependency,
                'short_name': download.dependency,
                'package_folder': None,
                'qualifier': download.qualifier,
                'tool_variant': download.tool_variant,
                'archive': download.label or os.path.basename(
                        str( download.path ).rstrip( '\\/' )
                ),
            }
        if download.dependency:
            meta['dependency'] = download.dependency
            if meta.get( 'type' ) == 'gitlab':
                meta['short_name'] = download.dependency
                meta['package_folder'] = meta.get( 'package_folder' )
        if download.qualifier is not None:
            meta['qualifier'] = download.qualifier
        if download.tool_variant:
            meta['tool_variant'] = download.tool_variant
        matches = dependency_downloads.matching_products( meta, products )
        key = storage.real_path( download.path ) if os.path.lexists( download.path ) else download.path
        for product in matches:
            real = storage.real_path( product['path'] ) if os.path.lexists( product['path'] ) else product['path']
            if real in used:
                continue
            used.add( real )
            paired.setdefault( key, [] ).append( product['item'] )
    return paired, used


def _path_under_extract( path, extract_real ):
    real = storage.real_path( path )
    return real == extract_real or real.startswith( extract_real + os.sep )


def _archive_contexts( root, clean_by_name, targets, leftovers ):
    """Per-extract size context so removal reports can match ``--list-dependencies``."""
    archives = []
    for name, clean in clean_by_name.items():
        extract = clean.get( 'extract' )
        if not extract or not os.path.isdir( extract ):
            continue
        extract_real = storage.real_path( extract )
        extract_bytes = _measure_bytes( extract )
        product_bytes = 0
        for target in targets:
            if target.dependency != name:
                continue
            if _path_under_extract( target.path, extract_real ):
                product_bytes += target.size_bytes
        for leftover in leftovers:
            if leftover.dependency != name:
                continue
            if _path_under_extract( leftover.path, extract_real ):
                product_bytes += leftover.size_bytes
        source_bytes = max( 0, extract_bytes - product_bytes )
        age_text, age_epoch = _age_for_path( root, extract )
        archives.append( {
            'dependency': name,
            'extract': extract,
            'extract_bytes': extract_bytes,
            'source_bytes': source_bytes,
            'qualifier': clean.get( 'qualifier' ),
            'storage_type': clean.get( 'storage_type' ) or 'archive',
            'age_text': age_text,
            'age_epoch': age_epoch,
        } )
    return archives


def _rule_line( width ):
    return INDENT + ( RULE * max( width, 20 ) )


def _format_size( size_bytes ):
    return storage.human_size( size_bytes ).rjust( SIZE_WIDTH )


def _relative_removal_path( path, root ):
    try:
        relative = os.path.relpath( path, root )
    except ValueError:
        return storage.display_path( path )
    if relative.startswith( '..' ):
        return storage.display_path( path )
    return relative.replace( '\\', '/' )


def _age_for_path( root, path ):
    """LAST USED text and epoch for a tree (resolve inventory, else directory mtime)."""
    try:
        key = dependency_inventory.entry_key_for_path( path )
        entry = dependency_inventory.load_entry( root, key )
    except Exception:
        entry = None
    if entry and entry.get( 'last_used_source' ) == 'resolve':
        stamp = entry.get( 'last_used' )
        text = dependency_inventory.format_age( stamp )
        # Best-effort epoch for rollups.
        try:
            from datetime import datetime, timezone
            when = datetime.strptime(
                    stamp.replace( 'Z', '' ), '%Y-%m-%dT%H:%M:%S'
            ).replace( tzinfo=timezone.utc )
            return text, when.timestamp()
        except ( ValueError, AttributeError, TypeError ):
            return text, None
    try:
        mtime = os.path.getmtime( path )
        return storage.relative_age( mtime ), mtime
    except OSError:
        return '-', None


def _leaf_result( outcomes_by_path, path, planning, removing ):
    if not removing:
        return 'left'
    outcome = outcomes_by_path.get( storage.real_path( path ), {} )
    result = outcome.get( 'result', 'removed' if planning else 'pending' )
    if planning and result == 'removed':
        return 'would_rm'
    if result == 'removed':
        return 'removed'
    if result == 'failed':
        return 'failed'
    return result


def _remark_for_result( result ):
    if result == 'would_rm':
        return 'would rm'
    if result in ( 'removed', 'failed' ):
        return result
    return ''


def _parent_rollup_result( child_results ):
    """Roll removal status to the identity when every child is a removal candidate."""
    actionable = [ r for r in child_results if r != 'left' ]
    if not actionable:
        return ''
    if any( r == 'left' for r in child_results ):
        # Mixed leave + remove: status stays on leaves (matches the sketch).
        return ''
    if any( r == 'failed' for r in actionable ):
        if all( r == 'failed' for r in actionable ):
            return 'failed'
        return ''
    if all( r == 'would_rm' for r in actionable ):
        return 'would rm'
    if all( r == 'removed' for r in actionable ):
        return 'removed'
    return ''


def _product_leaf( item, outcomes_by_path, planning, root, removing ):
    age_text, age_epoch = _age_for_path( root, item.path )
    return {
        'path': item.path,
        'rel_path': _relative_removal_path( item.path, root ),
        'display': item.label or _relative_removal_path( item.path, root ),
        'size_bytes': item.size_bytes,
        'qualifier': item.qualifier,
        'tool_variant': item.tool_variant,
        'age_text': age_text,
        'age_epoch': age_epoch,
        'removing': removing,
        'result': _leaf_result( outcomes_by_path, item.path, planning, removing ),
        'extra_paths': list( getattr( item, 'extra_paths', () ) or () ),
        'kind': 'product',
        'children': [],
    }


def _source_assets_leaf( archive, root ):
    return {
        'path': archive['extract'],
        'rel_path': _relative_removal_path( archive['extract'], root ),
        'display': 'source assets',
        'size_bytes': archive['source_bytes'],
        'qualifier': archive.get( 'qualifier' ),
        'tool_variant': '',
        'age_text': archive.get( 'age_text' ) or '-',
        'age_epoch': archive.get( 'age_epoch' ),
        'removing': False,
        'result': 'left',
        'extra_paths': [],
        'kind': 'source_assets',
        'children': [],
    }


def _extract_rollup_status( children ):
    removing = [
            child for child in children
            if child.get( 'removing' ) and child.get( 'result' ) != 'absent'
    ]
    staying = [
            child for child in children
            if not child.get( 'removing' ) and child.get( 'result' ) != 'absent'
    ]
    if not removing:
        return False, 'left'
    if staying:
        return False, 'left'
    results = [ child['result'] for child in removing ]
    if any( result == 'failed' for result in results ):
        if all( result == 'failed' for result in results ):
            return True, 'failed'
        return True, 'left'
    if all( result == 'would_rm' for result in results ):
        return True, 'would_rm'
    if all( result == 'removed' for result in results ):
        return True, 'removed'
    return True, results[0] if results else 'left'


def _extract_rollup_mark( children ):
    removing = [
            child for child in children
            if child.get( 'removing' ) and child.get( 'result' ) != 'absent'
    ]
    staying = [
            child for child in children
            if not child.get( 'removing' ) and child.get( 'result' ) != 'absent'
    ]
    failed = [ child for child in removing if child.get( 'result' ) == 'failed' ]
    if not removing:
        mark = storage.outcome_triple( 'full', 'none' )
    elif failed and len( failed ) == len( removing ) and not staying:
        mark = storage.outcome_triple( 'full', 'failed' )
    elif failed:
        mark = storage.outcome_triple( 'full', 'mixed' )
    elif staying:
        mark = storage.outcome_triple( 'partial', 'removed' )
    else:
        mark = storage.outcome_triple( 'full', 'removed' )
    return storage.with_heavy_marks( mark )


def _build_extract_rollup( archive, product_leaves, root ):
    from cuppa.core.dependency_identity import with_extract_mark

    extract_real = storage.real_path( archive['extract'] )
    children = [ _source_assets_leaf( archive, root ) ]
    used = set()
    for leaf in product_leaves:
        if _path_under_extract( leaf['path'], extract_real ):
            children.append( leaf )
            used.add( storage.real_path( leaf['path'] ) )
    children.sort( key=lambda leaf: (
            0 if leaf.get( 'kind' ) == 'source_assets' else 1,
            0 if leaf.get( 'removing' ) else 1,
            leaf.get( 'tool_variant' ) or '',
            leaf.get( 'rel_path' ) or '',
    ) )
    rel_path = _relative_removal_path( archive['extract'], root )
    removing, result = _extract_rollup_status( children )
    return {
        'path': archive['extract'],
        'rel_path': rel_path,
        'display': with_extract_mark( rel_path ),
        'size_bytes': archive['extract_bytes'],
        'qualifier': archive.get( 'qualifier' ),
        'tool_variant': '',
        'age_text': archive.get( 'age_text' ) or '-',
        'age_epoch': archive.get( 'age_epoch' ),
        'removing': removing,
        'result': result,
        'extra_paths': [],
        'kind': 'extract',
        'children': children,
        'rollup': True,
        'dependency': archive['dependency'],
    }, used


def _extract_child_leaf( item, outcomes_by_path, planning, root, removing ):
    from cuppa.core.dependency_identity import with_extract_mark

    age_text, age_epoch = _age_for_path( root, item.path )
    display = item.label or _relative_removal_path( item.path, root )
    return {
        'path': item.path,
        'rel_path': _relative_removal_path( item.path, root ),
        'display': with_extract_mark( display ),
        'size_bytes': item.size_bytes,
        'qualifier': item.qualifier,
        'tool_variant': item.tool_variant,
        'age_text': age_text,
        'age_epoch': age_epoch,
        'removing': removing,
        'result': _leaf_result( outcomes_by_path, item.path, planning, removing ),
        'extra_paths': list( getattr( item, 'extra_paths', () ) or () ),
        'kind': 'extract',
        'children': [],
    }


def _download_leaf(
        download, downloads_root, outcomes_by_path, planning, children=None, removing=None,
):
    if getattr( download, 'missing', False ):
        display = '(no archive to delete)'
        age_text, age_epoch = '-', None
        result = 'absent'
        removing = False
        rel_path = display
    else:
        display = download.label or os.path.basename( download.path.rstrip( '\\/' ) )
        age_text, age_epoch = _age_for_path( downloads_root, download.path )
        if removing is None:
            removing = True
        result = _leaf_result( outcomes_by_path, download.path, planning, removing )
        rel_path = _relative_removal_path( download.path, downloads_root )
    return {
        'path': download.path,
        'rel_path': rel_path,
        'display': display,
        'size_bytes': download.size_bytes,
        'qualifier': download.qualifier,
        'tool_variant': download.tool_variant,
        'age_text': age_text,
        'age_epoch': age_epoch,
        'removing': removing,
        'result': result,
        'extra_paths': [],
        'kind': 'download',
        'children': list( children or [] ),
    }


def _group_removal_rows(
        targets, leftovers, outcomes_by_path, planning, root, archives=None,
        downloads=None, download_leftovers=None, downloads_root=None,
        staying_extracts=None,
):
    """Group targets and leftovers by storage type and dependency for the removal tree."""
    from cuppa.core.dependency_storage import normalise_storage_type
    from cuppa.core.dependency_tree import TYPE_LABELS

    groups = {}
    archives = archives or []
    downloads = list( downloads or [] )
    download_leftovers = list( download_leftovers or [] )
    staying_extracts = list( staying_extracts or [] )

    def ensure( dependency, storage_type=None ):
        storage_type = normalise_storage_type( storage_type ) or storage_type or 'unknown'
        key = ( storage_type, dependency )
        if key not in groups:
            groups[key] = {
                'dependency': dependency,
                'storage_type': storage_type,
                'qualifiers': set(),
                'leaves': [],
                'extract_bytes': None,
                'download_bytes': 0,
            }
        return groups[key]

    product_leaves = [
            _product_leaf( target, outcomes_by_path, planning, root, True )
            for target in targets
    ]
    product_leaves.extend(
            _product_leaf( leftover, outcomes_by_path, planning, root, False )
            for leftover in leftovers
    )

    rollups = []
    used_product_reals = set()
    rollup_by_extract = {}
    extract_pair_items = []
    for archive in archives:
        node, consumed = _build_extract_rollup( archive, product_leaves, root )
        rollups.append( node )
        used_product_reals |= consumed
        extract_real = storage.real_path( archive['extract'] )
        rollup_by_extract[extract_real] = node
        extract_pair_items.append( RemovalTarget(
                dependency=archive['dependency'],
                path=archive['extract'],
                qualifier=archive.get( 'qualifier' ),
                tool_variant='',
                storage_type='archive',
                size_bytes=archive['extract_bytes'],
                label=os.path.basename( str( archive['extract'] ).rstrip( '\\/' ) ),
                extra_paths=(),
        ) )
        group = ensure( archive['dependency'], 'archive' )
        if archive.get( 'qualifier' ):
            group['qualifiers'].add( archive['qualifier'] )
        group['extract_bytes'] = archive['extract_bytes']

    staying_for_pair = [
            item for item in staying_extracts
            if storage.real_path( item.path ) not in rollup_by_extract
    ]
    unpaired_targets = [
            target for target in targets
            if storage.real_path( target.path ) not in used_product_reals
    ]
    unpaired_leftovers = [
            leftover for leftover in leftovers
            if storage.real_path( leftover.path ) not in used_product_reals
    ]
    pair_pool = (
            extract_pair_items + unpaired_targets + unpaired_leftovers + staying_for_pair
    )
    paired_selected, used_pair_reals = _pair_downloads_to_items(
            downloads, pair_pool, downloads_root,
    )
    paired_leftover, used_leftover_reals = _pair_downloads_to_items(
            download_leftovers, pair_pool, downloads_root,
    )
    used_pair_reals |= used_leftover_reals
    used_rollup_reals = set()
    target_ids = { id( target ) for target in targets }

    def children_for_paired( download, paired_map, leftover_mode=False ):
        key = (
                storage.real_path( download.path )
                if os.path.lexists( download.path ) else download.path
        )
        children = []
        for item in paired_map.get( key, [] ):
            item_real = storage.real_path( item.path )
            rollup = rollup_by_extract.get( item_real )
            if rollup is not None:
                children.append( rollup )
                used_rollup_reals.add( item_real )
                continue
            removing = ( not leftover_mode ) and ( id( item ) in target_ids )
            children.append( _extract_child_leaf(
                    item, outcomes_by_path, planning, root, removing,
            ) )
        return children

    for download in downloads:
        group = ensure( download.dependency, download.storage_type )
        if download.qualifier:
            group['qualifiers'].add( download.qualifier )
        group['leaves'].append( _download_leaf(
                download, downloads_root or root, outcomes_by_path, planning,
                children=children_for_paired( download, paired_selected ),
        ) )
        group['download_bytes'] += download.size_bytes

    for leftover_dl in download_leftovers:
        group = ensure( leftover_dl.dependency, leftover_dl.storage_type )
        if leftover_dl.qualifier:
            group['qualifiers'].add( leftover_dl.qualifier )
        group['leaves'].append( _download_leaf(
                leftover_dl, downloads_root or root, outcomes_by_path, planning,
                children=children_for_paired(
                        leftover_dl, paired_leftover, leftover_mode=True,
                ),
                removing=False,
        ) )
        group['download_bytes'] += leftover_dl.size_bytes

    for node in rollups:
        real = storage.real_path( node['path'] )
        if real in used_rollup_reals:
            continue
        group = ensure( node['dependency'], 'archive' )
        if node.get( 'qualifier' ):
            group['qualifiers'].add( node['qualifier'] )
        group['leaves'].append( node )

    for target in unpaired_targets:
        real = storage.real_path( target.path )
        if real in used_pair_reals:
            continue
        group = ensure( target.dependency, target.storage_type )
        if target.qualifier:
            group['qualifiers'].add( target.qualifier )
        group['leaves'].append(
                _product_leaf( target, outcomes_by_path, planning, root, True )
        )

    for leftover in unpaired_leftovers:
        real = storage.real_path( leftover.path )
        if real in used_pair_reals:
            continue
        group = ensure(
                leftover.dependency,
                getattr( leftover, 'storage_type', None ),
        )
        if leftover.qualifier:
            group['qualifiers'].add( leftover.qualifier )
        group['leaves'].append(
                _product_leaf( leftover, outcomes_by_path, planning, root, False )
        )

    for group in groups.values():
        kind_order = { 'download': 0, 'extract': 1, 'source_assets': 2, 'product': 3 }
        group['leaves'].sort( key=lambda leaf: (
                kind_order.get( leaf.get( 'kind' ), 9 ),
                leaf.get( 'tool_variant' ) or '',
                leaf.get( 'qualifier' ) or '',
                leaf['rel_path'],
        ) )
        quals = group['qualifiers']
        group['parent_qualifier'] = next( iter( quals ) ) if len( quals ) == 1 else None

    type_order = { key: index for index, ( key, _label ) in enumerate( TYPE_LABELS ) }
    return sorted( groups.values(), key=lambda group: (
            type_order.get( group['storage_type'], 99 ),
            ( group['dependency'] or '' ).lower(),
    ) )


def _collect_leaf_results( leaves ):
    results = []
    for leaf in leaves:
        if leaf.get( 'result' ) != 'absent':
            results.append( leaf['result'] )
        results.extend( _collect_leaf_results( leaf.get( 'children' ) or [] ) )
    return results


def _mark_for_leaf( leaf, check, ballot ):
    if leaf.get( 'rollup' ):
        return _extract_rollup_mark( leaf.get( 'children' ) or [] )
    if leaf['result'] == 'failed':
        return ballot
    if leaf['removing']:
        return check
    return '-'


def _flatten_removal_leaves( leaves, tee, elbow, pipe, gap, check, ballot, prefix='' ):
    rows = []
    labels = []
    for index, leaf in enumerate( leaves ):
        last = index == len( leaves ) - 1
        connector = elbow if last else tee
        branch = prefix + connector
        result = leaf['result']
        remark = _remark_for_result( result )
        mark = _mark_for_leaf( leaf, check, ballot )
        display = leaf.get( 'display' ) or leaf['rel_path']
        # Connectors already include a trailing space; keep a single space before the mark.
        label = "{}{} {}".format( branch, mark, display )
        labels.append( label )
        rows.append( {
            'kind': 'leaf',
            'size': _format_size( leaf['size_bytes'] ),
            'age': ( leaf['age_text'] or '-' ).ljust( AGE_WIDTH ),
            'remark': remark.ljust( REMARK_WIDTH ),
            'label': label,
            'branch': branch,
            'mark': mark,
            'display': display,
            'rel_path': leaf['rel_path'],
            'result': result,
            'removing': leaf['removing'],
            'remark_text': remark,
        } )
        children = leaf.get( 'children' ) or []
        if children:
            child_prefix = prefix + ( gap if last else pipe )
            child_rows, child_labels = _flatten_removal_leaves(
                    children, tee, elbow, pipe, gap, check, ballot, child_prefix,
            )
            rows.extend( child_rows )
            labels.extend( child_labels )
    return rows, labels


def _group_total_bytes( group ):
    download_bytes = group.get( 'download_bytes' ) or 0
    if group.get( 'extract_bytes' ) is not None:
        return group['extract_bytes'] + download_bytes
    total_bytes = sum( leaf['size_bytes'] for leaf in group['leaves'] )
    for leaf in group['leaves']:
        total_bytes += sum(
                child['size_bytes'] for child in ( leaf.get( 'children' ) or [] )
        )
    return total_bytes


def _leaf_tree_bytes( leaf ):
    total = int( leaf.get( 'size_bytes' ) or 0 )
    for child in leaf.get( 'children' ) or []:
        total += _leaf_tree_bytes( child )
    return total


def _collect_action_remaining_bytes( leaves ):
    """Sum wiped/removing vs remaining bytes without double-counting extract trees."""
    wiped = 0
    remaining = 0
    for leaf in leaves or []:
        children = leaf.get( 'children' ) or []
        if children:
            child_wiped, child_remaining = _collect_action_remaining_bytes( children )
            wiped += child_wiped
            remaining += child_remaining
            # Download / paired archive rows contribute their own file size.
            if leaf.get( 'kind' ) == 'download':
                if leaf.get( 'removing' ) and leaf.get( 'result' ) in (
                        'would_rm', 'removed', 'failed',
                ):
                    wiped += int( leaf.get( 'size_bytes' ) or 0 )
                elif leaf.get( 'result' ) != 'absent':
                    remaining += int( leaf.get( 'size_bytes' ) or 0 )
            continue
        if leaf.get( 'result' ) == 'absent':
            continue
        size = int( leaf.get( 'size_bytes' ) or 0 )
        if leaf.get( 'removing' ) and leaf.get( 'result' ) in (
                'would_rm', 'removed', 'failed',
        ):
            wiped += size
        else:
            remaining += size
    return wiped, remaining


def _max_age_from_leaves( leaves ):
    """Return ``(age_text, age_epoch)`` using the most recent child age."""
    best_epoch = None
    best_text = None
    for leaf in leaves or []:
        epoch = leaf.get( 'age_epoch' )
        if epoch is not None and ( best_epoch is None or epoch > best_epoch ):
            best_epoch = epoch
            best_text = leaf.get( 'age_text' ) or '-'
        child_text, child_epoch = _max_age_from_leaves( leaf.get( 'children' ) or [] )
        if child_epoch is not None and ( best_epoch is None or child_epoch > best_epoch ):
            best_epoch = child_epoch
            best_text = child_text
    return best_text or ( ' ' * AGE_WIDTH ).strip(), best_epoch


def _format_age_cell( age_text, age_epoch ):
    if age_epoch is None:
        return ' ' * AGE_WIDTH
    text = age_text or '-'
    return text.ljust( AGE_WIDTH )


def _selection_mark_for_leaves( leaves ):
    """Return ``(mark_or_empty, remark, fully_removing, partially_removing)``.

    Untouched parents (nothing going) use ``---``, matching extract rollups.
    """
    removing = []
    staying = []

    def walk( nodes ):
        for leaf in nodes or []:
            if leaf.get( 'result' ) == 'absent':
                continue
            children = leaf.get( 'children' ) or []
            if children:
                walk( children )
                continue
            if leaf.get( 'removing' ):
                removing.append( leaf )
            else:
                staying.append( leaf )

    walk( leaves )
    if not removing:
        if staying:
            # Same language as extract ``[E]`` when nothing under it is selected.
            return storage.outcome_triple( 'full', 'none' ), '', False, False
        return '', '', False, False
    failed = [ leaf for leaf in removing if leaf.get( 'result' ) == 'failed' ]
    if failed and len( failed ) == len( removing ) and not staying:
        mark = storage.with_heavy_marks( storage.outcome_triple( 'full', 'failed' ) )
        return mark, 'failed', True, False
    if failed:
        mark = storage.with_heavy_marks( storage.outcome_triple( 'full', 'mixed' ) )
        return mark, '', False, True
    if staying:
        mark = storage.with_heavy_marks( storage.outcome_triple( 'partial', 'removed' ) )
        return mark, '', False, True
    mark = storage.with_heavy_marks( storage.outcome_triple( 'full', 'removed' ) )
    results = [ leaf.get( 'result' ) for leaf in removing ]
    remark = _parent_rollup_result( results )
    return mark, remark, True, False


def _versions_from_group( group ):
    """Split group leaves into ``(qualifier_or_None, leaves)`` buckets."""
    from cuppa.core.dependency_identity import display_qualifier

    by_qual = {}
    order = []
    storage_type = group.get( 'storage_type' ) or 'archive'
    for leaf in group.get( 'leaves' ) or []:
        raw = leaf.get( 'qualifier' )
        key = raw if raw not in ( None, '' ) else None
        if key not in by_qual:
            by_qual[key] = []
            order.append( key )
        by_qual[key].append( leaf )
    versions = []
    for key in order:
        if key is None:
            label = None
        else:
            label = display_qualifier( key, storage_type )
        versions.append( {
            'qualifier': key,
            'label': label,
            'leaves': by_qual[key],
        } )
    return versions


def _spacer_render_row( branch='' ):
    return {
        'kind': 'spacer',
        'size': ' ' * SIZE_WIDTH,
        'age': ' ' * AGE_WIDTH,
        'remark': ' ' * REMARK_WIDTH,
        'label': branch,
        'branch': branch,
    }


def _write_removal_tree(
        out, targets, leftovers, outcomes_by_path, planning, root, archives=None,
        downloads=None, download_leftovers=None, downloads_root=None,
        staying_extracts=None, summary_label=None, action_label=None,
):
    """Hierarchical removal table: summary → type → identity → version → leaves."""
    from cuppa.core.dependency_tree import TYPE_LABELS

    downloads = list( downloads or [] )
    download_leftovers = list( download_leftovers or [] )
    staying_extracts = list( staying_extracts or [] )
    if not targets and not leftovers and not archives and not downloads and not download_leftovers:
        return

    tee, elbow, pipe, gap = storage.glyphs()
    check = storage.with_heavy_marks( storage.selected_mark() )
    ballot = storage.with_heavy_marks( storage.failed_mark() )
    groups = _group_removal_rows(
            targets, leftovers, outcomes_by_path, planning, root, archives=archives,
            downloads=downloads, download_leftovers=download_leftovers,
            downloads_root=downloads_root, staying_extracts=staying_extracts,
    )
    type_labels = dict( TYPE_LABELS )

    header = "{}{}  {}  {}  {}".format(
            INDENT,
            "SIZE".rjust( SIZE_WIDTH ),
            "LAST USED".ljust( AGE_WIDTH ),
            "REMARK".ljust( REMARK_WIDTH ),
            "DEPENDENCY",
    )
    dep_pad = SIZE_WIDTH + 2 + AGE_WIDTH + 2 + REMARK_WIDTH + 2

    body_lines = []
    rendered = []

    all_leaves = []
    for group in groups:
        all_leaves.extend( group['leaves'] )
    action_bytes, remaining_bytes = _collect_action_remaining_bytes( all_leaves )
    total_bytes = action_bytes + remaining_bytes
    total_age_text, total_age_epoch = _max_age_from_leaves( all_leaves )

    action_leaves = []
    remaining_leaves = []

    def _partition_leaves( leaves, into_action, into_remaining ):
        for leaf in leaves or []:
            children = leaf.get( 'children' ) or []
            if children:
                _partition_leaves( children, into_action, into_remaining )
                if leaf.get( 'kind' ) == 'download':
                    if leaf.get( 'removing' ) and leaf.get( 'result' ) in (
                            'would_rm', 'removed', 'failed',
                    ):
                        into_action.append( leaf )
                    elif leaf.get( 'result' ) != 'absent':
                        into_remaining.append( leaf )
                continue
            if leaf.get( 'result' ) == 'absent':
                continue
            if leaf.get( 'removing' ) and leaf.get( 'result' ) in (
                    'would_rm', 'removed', 'failed',
            ):
                into_action.append( leaf )
            else:
                into_remaining.append( leaf )

    _partition_leaves( all_leaves, action_leaves, remaining_leaves )
    action_age_text, action_age_epoch = _max_age_from_leaves( action_leaves )
    remaining_age_text, remaining_age_epoch = _max_age_from_leaves( remaining_leaves )

    if not summary_label:
        names = sorted( {
                ( group.get( 'dependency' ) or '' )
                for group in groups if group.get( 'dependency' )
        } )
        summary_label = "related dependencies for {}".format(
                ', '.join( names ) if names else 'selection'
        )
    if not action_label:
        action_label = 'removing' if planning else 'removed'

    # Root + action + remaining under a synthetic root connector set.
    body_lines.append( summary_label )
    rendered.append( {
        'kind': 'parent',
        'size': _format_size( total_bytes ),
        'age': _format_age_cell( total_age_text, total_age_epoch ),
        'remark': ' ' * REMARK_WIDTH,
        'label': summary_label,
        'parent_remark': '',
        'level': 'summary',
        'fully_removing': False,
        'partially_removing': False,
        'mark': '',
    } )

    # Spacer under the summary root (matches --list-dependencies section spacing).
    body_lines.append( pipe )
    rendered.append( _spacer_render_row( pipe ) )

    body_lines.append( "{}{}".format( tee, action_label ) )
    rendered.append( {
        'kind': 'parent',
        'size': _format_size( action_bytes ),
        'age': _format_age_cell( action_age_text, action_age_epoch ),
        'remark': ' ' * REMARK_WIDTH,
        'label': "{}{}".format( tee, action_label ),
        'parent_remark': '',
        'level': 'action',
        'fully_removing': True,
        'partially_removing': False,
        'mark': '',
        'name': action_label,
        'branch': tee,
    } )

    body_lines.append( "{}{}".format( tee, 'remaining' ) )
    rendered.append( {
        'kind': 'parent',
        'size': _format_size( remaining_bytes ),
        'age': _format_age_cell( remaining_age_text, remaining_age_epoch ),
        'remark': ' ' * REMARK_WIDTH,
        'label': "{}{}".format( tee, 'remaining' ),
        'parent_remark': '',
        'level': 'remaining',
        'fully_removing': False,
        'partially_removing': False,
        'mark': '',
        'name': 'remaining',
        'branch': tee,
    } )

    body_lines.append( pipe )
    rendered.append( _spacer_render_row( pipe ) )

    # Type clusters hang from the summary root after action/remaining.
    type_clusters = []
    index = 0
    while index < len( groups ):
        storage_type = groups[index].get( 'storage_type' ) or 'unknown'
        cluster = []
        while index < len( groups ) and (
                groups[index].get( 'storage_type' ) or 'unknown'
        ) == storage_type:
            cluster.append( groups[index] )
            index += 1
        type_clusters.append( ( storage_type, cluster ) )

    for type_index, ( storage_type, cluster ) in enumerate( type_clusters ):
        last_type = type_index == len( type_clusters ) - 1
        type_connector = elbow if last_type else tee
        type_prefix = gap if last_type else pipe
        type_label = type_labels.get( storage_type, storage_type )
        type_leaves = []
        for group in cluster:
            type_leaves.extend( group['leaves'] )
        type_bytes = sum( _group_total_bytes( group ) for group in cluster )
        type_age_text, type_age_epoch = _max_age_from_leaves( type_leaves )

        if type_index > 0:
            # Root still continues until the last type row — always show a pipe.
            body_lines.append( pipe )
            rendered.append( _spacer_render_row( pipe ) )

        type_line = "{}{}".format( type_connector, type_label )
        body_lines.append( type_line )
        rendered.append( {
            'kind': 'parent',
            'size': _format_size( type_bytes ),
            'age': _format_age_cell( type_age_text, type_age_epoch ),
            'remark': ' ' * REMARK_WIDTH,
            'label': type_line,
            'parent_remark': '',
            'level': 'type',
            'fully_removing': False,
            'partially_removing': False,
            'mark': '',
            'name': type_label,
            'branch': type_connector,
        } )

        # Spacer under type before first identity: continuation + child pipe.
        type_child_spacer = ( type_prefix + pipe ).rstrip()
        body_lines.append( type_child_spacer )
        rendered.append( _spacer_render_row( type_child_spacer ) )

        for group_index, group in enumerate( cluster ):
            last_identity = group_index == len( cluster ) - 1
            id_connector = elbow if last_identity else tee
            id_branch = type_prefix + id_connector
            id_prefix = type_prefix + ( gap if last_identity else pipe )
            versions = _versions_from_group( group )
            identity_leaves = group['leaves']
            total_bytes = _group_total_bytes( group )
            id_age_text, id_age_epoch = _max_age_from_leaves( identity_leaves )
            id_mark, id_remark, id_full, id_partial = _selection_mark_for_leaves(
                    identity_leaves
            )
            # Archive product-clean: identity remark stays blank (source assets remain).
            if group.get( 'extract_bytes' ) is not None and not id_full:
                id_remark = ''

            if group_index > 0:
                body_lines.append( type_child_spacer )
                rendered.append( _spacer_render_row( type_child_spacer ) )

            name = group['dependency'] or '-'
            if id_mark:
                identity_line = "{}{} {}".format( id_branch, id_mark, name )
            else:
                identity_line = "{}{}".format( id_branch, name )
            body_lines.append( identity_line )
            rendered.append( {
                'kind': 'parent',
                'size': _format_size( total_bytes ),
                'age': _format_age_cell( id_age_text, id_age_epoch ),
                'remark': id_remark.ljust( REMARK_WIDTH ),
                'label': identity_line,
                'parent_remark': id_remark,
                'level': 'identity',
                'fully_removing': id_full,
                'partially_removing': id_partial,
                'mark': id_mark,
                'name': name,
                'branch': id_branch,
            } )

            # Qualifier nesting: skip version row when no qualifier on any leaf.
            has_version_rows = any( version.get( 'label' ) for version in versions )
            if not has_version_rows:
                id_child_spacer = ( id_prefix + pipe ).rstrip()
                body_lines.append( id_child_spacer )
                rendered.append( _spacer_render_row( id_child_spacer ) )
                rows, labels = _flatten_removal_leaves(
                        identity_leaves, tee, elbow, pipe, gap, check, ballot,
                        prefix=id_prefix,
                )
                body_lines.extend( labels )
                rendered.extend( rows )
                continue

            # Spacer between identity and version leaves.
            id_child_spacer = ( id_prefix + pipe ).rstrip()
            body_lines.append( id_child_spacer )
            rendered.append( _spacer_render_row( id_child_spacer ) )

            for ver_index, version in enumerate( versions ):
                last_version = ver_index == len( versions ) - 1
                ver_connector = elbow if last_version else tee
                ver_branch = id_prefix + ver_connector
                ver_prefix = id_prefix + ( gap if last_version else pipe )
                ver_leaves = version['leaves']
                ver_bytes = sum( _leaf_tree_bytes( leaf ) for leaf in ver_leaves )
                # Prefer group extract sizing when this is the sole archive version.
                if (
                        group.get( 'extract_bytes' ) is not None
                        and len( versions ) == 1
                ):
                    ver_bytes = _group_total_bytes( group )
                ver_age_text, ver_age_epoch = _max_age_from_leaves( ver_leaves )
                ver_mark, ver_remark, ver_full, ver_partial = _selection_mark_for_leaves(
                        ver_leaves
                )
                if group.get( 'extract_bytes' ) is not None and not ver_full:
                    ver_remark = ''
                ver_label = version['label'] or '-'

                if ver_index > 0:
                    # Blank row between qualifier siblings (list-style identity spacing).
                    between_versions = ( id_prefix + pipe ).rstrip()
                    body_lines.append( between_versions )
                    rendered.append( _spacer_render_row( between_versions ) )

                if ver_mark:
                    version_line = "{}{} {}".format( ver_branch, ver_mark, ver_label )
                else:
                    version_line = "{}{}".format( ver_branch, ver_label )
                body_lines.append( version_line )
                rendered.append( {
                    'kind': 'parent',
                    'size': _format_size( ver_bytes ),
                    'age': _format_age_cell( ver_age_text, ver_age_epoch ),
                    'remark': ver_remark.ljust( REMARK_WIDTH ),
                    'label': version_line,
                    'parent_remark': ver_remark,
                    'level': 'version',
                    'fully_removing': ver_full,
                    'partially_removing': ver_partial,
                    'mark': ver_mark,
                    'name': ver_label,
                    'branch': ver_branch,
                } )
                rows, labels = _flatten_removal_leaves(
                        ver_leaves, tee, elbow, pipe, gap, check, ballot,
                        prefix=ver_prefix,
                )
                body_lines.extend( labels )
                rendered.extend( rows )

    width = max(
            len( header ),
            max( ( dep_pad + len( INDENT ) + len( line ) for line in body_lines ), default=40 ),
            40,
    )

    out.write( as_subdued( _rule_line( width - len( INDENT ) ) ) + "\n" )
    out.write( header + "\n" )
    out.write( as_subdued( _rule_line( width - len( INDENT ) ) ) + "\n" )

    for row in rendered:
        if row['kind'] == 'spacer':
            out.write( "{}{}  {}  {}  {}\n".format(
                    INDENT,
                    row['size'],
                    row['age'],
                    row['remark'],
                    as_subdued( row.get( 'branch' ) or '' ),
            ) )
            continue

        if row['kind'] == 'parent':
            remark = row.get( 'parent_remark' ) or ''
            if remark == 'failed':
                remark_cell = as_remove_error( remark.ljust( REMARK_WIDTH ) )
            elif remark:
                remark_cell = as_remove_notice( remark.ljust( REMARK_WIDTH ) )
            else:
                remark_cell = ' ' * REMARK_WIDTH

            level = row.get( 'level' )
            branch = row.get( 'branch' ) or ''
            name = row.get( 'name' )
            mark = row.get( 'mark' ) or ''

            if level == 'summary':
                size_cell = as_emphasised( row['size'] )
                age_cell = row['age']
                label = as_emphasised( row['label'] )
            elif level == 'action':
                size_cell = as_emphasised( as_remove_notice( row['size'] ) )
                age_cell = row['age']
                label = "{}{}".format(
                        as_subdued( branch ),
                        as_emphasised( as_remove_notice( name ) ),
                )
            elif level == 'remaining':
                size_cell = as_subdued( row['size'] )
                age_cell = as_subdued( row['age'] )
                label = "{}{}".format(
                        as_subdued( branch ),
                        as_subdued( name ),
                )
            elif level == 'type':
                size_cell = row['size']
                age_cell = row['age']
                label = "{}{}".format( as_subdued( branch ), name )
            elif level in ( 'identity', 'version' ):
                if row.get( 'fully_removing' ):
                    size_cell = as_emphasised( as_remove_notice( row['size'] ) )
                    age_cell = row['age']
                    if mark:
                        label = "{}{} {}".format(
                                as_subdued( branch ),
                                as_remove_notice( mark ),
                                as_emphasised( as_remove_notice( name ) ),
                        )
                    else:
                        label = "{}{}".format(
                                as_subdued( branch ),
                                as_emphasised( as_remove_notice( name ) ),
                        )
                elif row.get( 'partially_removing' ):
                    # Partial wipe: colour mark + name only; size/age stay secondary.
                    size_cell = as_subdued( row['size'] )
                    age_cell = as_subdued( row['age'] )
                    if mark:
                        label = "{}{} {}".format(
                                as_subdued( branch ),
                                as_remove_notice( mark ),
                                as_emphasised( as_remove_notice( name ) ),
                        )
                    else:
                        label = "{}{}".format(
                                as_subdued( branch ),
                                as_emphasised( as_remove_notice( name ) ),
                        )
                else:
                    size_cell = as_subdued( row['size'] ) if level == 'identity' else row['size']
                    age_cell = as_subdued( row['age'] ) if level == 'identity' else row['age']
                    if mark:
                        # Untouched ``---`` (and any other non-action mark): subdued.
                        label = "{}{} {}".format(
                                as_subdued( branch ),
                                as_subdued( mark ),
                                as_emphasised( name ),
                        )
                    else:
                        label = "{}{}".format(
                                as_subdued( branch ),
                                as_emphasised( name ),
                        )
            else:
                size_cell = as_subdued( row['size'] )
                age_cell = row['age']
                label = as_emphasised( row['label'] )

            out.write( "{}{}  {}  {}  {}\n".format(
                    INDENT,
                    size_cell,
                    age_cell,
                    remark_cell,
                    label,
            ) )
            continue

        # Leaf
        if row['removing']:
            if row['result'] == 'failed':
                accent = as_remove_error
            else:
                accent = as_remove_notice
            remark_cell = (
                    accent( row['remark_text'].ljust( REMARK_WIDTH ) )
                    if row['remark_text'] else ' ' * REMARK_WIDTH
            )
            # Branch glyphs already include a trailing space.
            label = "{}{} {}".format(
                    as_subdued( row['branch'] ),
                    accent( row['mark'] ),
                    accent( row.get( 'display' ) or row['rel_path'] ),
            )
            out.write( "{}{}  {}  {}  {}\n".format(
                    INDENT,
                    row['size'],
                    row['age'],
                    remark_cell,
                    label,
            ) )
        else:
            label = "{}{} {}".format(
                    as_subdued( row['branch'] ),
                    as_subdued( row['mark'] ),
                    as_subdued( row.get( 'display' ) or row['rel_path'] ),
            )
            out.write( "{}{}  {}  {}  {}\n".format(
                    INDENT,
                    as_subdued( row['size'] ),
                    as_subdued( row['age'] ),
                    ' ' * REMARK_WIDTH,
                    label,
            ) )

    out.write( as_subdued( _rule_line( width - len( INDENT ) ) ) + "\n" )

    # Same legend as ``--list-downloads`` when purge / wipe nests ``[E]`` under archives.
    if downloads or download_leftovers:
        from cuppa.core.dependency_identity import EXTRACT_MARK
        if any(
                ( row.get( 'display' ) or '' ).startswith( EXTRACT_MARK )
                for row in rendered if row.get( 'kind' ) == 'leaf'
        ):
            out.write( "\n" )
            out.write(
                "{} = dependency extracted from the download above\n".format(
                        as_info( EXTRACT_MARK )
                )
            )


def _write_leftovers_summary( out, leftovers, download_leftovers=None ):
    leftovers = list( leftovers or [] )
    download_leftovers = list( download_leftovers or [] )
    if not leftovers and not download_leftovers:
        return
    total = sum( item.size_bytes for item in leftovers ) + sum(
            item.size_bytes for item in download_leftovers
    )
    parts = []
    if leftovers:
        unit = "tree" if len( leftovers ) == 1 else "trees"
        parts.append( "{} {}".format( len( leftovers ), unit ) )
    if download_leftovers:
        unit = "download" if len( download_leftovers ) == 1 else "downloads"
        parts.append( "{} {}".format( len( download_leftovers ), unit ) )
    out.write( "\n" )
    out.write( "Leaving {} ({}) for other selections as shown.\n".format(
            " and ".join( parts ),
            storage.human_size( total ),
    ) )


def _write_develop_skips( out, develop_skips ):
    if not develop_skips:
        return
    out.write( "\n" )
    out.write( "Skipped develop working copies (never removed):\n" )
    for item in develop_skips:
        out.write( "  {}: {}\n".format(
                item.dependency,
                storage.display_path( item.path ),
        ) )


def _write_verify( out, archives=None, purge=False, wipe=False, unreferenced=False ):
    out.write( "\n" )
    out.write( "Verify with:\n\n" )
    if unreferenced:
        out.write( as_emphasised(
                "cuppa -Q -D --list-dependencies --list-scope=unreferenced"
        ) + "\n" )
        out.write( as_emphasised(
                "cuppa -Q -D --list-downloads --list-scope=unreferenced"
        ) + "\n" )
        return
    if wipe or purge:
        out.write( as_emphasised( "cuppa -Q -D --list-downloads" ) + "\n" )
        if wipe:
            out.write( as_emphasised( "cuppa -Q -D --list-dependencies" ) + "\n" )
            return
        if archives:
            out.write( as_subdued(
                    "(archive product clean leaves source assets; "
                    "--list-dependencies still useful there)\n"
            ) )
        return
    out.write( as_emphasised( "cuppa -Q -D --list-dependencies" ) + "\n" )
    if archives:
        out.write( as_subdued(
                "(archive product clean leaves source assets; listing upgrades "
                "missing or estimated inventory sizes to exact)\n"
        ) )


def _refresh_archive_inventory_sizes( root, archives, targets, outcomes_by_path ):
    """Rewrite exact inventory sizes for extracts after successful product removal."""
    for archive in archives:
        extract = archive.get( 'extract' )
        if not extract or not os.path.isdir( extract ):
            continue
        extract_real = storage.real_path( extract )
        removed_any = False
        for target in targets:
            if target.dependency != archive['dependency']:
                continue
            if not _path_under_extract( target.path, extract_real ):
                continue
            outcome = outcomes_by_path.get( storage.real_path( target.path ), {} )
            if outcome.get( 'result' ) == 'removed':
                removed_any = True
                break
        if not removed_any:
            continue
        key = dependency_inventory.entry_key_for_path( extract )
        entry = dependency_inventory.load_entry( root, key ) or {}
        try:
            dependency_inventory.touch_entry(
                    root,
                    extract,
                    storage_type=entry.get( 'type' ) or entry.get( 'kind' ) or 'archive',
                    dependency=archive['dependency'],
                    qualifier=archive.get( 'qualifier' ) or entry.get( 'qualifier' ),
                    tool_variant=entry.get( 'tool_variant' ),
                    downloads=entry.get( 'downloads' ),
                    exact_sizes=True,
                    refresh_size=True,
                    update_last_used=False,
                    short_name=entry.get( 'short_name' ),
                    stem=entry.get( 'stem' ),
                    source_url=entry.get( 'source_url' ),
                    remote_location=entry.get( 'remote_location' ),
            )
        except Exception as error:
            logger.warn(
                    "Could not refresh inventory size for [{}]: {}".format(
                            as_warning( extract ), as_warning( str( error ) )
                    )
            )


def _write_freed_summary(
        out, planning, removed_count, removed_bytes, remaining_archive_bytes=None,
        download_count=0,
):
    parts = []
    if removed_count:
        unit = "tree" if removed_count == 1 else "trees"
        parts.append( "{} {}".format( removed_count, unit ) )
    if download_count:
        unit = "download" if download_count == 1 else "downloads"
        parts.append( "{} {}".format( download_count, unit ) )
    if not parts:
        parts.append( "0 trees" )
    size = as_emphasised( as_info( storage.human_size( removed_bytes ) ) )
    joined = " and ".join( parts )
    if planning:
        line = "Would remove {} freeing up {} of disk space".format( joined, size )
    else:
        line = "Removed {} freeing up {} of disk space".format( joined, size )
    if remaining_archive_bytes is not None:
        line += " leaving a final archive size of {}".format(
                as_emphasised( as_info( storage.human_size( remaining_archive_bytes ) ) )
        )
    out.write( line + ".\n" )


def _remaining_archive_bytes( archives, targets, outcomes_by_path, planning ):
    """Extract bytes left after successful (or planned) product removals."""
    if not archives:
        return None
    remaining = 0
    for archive in archives:
        removed = 0
        extract_real = storage.real_path( archive['extract'] )
        for target in targets:
            if target.dependency != archive['dependency']:
                continue
            if not _path_under_extract( target.path, extract_real ):
                continue
            outcome = outcomes_by_path.get( storage.real_path( target.path ), {} )
            result = outcome.get( 'result' )
            if result == 'removed' or ( planning and result == 'removed' ):
                removed += target.size_bytes
            elif planning and not outcome:
                # Defensive: treat as removed when planning without an outcome entry.
                removed += target.size_bytes
        remaining += max( 0, archive['extract_bytes'] - removed )
    return remaining


def _staying_extracts_from_owned( owned, targets, leftovers ):
    """Owned product trees that remain on disk (storage_clean extracts, develop skips)."""
    remove_reals = { storage.real_path( item.path ) for item in targets }
    leftover_reals = { storage.real_path( item.path ) for item in leftovers }
    staying = []
    seen = set()
    for item in owned or []:
        if item.category not in ( 'dependencies', 'cached' ) or not item.path:
            continue
        if item.category == 'develop' or item.develop:
            continue
        if not os.path.isdir( item.path ):
            continue
        real = storage.real_path( item.path )
        if real in remove_reals or real in leftover_reals or real in seen:
            continue
        seen.add( real )
        staying.append( RemovalTarget(
            dependency=item.dependency,
            path=item.path,
            qualifier=item.qualifier,
            tool_variant=item.tool_variant,
            storage_type=item.storage_type,
            size_bytes=_measure_bytes( item.path ),
            label=os.path.basename( item.path.rstrip( '\\/' ) ),
            extra_paths=(),
        ) )
    return staying


def _item_field( item, name, default=None ):
    if isinstance( item, dict ):
        return item.get( name, default )
    return getattr( item, name, default )


def _item_matches_any_token( item, tokens ):
    """True when ``item`` matches at least one resolved ``dependency_tokens`` entry."""
    from cuppa.core import dependency_tokens
    from cuppa.core.dependency_storage import normalise_storage_type

    if not tokens:
        return True

    raw_type = _item_field( item, 'storage_type' )
    item_type = normalise_storage_type( raw_type ) or raw_type or ''
    item_name = _item_field( item, 'dependency' ) or ''
    item_qual = _item_field( item, 'qualifier' )
    item_label = _item_field( item, 'label' )

    for storage_type, name, qualifier in tokens:
        if storage_type and item_type and item_type != storage_type:
            continue
        if storage_type and not item_type:
            continue
        if not dependency_tokens.name_matches( name, item_name ):
            continue
        if qualifier is None:
            return True
        row_like = {
            'type': item_type or 'unknown',
            'kind': item_type or 'unknown',
            'qualifier': item_qual,
            'dependency': item_name,
            'short_name': item_name,
            'label': item_label,
        }
        if _row_matches_force_token( row_like, name, qualifier ):
            return True
    return False


def _tokens_need_leaf_filter( tokens ):
    """True when any token restricts by storage type or qualifier."""
    return any(
            storage_type is not None or qualifier is not None
            for storage_type, _name, qualifier in ( tokens or [] )
    )


def _identity_key( item ):
    from cuppa.core.dependency_storage import normalise_storage_type

    storage_type = _item_field( item, 'storage_type' )
    return (
            normalise_storage_type( storage_type ) or storage_type,
            ( _item_field( item, 'dependency' ) or '' ).lower(),
    )


def _target_as_leftover( target ):
    label = target.label
    if not label:
        label = os.path.basename( str( target.path ).rstrip( '\\/' ) )
    return Leftover(
            dependency=target.dependency,
            path=target.path,
            qualifier=target.qualifier,
            tool_variant=target.tool_variant,
            size_bytes=target.size_bytes,
            label=label,
            storage_type=target.storage_type,
    )


def _filter_plan_by_tokens(
        cuppa_env, targets, leftovers, archives,
        download_targets=None, download_leftovers=None,
):
    """Apply ``cuppa_env['dependency_tokens']`` type/qualifier filters to a removal plan."""
    tokens = cuppa_env.get( 'dependency_tokens' ) or []
    if not _tokens_need_leaf_filter( tokens ):
        return (
                list( targets or [] ),
                list( leftovers or [] ),
                list( archives or [] ),
                list( download_targets or [] ),
                list( download_leftovers or [] ),
        )

    filtered_targets = []
    demoted = []
    for item in targets or []:
        if _item_matches_any_token( item, tokens ):
            filtered_targets.append( item )
        else:
            demoted.append( item )

    kept_identities = { _identity_key( item ) for item in filtered_targets }
    filtered_leftovers = [
            _target_as_leftover( item )
            for item in demoted
            if _identity_key( item ) in kept_identities
    ]
    for item in leftovers or []:
        if _identity_key( item ) in kept_identities:
            filtered_leftovers.append( item )

    filtered_archives = [
            archive for archive in ( archives or [] )
            if _item_matches_any_token( archive, tokens )
    ]

    filtered_downloads = []
    demoted_downloads = []
    for item in download_targets or []:
        if _item_matches_any_token( item, tokens ):
            filtered_downloads.append( item )
        else:
            demoted_downloads.append( item )

    kept_dl_identities = { _identity_key( item ) for item in filtered_downloads }
    filtered_dl_leftovers = []
    for item in list( download_leftovers or [] ) + demoted_downloads:
        if _identity_key( item ) in kept_dl_identities:
            filtered_dl_leftovers.append( item )

    return (
            filtered_targets,
            filtered_leftovers,
            filtered_archives,
            filtered_downloads,
            filtered_dl_leftovers,
    )


def remove_dependencies( construct, cuppa_env, out=None ):
    """Remove named (or all default) dependency trees for the current selection.

    When purge or wipe flags are set, also delete matching archives under ``downloads_root``.
    Wipe clears the whole extract even when ``storage_clean`` would leave it.
    """
    out = out or sys.stdout
    names, error = resolve_requested_names( cuppa_env )
    if isinstance( error, UnknownDependencyNames ):
        # Lazy import: dependency_actions imports this module at load time.
        from cuppa.core import dependency_actions
        dependency_actions.write_unknown_remove_names_error(
                construct, cuppa_env, error, out=out
        )
        return 1
    if error:
        out.write( "error: {}\n".format( error ) )
        return 1

    root = _dependencies_root( cuppa_env )
    _refuse_suspicious_dependencies_root( root, cuppa_env.get( 'sconstruct_dir' ) )

    wipe = wants_wipe( cuppa_env )
    purge = wants_purge( cuppa_env ) or wipe
    if purge:
        downloads_root_check = _downloads_root( cuppa_env )
        if downloads_root_check and storage.is_suspicious_root( downloads_root_check ):
            raise storage.StorageError(
                "refusing to purge under suspicious downloads root [{}]".format(
                        downloads_root_check
                )
            )
    plan = collect_removal_plan( construct, cuppa_env, names, wipe=wipe )
    targets = plan['targets']
    leftovers = plan['leftovers']
    archives = plan.get( 'archives' ) or []
    develop_skips = plan['develop_skips']
    owned = plan.get( 'owned' ) or []
    planning = dry_run( cuppa_env )

    download_targets = []
    download_leftovers = []
    downloads_root = None
    staying_extracts = []
    if purge:
        download_targets, download_leftovers, downloads_root = collect_purge_downloads(
                construct, cuppa_env, names, owned=owned,
        )
        if not wipe:
            staying_extracts = _staying_extracts_from_owned( owned, targets, leftovers )

    (
            targets, leftovers, archives, download_targets, download_leftovers,
    ) = _filter_plan_by_tokens(
            cuppa_env, targets, leftovers, archives,
            download_targets=download_targets,
            download_leftovers=download_leftovers,
    )
    if purge and not wipe:
        staying_extracts = _staying_extracts_from_owned( owned, targets, leftovers )

    actionable_downloads = [ item for item in download_targets if not item.missing ]
    if not targets and not actionable_downloads:
        out.write( "nothing to remove" )
        if names:
            out.write( " for {} under the current selection".format(
                    ', '.join( names )
            ) )
        out.write( " under {}\n".format( storage.display_path( root ) ) )
        if leftovers or archives or download_targets or download_leftovers:
            _write_removal_tree(
                    out, [], leftovers, {}, planning, root, archives=archives,
                    downloads=download_targets, download_leftovers=download_leftovers,
                    downloads_root=downloads_root, staying_extracts=staying_extracts,
                    summary_label="related dependencies for {}".format(
                            ', '.join( names ) if names else 'selection'
                    ),
                    action_label=(
                            'wiped' if wipe else ( 'removing' if planning else 'removed' )
                    ),
            )
            _write_leftovers_summary( out, leftovers, download_leftovers )
        _write_develop_skips( out, develop_skips )
        if leftovers or develop_skips or archives or download_targets or download_leftovers:
            _write_verify( out, archives=archives or None, purge=purge, wipe=wipe )
        return 0

    planned_bytes = sum( item.size_bytes for item in targets ) + sum(
            item.size_bytes for item in actionable_downloads
    )
    announce_parts = []
    if targets:
        unit = "dependency tree" if len( targets ) == 1 else "dependency trees"
        announce_parts.append( "{} {}".format( as_emphasised( str( len( targets ) ) ), unit ) )
    if actionable_downloads:
        unit = "download" if len( actionable_downloads ) == 1 else "downloads"
        announce_parts.append(
                "{} {}".format( as_emphasised( str( len( actionable_downloads ) ) ), unit )
        )
    if not announce_parts:
        announce_parts.append( "nothing" )
    where = as_info( storage.display_path( root ) )
    if purge and downloads_root:
        where = "{} / {}".format( where, as_info( storage.display_path( downloads_root ) ) )
    verb = "Would wipe" if planning and wipe else (
            "Wiping" if wipe else ( "Would remove" if planning else "Removing" )
    )
    announce = "{} {} ({}) under {}".format(
            verb,
            " and ".join( announce_parts ),
            as_emphasised( storage.human_size( planned_bytes ) ),
            where,
    )
    out.write( announce + "\n" )
    if planning:
        hint = "wipe" if wipe else "remove"
        out.write( as_subdued( "(dry run; pass without -n to {})".format( hint ) ) + "\n" )
    out.write( "\n" )

    outcomes_by_path = {}
    failures = []
    removed_bytes = 0
    removed_count = 0

    for target in targets:
        paths = ( target.path, ) + tuple( target.extra_paths or () )
        real = storage.real_path( target.path )
        if planning:
            outcomes_by_path[real] = { 'result': 'removed' }
            removed_bytes += target.size_bytes
            removed_count += 1
            continue
        try:
            for path in paths:
                storage.ensure_contained( path, root, what="dependency path" )
                if os.path.islink( path ):
                    raise storage.StorageError(
                        "refusing to remove through symlink [{}]".format( path )
                    )
                if not os.path.lexists( path ):
                    # Sibling product may already be gone; continue others.
                    continue
                storage.remove_path( path, dry_run=False )
                storage.prune_empty_parents( os.path.dirname( path ), root )
                try:
                    dependency_inventory.delete_entry_for_path( root, path )
                except Exception:
                    pass
            outcomes_by_path[real] = { 'result': 'removed' }
            removed_bytes += target.size_bytes
            removed_count += 1
        except storage.StorageError as error:
            reason = str( error )
            already_gone = "already deleted" in reason.lower() or "not found" in reason.lower()
            severity = 'warning' if already_gone else 'error'
            outcomes_by_path[real] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': target.dependency,
                'path': target.path,
                'reason': reason,
                'severity': severity,
            } )
        except OSError as error:
            reason = str( error )
            outcomes_by_path[real] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': target.dependency,
                'path': target.path,
                'reason': reason,
                'severity': 'error',
            } )

    download_removed_count = 0
    for download in download_targets:
        real_key = (
                storage.real_path( download.path )
                if os.path.lexists( download.path ) else download.path
        )
        if download.missing:
            outcomes_by_path[real_key] = { 'result': 'absent' }
            continue
        if planning:
            outcomes_by_path[real_key] = { 'result': 'removed' }
            removed_bytes += download.size_bytes
            download_removed_count += 1
            continue
        try:
            storage.ensure_contained( download.path, downloads_root, what="download path" )
            if os.path.islink( download.path ):
                raise storage.StorageError(
                    "refusing to remove through symlink [{}]".format( download.path )
                )
            if os.path.lexists( download.path ):
                storage.remove_path( download.path, dry_run=False )
                storage.prune_empty_parents( os.path.dirname( download.path ), downloads_root )
            outcomes_by_path[real_key] = { 'result': 'removed' }
            removed_bytes += download.size_bytes
            download_removed_count += 1
        except storage.StorageError as error:
            reason = str( error )
            already_gone = "already deleted" in reason.lower() or "not found" in reason.lower()
            severity = 'warning' if already_gone else 'error'
            outcomes_by_path[real_key] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': download.dependency,
                'path': download.path,
                'reason': reason,
                'severity': severity,
            } )
        except OSError as error:
            reason = str( error )
            outcomes_by_path[real_key] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': download.dependency,
                'path': download.path,
                'reason': reason,
                'severity': 'error',
            } )

    _write_removal_tree(
            out, targets, leftovers, outcomes_by_path, planning, root, archives=archives,
            downloads=download_targets, download_leftovers=download_leftovers,
            downloads_root=downloads_root, staying_extracts=staying_extracts,
            summary_label="related dependencies for {}".format(
                    ', '.join( names ) if names else 'selection'
            ),
            action_label=(
                    'wiped' if wipe else ( 'removing' if planning else 'removed' )
            ),
    )
    _write_leftovers_summary( out, leftovers, download_leftovers )
    _write_develop_skips( out, develop_skips )

    if failures:
        out.write( "\n" )
        out.write( as_warning( "Not all requested dependency trees could be removed:" ) + "\n" )
        for item in failures:
            colour = as_remove_error if item['severity'] == 'error' else as_warning
            out.write( "  {}: {}\n".format(
                    colour( item['dependency'] ),
                    item['reason'],
            ) )

    out.write( "\n" )
    remaining = 0 if wipe else _remaining_archive_bytes(
            archives, targets, outcomes_by_path, planning
    )
    _write_freed_summary(
            out, planning, removed_count, removed_bytes,
            remaining_archive_bytes=remaining,
            download_count=download_removed_count,
    )
    if not planning and archives and not wipe:
        _refresh_archive_inventory_sizes( root, archives, targets, outcomes_by_path )
    _write_verify( out, archives=archives or None, purge=purge, wipe=wipe )

    hard_errors = [ item for item in failures if item['severity'] == 'error' ]
    return 1 if hard_errors else 0


def _other_project_used_by( entry, this_project ):
    """Return used_by paths that are not this project."""
    used_by = ( entry or {} ).get( 'used_by' ) or {}
    if not used_by:
        return []
    if not this_project:
        return sorted( used_by.keys() )
    this_real = storage.real_path( this_project )
    return sorted(
            path for path in used_by
            if storage.real_path( path ) != this_real
    )


def parse_force_wipe_tokens( spec ):
    """Parse force-wipe tokens: optional ``[selector]`` plus ``name`` or ``name/qualifier``.

    Returns ``(tokens, error)`` where each token is
    ``(storage_type_or_None, name, qualifier_or_None)``.
    """
    from cuppa.core import dependency_tokens

    tokens, error = dependency_tokens.parse_dependency_tokens( spec )
    if error:
        if error == "no dependency tokens given":
            return [], (
                    "no force-wipe tokens given "
                    "(use --force-wipe-dependencies=[source]name/qualifier,…)"
            )
        return [], error
    return tokens, None


def force_token_is_wildcard( name, qualifier ):
    """True when the token is a glob or an identity-wide (no qualifier) match."""
    if qualifier is None:
        return True
    return _is_wildcard_pattern( name ) or _is_wildcard_pattern( qualifier )


def _normalise_wipe_name( value ):
    return ( value or '' ).strip().lower()


def _is_wildcard_pattern( text ):
    """True when ``text`` uses shell / ``fnmatch`` wildcards (``*``, ``?``, ``[``)."""
    return any( char in ( text or '' ) for char in '*?[' )


def _qualifier_aliases( qualifier, storage_type ):
    """Return forms that should match a list leaf qualifier / display label."""
    from cuppa.core.dependency_identity import display_qualifier

    raw = ( qualifier or '' ).strip()
    aliases = { raw, raw.lower() }
    display = display_qualifier( raw, storage_type or 'repository' )
    if display:
        aliases.add( display )
        aliases.add( display.lower() )
    # Accept with or without leading @ for location-style tokens.
    if raw.startswith( '@' ):
        aliases.add( raw[1:] )
        aliases.add( raw[1:].lower() )
    else:
        aliases.add( '@' + raw )
        aliases.add( ( '@' + raw ).lower() )
    # Unqualified default-branch label: "@master (unqualified)".
    if ' (unqualified)' in display.lower():
        base = display.split( ' (', 1 )[0]
        aliases.add( base )
        aliases.add( base.lower() )
    return { item for item in aliases if item }


def _row_name_candidates( row ):
    return {
            item for item in (
                    ( row.get( 'short_name' ) or '' ).strip(),
                    ( row.get( 'dependency' ) or '' ).strip(),
                    ( row.get( 'stem' ) or '' ).strip(),
            ) if item
    }


def _fnmatch_any( candidates, patterns ):
    """Case-insensitive ``fnmatch`` of any candidate against any pattern."""
    for candidate in candidates:
        cand_l = candidate.lower()
        for pattern in patterns:
            if fnmatch.fnmatch( cand_l, pattern.lower() ):
                return True
    return False


def _row_matches_force_token( row, name, qualifier ):
    storage_type = row.get( 'type' ) or row.get( 'kind' ) or 'unknown'
    name_candidates = _row_name_candidates( row )
    if _is_wildcard_pattern( name ):
        if not _fnmatch_any( name_candidates, { name } ):
            return False
    else:
        want = _normalise_wipe_name( name )
        if want not in { _normalise_wipe_name( item ) for item in name_candidates }:
            return False

    row_qual = row.get( 'qualifier' )
    # Prefer an explicit display label on the row when present.
    candidates = _qualifier_aliases( row_qual, storage_type )
    label = row.get( 'label' )
    if label:
        candidates.add( str( label ).strip() )
        candidates.add( str( label ).strip().lower() )
    want_aliases = _qualifier_aliases( qualifier, storage_type )
    if _is_wildcard_pattern( qualifier ):
        return _fnmatch_any( candidates, want_aliases )
    return bool( candidates & want_aliases )


def _inventory_by_path( root ):
    by_path = {}
    for entry in dependency_inventory.load_all_entries( root ):
        path = entry.get( 'path' )
        if path:
            by_path[storage.real_path( path )] = entry
    return by_path


def _target_from_row( row ):
    path = row.get( 'path' )
    return RemovalTarget(
            dependency=row.get( 'dependency' ) or row.get( 'short_name' ) or '-',
            path=path,
            qualifier=row.get( 'qualifier' ),
            tool_variant=row.get( 'tool_variant' ),
            storage_type=row.get( 'type' ) or row.get( 'kind' ) or 'unknown',
            size_bytes=int( row.get( 'size_bytes' ) or _measure_bytes( path ) ),
            label=None,
            extra_paths=(),
    )


def _download_from_row( row, missing=False ):
    path = row.get( 'path' )
    return DownloadTarget(
            dependency=row.get( 'dependency' ) or row.get( 'short_name' ) or '-',
            path=path,
            qualifier=row.get( 'qualifier' ),
            tool_variant=row.get( 'tool_variant' ),
            storage_type=row.get( 'type' ) or 'archive',
            size_bytes=0 if missing else int(
                    row.get( 'size_bytes' ) or _download_file_size( path )
            ),
            label=row.get( 'label' ) or os.path.basename( path or '' ),
            missing=missing,
    )


def _force_wipe_identity_names( targets, download_targets ):
    """Normalised identity names touched by a force-wipe plan."""
    names = set()
    for item in list( targets or [] ) + list( download_targets or [] ):
        name = _normalise_wipe_name( getattr( item, 'dependency', None ) )
        if name:
            names.add( name )
    return names


def _row_matches_identities( row, identities ):
    if not identities:
        return False
    for key in ( row.get( 'short_name' ), row.get( 'dependency' ), row.get( 'stem' ) ):
        if _normalise_wipe_name( key ) in identities:
            return True
    return False


def _collect_force_wipe_context( rows, dl_rows, targets, download_targets ):
    """Same-identity leaves that remain after a partial force-wipe.

    Shown muted in the report (no ``would rm``) so the identity parent is not marked
    removed when siblings stay, and so the final size includes what is left.
    """
    identities = _force_wipe_identity_names( targets, download_targets )
    wipe_extract = {
            storage.real_path( item.path )
            for item in targets
            if item.path and os.path.lexists( item.path )
    }
    wipe_download = set()
    for item in download_targets or []:
        if not item.path:
            continue
        wipe_download.add(
                storage.real_path( item.path ) if os.path.lexists( item.path ) else item.path
        )

    leftovers = []
    leftover_seen = set( wipe_extract )
    for row in rows or []:
        if not _row_matches_identities( row, identities ):
            continue
        path = row.get( 'path' )
        if not path or not os.path.lexists( path ):
            continue
        if os.path.islink( path ):
            continue
        real = storage.real_path( path )
        if real in leftover_seen:
            continue
        leftover_seen.add( real )
        leftovers.append( _target_from_row( row ) )

    download_leftovers = []
    download_seen = set( wipe_download )
    for row in dl_rows or []:
        if row.get( 'role' ) != 'archive':
            continue
        if not _row_matches_identities( row, identities ):
            continue
        path = row.get( 'path' )
        if not path:
            continue
        real = storage.real_path( path ) if os.path.lexists( path ) else path
        if real in download_seen:
            continue
        download_seen.add( real )
        if not os.path.lexists( path ):
            continue
        if os.path.islink( path ):
            continue
        download_leftovers.append( _download_from_row( row, missing=False ) )

    return leftovers, download_leftovers


def _execute_force_wipe(
        out, root, downloads_root, targets, download_targets, planning,
        notes=None, used_by_warnings=None, unreferenced=False,
        leftovers=None, download_leftovers=None, summary_label=None,
):
    """Announce, delete, and report a force-wipe plan."""
    notes = notes or []
    used_by_warnings = used_by_warnings or []
    leftovers = list( leftovers or [] )
    download_leftovers = list( download_leftovers or [] )
    if not summary_label:
        summary_label = (
                'unreferenced dependencies' if unreferenced
                else 'related dependencies for selection'
        )
    actionable_downloads = [ item for item in download_targets if not item.missing ]
    if not targets and not actionable_downloads:
        out.write( "nothing to wipe under the requested force-wipe selection\n" )
        for item in used_by_warnings:
            out.write( as_warning(
                    "warning: {} still recorded as used by another project: {}\n".format(
                            item['dependency'],
                            ', '.join( storage.display_path( p ) for p in item['used_by'] ),
                    )
            ) )
        if leftovers or download_leftovers:
            _write_removal_tree(
                    out, [], leftovers, {}, planning, root,
                    downloads=[], download_leftovers=download_leftovers,
                    downloads_root=downloads_root, staying_extracts=[],
                    summary_label=summary_label,
                    action_label='wiped',
            )
        _write_verify( out, wipe=True, unreferenced=unreferenced )
        return 0

    planned_bytes = sum( item.size_bytes for item in targets ) + sum(
            item.size_bytes for item in actionable_downloads
    )
    announce_parts = []
    if targets:
        unit = "dependency tree" if len( targets ) == 1 else "dependency trees"
        announce_parts.append( "{} {}".format( as_emphasised( str( len( targets ) ) ), unit ) )
    if actionable_downloads:
        unit = "download" if len( actionable_downloads ) == 1 else "downloads"
        announce_parts.append(
                "{} {}".format( as_emphasised( str( len( actionable_downloads ) ) ), unit )
        )
    where = as_info( storage.display_path( root ) )
    if downloads_root:
        where = "{} / {}".format( where, as_info( storage.display_path( downloads_root ) ) )
    out.write( "{} {} ({}) under {}\n".format(
            "Would wipe" if planning else "Wiping",
            " and ".join( announce_parts ),
            as_emphasised( storage.human_size( planned_bytes ) ),
            where,
    ) )
    if planning:
        out.write( as_subdued( "(dry run; pass without -n to wipe)" ) + "\n" )
    out.write( "\n" )
    for note in notes:
        out.write( as_subdued( note ) + "\n" )
    if notes:
        out.write( "\n" )
    for item in used_by_warnings:
        out.write( as_warning(
                "warning: wiping {} despite used_by from another project ({})\n".format(
                        storage.display_path( item['path'] ),
                        ', '.join( storage.display_path( p ) for p in item['used_by'] ),
                )
        ) )
    if used_by_warnings:
        out.write( "\n" )

    outcomes_by_path = {}
    failures = []
    removed_bytes = 0
    removed_count = 0

    for target in targets:
        real = storage.real_path( target.path )
        if planning:
            outcomes_by_path[real] = { 'result': 'removed' }
            removed_bytes += target.size_bytes
            removed_count += 1
            continue
        try:
            storage.ensure_contained( target.path, root, what="dependency path" )
            if os.path.islink( target.path ):
                raise storage.StorageError(
                    "refusing to remove through symlink [{}]".format( target.path )
                )
            if os.path.lexists( target.path ):
                storage.remove_path( target.path, dry_run=False )
                storage.prune_empty_parents( os.path.dirname( target.path ), root )
                try:
                    dependency_inventory.delete_entry_for_path( root, target.path )
                except Exception:
                    pass
            outcomes_by_path[real] = { 'result': 'removed' }
            removed_bytes += target.size_bytes
            removed_count += 1
        except ( storage.StorageError, OSError ) as error:
            reason = str( error )
            already_gone = "already deleted" in reason.lower() or "not found" in reason.lower()
            severity = 'warning' if already_gone else 'error'
            outcomes_by_path[real] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': target.dependency,
                'path': target.path,
                'reason': reason,
                'severity': severity,
            } )

    download_removed_count = 0
    for download in download_targets:
        real_key = (
                storage.real_path( download.path )
                if os.path.lexists( download.path ) else download.path
        )
        if download.missing:
            outcomes_by_path[real_key] = { 'result': 'absent' }
            continue
        if planning:
            outcomes_by_path[real_key] = { 'result': 'removed' }
            removed_bytes += download.size_bytes
            download_removed_count += 1
            continue
        try:
            storage.ensure_contained( download.path, downloads_root, what="download path" )
            if os.path.islink( download.path ):
                raise storage.StorageError(
                    "refusing to remove through symlink [{}]".format( download.path )
                )
            if os.path.lexists( download.path ):
                storage.remove_path( download.path, dry_run=False )
                storage.prune_empty_parents( os.path.dirname( download.path ), downloads_root )
            outcomes_by_path[real_key] = { 'result': 'removed' }
            removed_bytes += download.size_bytes
            download_removed_count += 1
        except ( storage.StorageError, OSError ) as error:
            reason = str( error )
            already_gone = "already deleted" in reason.lower() or "not found" in reason.lower()
            severity = 'warning' if already_gone else 'error'
            outcomes_by_path[real_key] = { 'result': 'failed', 'reason': reason }
            failures.append( {
                'dependency': download.dependency,
                'path': download.path,
                'reason': reason,
                'severity': severity,
            } )

    _write_removal_tree(
            out, targets, leftovers, outcomes_by_path, planning, root,
            downloads=download_targets, download_leftovers=download_leftovers,
            downloads_root=downloads_root, staying_extracts=[],
            summary_label=summary_label,
            action_label='wiped',
    )

    if failures:
        out.write( "\n" )
        out.write( as_warning( "Not all requested paths could be wiped:" ) + "\n" )
        for item in failures:
            colour = as_remove_error if item['severity'] == 'error' else as_warning
            out.write( "  {}: {}\n".format(
                    colour( item['dependency'] ),
                    item['reason'],
            ) )

    remaining = sum( item.size_bytes for item in leftovers ) + sum(
            item.size_bytes for item in download_leftovers if not getattr( item, 'missing', False )
    )
    out.write( "\n" )
    _write_freed_summary(
            out, planning, removed_count, removed_bytes,
            remaining_archive_bytes=remaining,
            download_count=download_removed_count,
    )
    _write_verify( out, wipe=True, unreferenced=unreferenced )
    hard_errors = [ item for item in failures if item['severity'] == 'error' ]
    return 1 if hard_errors else 0


def force_wipe_dependencies( construct, cuppa_env, out=None ):
    """Clear-down list-tree leaves named as ``name/qualifier`` tokens."""
    from cuppa.core import dependency_actions, dependency_downloads, dependency_identity

    out = out or sys.stdout
    tokens, error = parse_force_wipe_tokens( cuppa_env.get( 'force_wipe_dependencies' ) )
    if error:
        out.write( "error: {}\n".format( error ) )
        return 1

    root = _dependencies_root( cuppa_env )
    _refuse_suspicious_dependencies_root( root, cuppa_env.get( 'sconstruct_dir' ) )
    downloads_root = _downloads_root( cuppa_env )
    if downloads_root and storage.is_suspicious_root( downloads_root ):
        raise storage.StorageError(
            "refusing to wipe under suspicious downloads root [{}]".format( downloads_root )
        )

    rows = dependency_actions._collect_rows( construct, cuppa_env ).get( 'rows' ) or []
    dl_rows = dependency_downloads.collect_download_rows( construct, cuppa_env ).get( 'rows' ) or []
    by_path = _inventory_by_path( root )
    this_project = cuppa_env.get( 'sconstruct_dir' )
    planning = dry_run( cuppa_env )

    from cuppa.core import dependency_tokens

    targets = []
    seen = set()
    notes = []
    used_by_warnings = []
    matched_reals = set()

    for storage_type, name, qualifier in tokens:
        token_label = dependency_tokens.format_token( storage_type, name, qualifier )
        matches = [
                row for row in rows
                if row.get( 'path' ) and dependency_tokens.row_matches_token(
                        row, storage_type, name, qualifier
                )
        ]
        # Distinct paths only.
        by_real = {}
        for row in matches:
            real = storage.real_path( row['path'] ) if os.path.lexists( row['path'] ) else row['path']
            by_real.setdefault( real, row )
        if not by_real:
            out.write( "error: no dependency leaf matches [{}]\n".format( token_label ) )
            return 1
        wildcard = force_token_is_wildcard( name, qualifier )
        if not wildcard and len( by_real ) > 1:
            out.write( "error: ambiguous force-wipe token [{}]; candidates:\n".format(
                    token_label
            ) )
            for row in sorted( by_real.values(), key=lambda item: item.get( 'path' ) or '' ):
                out.write( "  {} ({})\n".format(
                        storage.display_path( row['path'] ),
                        storage.human_size( int( row.get( 'size_bytes' ) or 0 ) ),
                ) )
            return 1
        for row in sorted( by_real.values(), key=lambda item: item.get( 'path' ) or '' ):
            path = row['path']
            if not os.path.lexists( path ):
                out.write( "error: matched leaf [{}] path does not exist: {}\n".format(
                        token_label, path
                ) )
                return 1
            real = storage.real_path( path )
            if real in seen:
                continue
            storage.ensure_contained( path, root, what="dependency path" )
            if os.path.islink( path ):
                raise storage.StorageError(
                    "refusing to remove through symlink [{}]".format( path )
                )
            entry = by_path.get( real ) or {}
            others = _other_project_used_by( entry, this_project )
            if others:
                used_by_warnings.append( {
                    'dependency': row.get( 'dependency' ) or row.get( 'short_name' ) or path,
                    'path': path,
                    'used_by': others,
                } )
            if not entry:
                notes.append( "no inventory record for {}".format( storage.display_path( path ) ) )
            seen.add( real )
            matched_reals.add( real )
            targets.append( _target_from_row( row ) )

    download_targets = []
    download_seen = set()
    for row in dl_rows:
        if row.get( 'role' ) != 'archive':
            continue
        path = row.get( 'path' )
        if not path:
            continue
        paired = False
        for storage_type, name, qualifier in tokens:
            if dependency_tokens.row_matches_token( row, storage_type, name, qualifier ):
                paired = True
                break
        if not paired:
            # Product children in downloads listing may point at extract paths.
            continue
        real = storage.real_path( path ) if os.path.lexists( path ) else path
        if real in download_seen:
            continue
        download_seen.add( real )
        if not os.path.lexists( path ):
            download_targets.append( _download_from_row( row, missing=True ) )
            continue
        if not downloads_root:
            continue
        storage.ensure_contained( path, downloads_root, what="download path" )
        if os.path.islink( path ):
            raise storage.StorageError(
                "refusing to remove through symlink [{}]".format( path )
            )
        download_targets.append( _download_from_row( row, missing=False ) )

    # Also pick up archives whose basename/path is linked from inventory downloads
    # for wiped extracts, or find_cached_download for archive homes.
    for target in targets:
        entry = by_path.get( storage.real_path( target.path ) ) or {}
        for download_path in entry.get( 'downloads' ) or []:
            if not download_path:
                continue
            real = storage.real_path( download_path ) if os.path.lexists( download_path ) else download_path
            if real in download_seen:
                continue
            download_seen.add( real )
            if not downloads_root or not os.path.lexists( download_path ):
                download_targets.append( DownloadTarget(
                        dependency=target.dependency,
                        path=download_path,
                        qualifier=target.qualifier,
                        tool_variant=target.tool_variant,
                        storage_type='archive',
                        size_bytes=0,
                        label=os.path.basename( download_path ),
                        missing=not os.path.lexists( download_path ),
                ) )
                continue
            storage.ensure_contained( download_path, downloads_root, what="download path" )
            download_targets.append( DownloadTarget(
                    dependency=target.dependency,
                    path=download_path,
                    qualifier=target.qualifier,
                    tool_variant=target.tool_variant,
                    storage_type='archive',
                    size_bytes=_download_file_size( download_path ),
                    label=os.path.basename( download_path ),
                    missing=False,
            ) )
        try:
            found = dependency_identity.find_cached_download(
                    downloads_root,
                    storage_type=target.storage_type,
                    path=target.path,
            )
        except Exception:
            found = None
        if found and downloads_root:
            real = storage.real_path( found ) if os.path.lexists( found ) else found
            if real not in download_seen:
                download_seen.add( real )
                if os.path.lexists( found ):
                    storage.ensure_contained( found, downloads_root, what="download path" )
                    download_targets.append( DownloadTarget(
                            dependency=target.dependency,
                            path=found,
                            qualifier=target.qualifier,
                            tool_variant=target.tool_variant,
                            storage_type='archive',
                            size_bytes=_download_file_size( found ),
                            label=os.path.basename( found ),
                            missing=False,
                    ) )

    leftovers, download_leftovers = _collect_force_wipe_context(
            rows, dl_rows, targets, download_targets,
    )
    raw_spec = cuppa_env.get( 'force_wipe_dependencies' )
    if isinstance( raw_spec, ( list, tuple ) ):
        raw_spec = raw_spec[0] if raw_spec else ''
    summary_label = "related dependencies for {}".format(
            str( raw_spec ).strip() or 'selection'
    )
    return _execute_force_wipe(
            out, root, downloads_root, targets, download_targets, planning,
            notes=notes, used_by_warnings=used_by_warnings, unreferenced=False,
            leftovers=leftovers, download_leftovers=download_leftovers,
            summary_label=summary_label,
    )


def force_wipe_unreferenced_dependencies( construct, cuppa_env, out=None ):
    """Clear-down every tree and download this resolve marks as unreferenced."""
    from cuppa.core import dependency_actions, dependency_downloads, dependency_tree

    out = out or sys.stdout
    root = _dependencies_root( cuppa_env )
    _refuse_suspicious_dependencies_root( root, cuppa_env.get( 'sconstruct_dir' ) )
    downloads_root = _downloads_root( cuppa_env )
    if downloads_root and storage.is_suspicious_root( downloads_root ):
        raise storage.StorageError(
            "refusing to wipe under suspicious downloads root [{}]".format( downloads_root )
        )

    dep_data = dependency_actions.apply_list_scope(
            dependency_actions._collect_rows( construct, cuppa_env ),
            'unreferenced',
            tree_builder=dependency_tree.build_tree,
    )
    dl_data = dependency_actions.apply_list_scope(
            dependency_downloads.collect_download_rows( construct, cuppa_env ),
            'unreferenced',
            tree_builder=dependency_downloads.build_downloads_tree,
    )

    this_project = cuppa_env.get( 'sconstruct_dir' )
    planning = dry_run( cuppa_env )
    by_path = _inventory_by_path( root )

    targets = []
    seen = set()
    notes = []
    used_by_warnings = []

    for row in dep_data.get( 'rows' ) or []:
        if row.get( 'state' ) != 'unreferenced':
            continue
        path = row.get( 'path' )
        if not path or not os.path.lexists( path ):
            continue
        real = storage.real_path( path )
        if real in seen:
            continue
        storage.ensure_contained( path, root, what="dependency path" )
        if os.path.islink( path ):
            raise storage.StorageError(
                "refusing to remove through symlink [{}]".format( path )
            )
        entry = by_path.get( real ) or {}
        others = _other_project_used_by( entry, this_project )
        if others:
            used_by_warnings.append( {
                'dependency': row.get( 'dependency' ) or row.get( 'short_name' ) or path,
                'path': path,
                'used_by': others,
            } )
        if not entry:
            notes.append( "no inventory record for {}".format( storage.display_path( path ) ) )
        seen.add( real )
        targets.append( _target_from_row( row ) )

    download_targets = []
    for row in dl_data.get( 'rows' ) or []:
        if row.get( 'state' ) != 'unreferenced':
            continue
        if row.get( 'role' ) != 'archive':
            continue
        path = row.get( 'path' )
        if not path:
            continue
        if not os.path.lexists( path ):
            download_targets.append( _download_from_row( row, missing=True ) )
            continue
        if not downloads_root:
            continue
        storage.ensure_contained( path, downloads_root, what="download path" )
        if os.path.islink( path ):
            raise storage.StorageError(
                "refusing to remove through symlink [{}]".format( path )
            )
        download_targets.append( _download_from_row( row, missing=False ) )

    return _execute_force_wipe(
            out, root, downloads_root, targets, download_targets, planning,
            notes=notes, used_by_warnings=used_by_warnings, unreferenced=True,
            summary_label='unreferenced dependencies',
    )
