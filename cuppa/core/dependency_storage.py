#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dependency storage — resolve-only path discovery
#-------------------------------------------------------------------------------

"""Resolve dependency on-disk paths without retrieving them.

Optional ``storage_paths()`` on a dependency instance returns the folders that dependency owns.
Types that omit it are reported as skipped (layout not declared), never guessed.

``cuppa_env['storage_resolve_only']`` disables fetch/extract while factories still compute paths
(the same idea as ``retrieval_disabled_reason()`` for ``--offline`` / ``--clean``).

``construct.create_build_envs`` returns a list of selection dicts
``{ 'env', 'variant', 'target_arch', 'abi', ... }`` — factories take the nested ``env``.
"""

import os
import re
from collections import namedtuple

from cuppa.core import build_layout
from cuppa.log import logger
from cuppa.colourise import as_info, as_warning


RESOLVE_ONLY_REASON = "storage action"

# One owned path discovered for a named dependency under the current selection.
OwnedPath = namedtuple(
    'OwnedPath',
    [
        'dependency',       # sconstruct / registry name
        'kind',             # location | package | conan | boost | …
        'category',         # dependencies | downloads | build | develop
        'path',
        'qualifier',        # @branch, version, fingerprint prefix, …
        'tool_variant',     # toolchain_variant_arch_abi or None
        'develop',          # True when this path is a develop working copy
    ],
)

Skip = namedtuple( 'Skip', [ 'dependency', 'reason' ] )

# tool_variant dirs look like gcc153_rel_x86_64_cxx2c / clang211_dbg_x86_64_cxx2c
_TOOL_VARIANT_DIR = re.compile(
    r'^.+_(dbg|rel|cov)_[A-Za-z0-9_]+$'
)


def enable_resolve_only( cuppa_env ):
    """Mark the environment so dependency factories do not retrieve or extract."""
    cuppa_env['storage_resolve_only'] = True


def resolve_only_active( env ):
    return bool( env.get( 'storage_resolve_only' ) )


def empty_storage_paths():
    return {
        'dependencies': [],
        'downloads': [],
        'build': [],
        'develop': [],
    }


def normalise_storage_paths( paths ):
    """Coerce a ``storage_paths()`` result into the standard four lists."""
    result = empty_storage_paths()
    if not paths:
        return result
    for key in result:
        value = paths.get( key ) or []
        if isinstance( value, ( str, bytes ) ):
            value = [ value ]
        result[key] = [ p for p in value if p ]
    return result


def looks_like_tool_variant_dir( name ):
    return bool( name and _TOOL_VARIANT_DIR.match( name ) )


# Keys location / package factories read from the env during resolve-only. SConscript
# loading normally sets abs_sconscript_dir; storage actions run before that.
_ENV_KEYS_FROM_CUPPA = (
    'sconstruct_dir',
    'abs_sconstruct_dir',
    'dependencies_root',
    'downloads_root',
    'storage_root',
    'storage_resolve_only',
    'offline',
    'clean',
    'dump',
    'develop',
    'current_branch',
    'current_revision',
    'location_match_current_branch',
    'location_match_branch',
    'location_match_tag',
    'location_explicit_default_branch',
)


def selection_build_envs( construct, cuppa_env ):
    """Flattened list of ``create_build_envs`` selection dicts for active toolchains."""
    selections = []
    sconstruct_dir = cuppa_env.get( 'sconstruct_dir' )
    for toolchain in cuppa_env.get( 'active_toolchains' ) or []:
        for selection in construct.create_build_envs( toolchain, cuppa_env ):
            selection = dict( selection )
            selection['toolchain'] = toolchain
            env = selection.get( 'env' )
            if env is not None:
                for key in _ENV_KEYS_FROM_CUPPA:
                    if key in cuppa_env and key not in env:
                        env[key] = cuppa_env[key]
                if 'abs_sconscript_dir' not in env and sconstruct_dir:
                    env['abs_sconscript_dir'] = os.path.abspath( sconstruct_dir )
                if 'sconscript_dir' not in env and sconstruct_dir:
                    env['sconscript_dir'] = sconstruct_dir
                env['storage_resolve_only'] = True
                if 'tool_variant_dir' not in env:
                    env['tool_variant_dir'] = build_layout.tool_variant_dir(
                        toolchain.name(),
                        selection['variant'],
                        selection['target_arch'],
                        selection['abi'],
                    )
            selections.append( selection )
    return selections


def _dependency_kind( instance ):
    module = getattr( type( instance ), '__module__', '' ) or ''
    name = type( instance ).__name__
    if 'conan' in module or 'conan' in name.lower():
        return 'conan'
    if 'boost' in module or name == 'Boost':
        return 'boost'
    if 'package' in module or 'Package' in name:
        return 'package'
    if 'location' in module or hasattr( instance, '_location' ):
        return 'location'
    return 'dependency'


def _call_storage_paths( instance ):
    method = getattr( instance, 'storage_paths', None )
    if method is None:
        return None
    return normalise_storage_paths( method() )


def _meta_from_instance( instance ):
    qualifier = None
    tool_variant = None
    for attr in ( 'storage_qualifier', 'qualifier' ):
        getter = getattr( instance, attr, None )
        if callable( getter ):
            qualifier = getter()
            break
        if getter is not None and not callable( getter ):
            qualifier = getter
            break
    for attr in ( 'storage_tool_variant', 'tool_variant' ):
        getter = getattr( instance, attr, None )
        if callable( getter ):
            tool_variant = getter()
            break
        if getter is not None and not callable( getter ):
            tool_variant = getter
            break
    # Location / boost expose branch via the wrapped Location.
    if qualifier is None:
        location = getattr( instance, '_location', None )
        if location is not None:
            branch = getattr( location, 'branch', None )
            if callable( branch ):
                branch = branch()
            if branch:
                qualifier = '@' + str( branch )
            local_folder = getattr( location, 'local_folder', None )
            if callable( local_folder ):
                folder = local_folder()
                if folder:
                    _name, folder_qualifier = split_location_folder_name( folder )
                    if folder_qualifier:
                        qualifier = folder_qualifier
    return qualifier, tool_variant


