#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency removal — --remove-dependencies / --remove-all-dependencies
#-------------------------------------------------------------------------------

"""Remove selected dependency trees under ``dependencies_root`` (Slice D).

Does not touch downloads, develop working copies, or build artefacts. Selection follows the
same toolchain / variant / location-match options as writing the trees. See
``design/plans/removal-options.md`` §4.13.
"""

from __future__ import annotations

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
AGE_WIDTH = 12
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
    [ 'dependency', 'path', 'qualifier', 'tool_variant', 'size_bytes', 'label' ],
)

DevelopSkip = namedtuple(
    'DevelopSkip',
    [ 'dependency', 'path', 'reason' ],
)

UnknownDependencyNames = namedtuple(
    'UnknownDependencyNames',
    [ 'unknown', 'project_used' ],
)


def parse_dependency_names( spec ):
    """Split a comma-separated ``--remove-dependencies`` value into names."""
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
    """Return ``(names, error)`` for the current remove flags.

    ``error`` is ``None`` on success, a string for empty input, or
    :class:`UnknownDependencyNames` when names are not project-used.
    ``--remove-all-dependencies`` with no project-used names yields an empty list.
    """
    project_used = project_dependency_names( cuppa_env )
    project_set = set( project_used )

    if cuppa_env.get( 'remove_all_dependencies' ):
        return list( project_used ), None

    names = parse_dependency_names( cuppa_env.get( 'remove_dependencies' ) )
    if not names:
        return [], "no dependency names given (use --remove-dependencies=name or --remove-all-dependencies)"

    unknown = [ name for name in names if name not in project_set ]
    if unknown:
        return [], UnknownDependencyNames(
                unknown=tuple( unknown ),
                project_used=tuple( project_used ),
        )
    # Preserve order, drop duplicates.
    seen = set()
    ordered = []
    for name in names:
        if name not in seen:
            seen.add( name )
            ordered.append( name )
    return ordered, None


def _dependencies_root( cuppa_env ):
    root = cuppa_env.get( 'dependencies_root' )
    if not root:
        raise storage.StorageError( "dependencies_root is not set" )
    return os.path.abspath( os.path.expanduser( root ) )


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
        ) )
    return leftovers