def _scons_env_from_selection( selection ):
    """``create_build_envs`` yields dicts; factories need the nested SCons env."""
    if selection is None:
        return None
    if isinstance( selection, dict ) and 'env' in selection:
        return selection['env']
    return selection


def resolve_named_dependencies( construct, cuppa_env, names, selections=None ):
    """Create each named dependency for the active selection and collect owned paths.

    Returns ``(owned_paths, skips)``. Factories that return ``None`` or lack
    ``storage_paths`` are skipped with a reason.
    """
    enable_resolve_only( cuppa_env )
    factories = cuppa_env.get( 'dependencies' ) or {}
    known = sorted( factories.keys() )
    owned = []
    skips = []
    seen_paths = set()

    if selections is None:
        selections = selection_build_envs( construct, cuppa_env )
    if not selections:
        skips.append( Skip( dependency='*', reason='no active toolchains' ) )
        return owned, skips

    for name in names:
        factory = factories.get( name )
        if factory is None:
            skips.append( Skip(
                dependency=name,
                reason='unknown dependency (known: {})'.format( ', '.join( known ) or 'none' ),
            ) )
            continue

        created_any = False
        declared = False
        for selection in selections:
            env = _scons_env_from_selection( selection )
            if env is None:
                continue
            try:
                instance = factory( env )
            except Exception as error:
                logger.warn( "Could not resolve dependency [{}] for storage: {}".format(
                        as_warning( name ), as_warning( str( error ) )
                ) )
                skips.append( Skip( dependency=name, reason=str( error ) ) )
                created_any = True
                continue

            if instance is None:
                continue
            created_any = True

            paths = _call_storage_paths( instance )
            if paths is None:
                for attr in ( '_package', '_location' ):
                    inner = getattr( instance, attr, None )
                    if inner is not None:
                        paths = _call_storage_paths( inner )
                        if paths is not None:
                            break
            if paths is None:
                continue

            declared = True
            kind = _dependency_kind( instance )
            qualifier, tool_variant = _meta_from_instance( instance )
            if tool_variant is None:
                tool_variant = env.get( 'tool_variant_dir', '' ).replace( '/', '_' ).replace( '\\', '_' ) or None

            for category, path_list in paths.items():
                for path in path_list:
                    key = ( category, path )
                    if key in seen_paths:
                        continue
                    seen_paths.add( key )
                    owned.append( OwnedPath(
                        dependency=name,
                        kind=kind,
                        category=category,
                        path=path,
                        qualifier=qualifier,
                        tool_variant=tool_variant if category != 'develop' else None,
                        develop=( category == 'develop' ),
                    ) )

        if not created_any:
            skips.append( Skip( dependency=name, reason='factory returned nothing' ) )
        elif not declared:
            skips.append( Skip( dependency=name, reason='layout not declared' ) )
            logger.info( "Dependency [{}] has no storage_paths(); skipped".format( as_info( name ) ) )

    return owned, skips


def default_dependency_names( cuppa_env ):
    """Names Phase 3 treats as known to this build (default_dependencies only for now)."""
    return list( cuppa_env.get( 'default_dependencies' ) or [] )


def describe_tree_path( path, dependencies_root ):
    """Best-effort dependency / qualifier / tool_variant from a path under the root.

    Used for on-disk trees that are not yet in the inventory. Never invents ownership
    for nested source folders inside a VCS tree.
    """
    root = os.path.realpath( os.path.expanduser( dependencies_root ) )
    real = os.path.realpath( path )
    try:
        relative = os.path.relpath( real, root )
    except ValueError:
        return {
            'dependency': os.path.basename( real ),
            'qualifier': None,
            'tool_variant': None,
            'kind': 'unknown',
        }
    parts = relative.split( os.sep )
    if not parts or parts[0] in ( '', '.' ):
        return {
            'dependency': os.path.basename( real ),
            'qualifier': None,
            'tool_variant': None,
            'kind': 'unknown',
        }

    if parts[0] == 'conan' and len( parts ) >= 3:
        return {
            'dependency': parts[1],
            'qualifier': parts[2],
            'tool_variant': None,
            'kind': 'conan',
        }

    if looks_like_tool_variant_dir( parts[0] ) and len( parts ) >= 3:
        return {
            'dependency': parts[1],
            'qualifier': parts[2],
            'tool_variant': parts[0],
            'kind': 'package',
        }

    top = parts[0]
    dependency, qualifier = split_location_folder_name( top )
    return {
        'dependency': dependency,
        'qualifier': qualifier,
        'tool_variant': None,
        'kind': 'location',
    }


def split_location_folder_name( folder ):
    """Split a location folder into ``(name, @branch_or_None)``.

    Encoded ``git@host`` URLs become folders like ``git_ssh_git@host__path``, so a single
    ``@`` there is part of the name. A second ``@`` is a branch/tag (``…@master``).
    HTTPS folders use at most one ``@`` for the branch (``…fmt.git@11.1.1``).
    """
    if not folder:
        return folder, None
    at_count = folder.count( '@' )
    if at_count >= 2:
        name, branch = folder.rsplit( '@', 1 )
        return name, '@' + branch
    if at_count == 1 and not folder.startswith( 'git_ssh_git@' ):
        name, branch = folder.rsplit( '@', 1 )
        return name, '@' + branch
    return folder, None