def enumerate_archive_product_dirs( home ):
    """List b2 stage leaves and folded ``bin.*`` toolset units under a Boost home.

    Stage products remain one leaf per ``build…/<toolchain>/<variant>/<arch>``.
    Bin products are one unit per ``bin.<abi>/<toolset-token>`` (nested Boost.Build
    dirs for that toolset folded together for leftovers / reporting).
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
            else:
                products.append( {
                    'path': os.path.abspath( path ),
                    'paths': [ os.path.abspath( path ) ],
                    'tool_variant': name,
                    'kind': 'bin_root',
                } )
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
        ) )
    return leftovers


def collect_removal_plan( construct, cuppa_env, names ):
    """Build remove targets, leftovers, develop skips, and resolve skips for ``names``."""
    root = _dependencies_root( cuppa_env )
    selections = dependency_storage.selection_build_envs( construct, cuppa_env )
    owned, skips = dependency_storage.resolve_named_dependencies(
            construct, cuppa_env, names, selections=selections
    )
    clean_by_name = _collect_storage_clean( construct, cuppa_env, names, selections )

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
    }


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


def _group_removal_rows( targets, leftovers, outcomes_by_path, planning, root, archives=None ):
    """Group targets and leftovers by dependency for the removal tree."""
    groups = {}
    archives = archives or []

    def ensure( dependency ):
        if dependency not in groups:
            groups[dependency] = {
                'dependency': dependency,
                'qualifiers': set(),
                'leaves': [],
                'extract_bytes': None,
            }
        return groups[dependency]

    for archive in archives:
        group = ensure( archive['dependency'] )
        if archive.get( 'qualifier' ):
            group['qualifiers'].add( archive['qualifier'] )
        group['extract_bytes'] = archive['extract_bytes']
        group['leaves'].append( {
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
        } )

    for target in targets:
        group = ensure( target.dependency )
        if target.qualifier:
            group['qualifiers'].add( target.qualifier )
        age_text, age_epoch = _age_for_path( root, target.path )
        group['leaves'].append( {
            'path': target.path,
            'rel_path': _relative_removal_path( target.path, root ),
            'display': target.label or _relative_removal_path( target.path, root ),
            'size_bytes': target.size_bytes,
            'qualifier': target.qualifier,
            'tool_variant': target.tool_variant,
            'age_text': age_text,
            'age_epoch': age_epoch,
            'removing': True,
            'result': _leaf_result( outcomes_by_path, target.path, planning, True ),
            'extra_paths': list( target.extra_paths or () ),
            'kind': 'product',
        } )

    for leftover in leftovers:
        group = ensure( leftover.dependency )
        if leftover.qualifier:
            group['qualifiers'].add( leftover.qualifier )
        age_text, age_epoch = _age_for_path( root, leftover.path )
        group['leaves'].append( {
            'path': leftover.path,
            'rel_path': _relative_removal_path( leftover.path, root ),
            'display': leftover.label or _relative_removal_path( leftover.path, root ),
            'size_bytes': leftover.size_bytes,
            'qualifier': leftover.qualifier,
            'tool_variant': leftover.tool_variant,
            'age_text': age_text,
            'age_epoch': age_epoch,
            'removing': False,
            'result': 'left',
            'extra_paths': [],
            'kind': 'product',
        } )

    for group in groups.values():
        # Source assets first; then products by tool_variant / path.
        group['leaves'].sort( key=lambda leaf: (
                0 if leaf.get( 'kind' ) == 'source_assets' else 1,
                leaf.get( 'tool_variant' ) or '',
                leaf.get( 'qualifier' ) or '',
                leaf['rel_path'],
        ) )
        # Shared qualifier (e.g. package version) hangs on the parent label.
        quals = group['qualifiers']
        group['parent_qualifier'] = next( iter( quals ) ) if len( quals ) == 1 else None
    return [ groups[name] for name in sorted( groups ) ]


def _write_removal_tree( out, targets, leftovers, outcomes_by_path, planning, root, archives=None ):
    """Hierarchical removal table: identity rollup, selected leaves, muted leftovers."""
    if not targets and not leftovers and not archives:
        return

    tee, elbow, _pipe, _gap = storage.glyphs()
    check = storage.with_heavy_marks( storage.selected_mark() )
    ballot = storage.with_heavy_marks( storage.failed_mark() )
    groups = _group_removal_rows(
            targets, leftovers, outcomes_by_path, planning, root, archives=archives
    )

    header = "{}{}  {}  {}  {}".format(
            INDENT,
            "SIZE".rjust( SIZE_WIDTH ),
            "LAST USED".ljust( AGE_WIDTH ),
            "REMARK".ljust( REMARK_WIDTH ),
            "DEPENDENCY",
    )
    # Prefix before DEPENDENCY column content.
    dep_pad = SIZE_WIDTH + 2 + AGE_WIDTH + 2 + REMARK_WIDTH + 2

    body_lines = []  # plain-width samples for rule sizing
    rendered = []

    for group in groups:
        leaves = group['leaves']
        if group.get( 'extract_bytes' ) is not None:
            total_bytes = group['extract_bytes']
        else:
            total_bytes = sum( leaf['size_bytes'] for leaf in leaves )
        parent_label = group['dependency']
        if group.get( 'parent_qualifier' ):
            parent_label = "{}  {}".format( parent_label, group['parent_qualifier'] )
        # Archive identity is never fully removed (source assets stay) — no parent REMARK.
        if group.get( 'extract_bytes' ) is not None:
            parent_remark = ''
        else:
            parent_remark = _parent_rollup_result( [
                    leaf['result'] for leaf in leaves
            ] )

        body_lines.append( parent_label )
        rendered.append( {
            'kind': 'parent',
            'size': _format_size( total_bytes ),
            'age': ' ' * AGE_WIDTH,
            'remark': parent_remark.ljust( REMARK_WIDTH ),
            'label': parent_label,
            'parent_remark': parent_remark,
        } )

        for index, leaf in enumerate( leaves ):
            branch = elbow if index == len( leaves ) - 1 else tee
            result = leaf['result']
            remark = _remark_for_result( result )
            if result == 'failed':
                mark = ballot
            elif leaf['removing']:
                mark = check
            else:
                mark = '-'
            leaf_display = leaf.get( 'display' ) or leaf['rel_path']
            leaf_label = "{} {} {}".format(
                    branch, mark, leaf_display
            )
            body_lines.append( leaf_label )
            rendered.append( {
                'kind': 'leaf',
                'size': _format_size( leaf['size_bytes'] ),
                'age': ( leaf['age_text'] or '-' ).ljust( AGE_WIDTH ),
                'remark': remark.ljust( REMARK_WIDTH ),
                'label': leaf_label,
                'branch': branch,
                'mark': mark,
                'display': leaf_display,
                'rel_path': leaf['rel_path'],
                'result': result,
                'removing': leaf['removing'],
                'remark_text': remark,
            } )

    width = max(
            len( header ),
            max( ( dep_pad + len( INDENT ) + len( line ) for line in body_lines ), default=40 ),
            40,
    )

    out.write( as_subdued( _rule_line( width - len( INDENT ) ) ) + "\n" )
    out.write( header + "\n" )
    out.write( as_subdued( _rule_line( width - len( INDENT ) ) ) + "\n" )

    for row in rendered:
        if row['kind'] == 'parent':
            remark = row['parent_remark']
            if remark == 'failed':
                remark_cell = as_remove_error( remark.ljust( REMARK_WIDTH ) )
            elif remark:
                remark_cell = as_remove_notice( remark.ljust( REMARK_WIDTH ) )
            else:
                remark_cell = ' ' * REMARK_WIDTH
            out.write( "{}{}  {}  {}  {}\n".format(
                    INDENT,
                    as_subdued( row['size'] ),
                    row['age'],
                    remark_cell,
                    as_emphasised( row['label'] ),
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
            label = "{}{} {}".format(
                    as_subdued( row['branch'] + ' ' ),
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
                    as_subdued( row['branch'] + ' ' ),
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


def _write_leftovers_summary( out, leftovers ):
    if not leftovers:
        return
    total = sum( item.size_bytes for item in leftovers )
    unit = "tree" if len( leftovers ) == 1 else "trees"
    out.write( "\n" )
    out.write( "Leaving {} {} ({}) for other selections as shown.\n".format(
            len( leftovers ),
            unit,
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


def _write_verify( out, archives=None ):
    out.write( "\n" )
    out.write( "Verify with:\n\n" )
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


def _write_freed_summary( out, planning, removed_count, removed_bytes, remaining_archive_bytes=None ):
    unit = "tree" if removed_count == 1 else "trees"
    size = as_emphasised( as_info( storage.human_size( removed_bytes ) ) )
    if planning:
        line = "Would remove {} {} freeing up {} of disk space".format(
                removed_count, unit, size,
        )
    else:
        line = "Removed {} {} freeing up {} of disk space".format(
                removed_count, unit, size,
        )
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


def remove_dependencies( construct, cuppa_env, out=None ):
    """Remove named (or all default) dependency trees for the current selection."""
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

    plan = collect_removal_plan( construct, cuppa_env, names )
    targets = plan['targets']
    leftovers = plan['leftovers']
    archives = plan.get( 'archives' ) or []
    develop_skips = plan['develop_skips']
    planning = dry_run( cuppa_env )

    if not targets:
        out.write( "nothing to remove" )
        if names:
            out.write( " for {} under the current selection".format(
                    ', '.join( names )
            ) )
        out.write( " under {}\n".format( storage.display_path( root ) ) )
        if leftovers or archives:
            _write_removal_tree(
                    out, [], leftovers, {}, planning, root, archives=archives
            )
            _write_leftovers_summary( out, leftovers )
        _write_develop_skips( out, develop_skips )
        if leftovers or develop_skips or archives:
            _write_verify( out, archives=archives or None )
        return 0

    planned_bytes = sum( item.size_bytes for item in targets )
    unit = "dependency tree" if len( targets ) == 1 else "dependency trees"
    announce = "{} {} {} ({}) under {}".format(
            "Would remove" if planning else "Removing",
            as_emphasised( str( len( targets ) ) ),
            unit,
            as_emphasised( storage.human_size( planned_bytes ) ),
            as_info( storage.display_path( root ) ),
    )
    out.write( announce + "\n" )
    if planning:
        out.write( as_subdued( "(dry run; pass without -n to remove)" ) + "\n" )
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

    _write_removal_tree(
            out, targets, leftovers, outcomes_by_path, planning, root, archives=archives
    )
    _write_leftovers_summary( out, leftovers )
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
    remaining = _remaining_archive_bytes( archives, targets, outcomes_by_path, planning )
    _write_freed_summary(
            out, planning, removed_count, removed_bytes,
            remaining_archive_bytes=remaining,
    )
    if not planning and archives:
        _refresh_archive_inventory_sizes( root, archives, targets, outcomes_by_path )
    _write_verify( out, archives=archives or None )

    hard_errors = [ item for item in failures if item['severity'] == 'error' ]
    return 1 if hard_errors else 0
