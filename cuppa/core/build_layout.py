#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Build layout
#-------------------------------------------------------------------------------

"""Where a variant's build output lives under the build root.

`tool_variant_dir` is the path segment shared by every sconscript that builds for a given
toolchain, variant, architecture, and ABI. Removal and listing compose it here so they cannot
drift from `construct.call_project_sconscript_files`.
"""

import os
from collections import namedtuple


WORKING = 'working'
FINAL = 'final'


def sanitise_abi( abi ):
    """Path-safe ABI segment. Matches construct.py: ``c++2c`` becomes ``cxx2c``."""
    return abi.replace( '+', 'x' )


def tool_variant_dir( toolchain_name, variant, target_arch, abi ):
    """``<toolchain>/<variant>/<arch>/<abi>`` — the suffix under each sconscript's build path."""
    return os.path.join( toolchain_name, variant, target_arch, abi )


BuildVariant = namedtuple(
    'BuildVariant',
    [ 'path', 'relpath', 'sconscript', 'tool_variant', 'selected' ],
)


def is_variant_root( path ):
    """True when ``path`` is the directory that holds ``working`` and/or ``final``."""
    if not os.path.isdir( path ):
        return False
    working = os.path.join( path, WORKING )
    final = os.path.join( path, FINAL )
    return os.path.isdir( working ) or os.path.isdir( final )


def discover_build_variants( abs_build_root, selected_suffixes=() ):
    """Every variant root under the build root.

    A variant root is a directory that directly contains ``working`` and/or ``final``. The
    sconscript column is the path between the build root and the four-segment tool-variant
    suffix; ``selected`` is true when that suffix is one of ``selected_suffixes``.
    """
    if not abs_build_root or not os.path.isdir( abs_build_root ):
        return []

    selected = set( os.path.normpath( suffix ) for suffix in selected_suffixes )
    found = []
    abs_build_root = os.path.realpath( abs_build_root )

    for root, dirnames, _filenames in os.walk( abs_build_root, followlinks=False ):
        # Do not descend into working/final; the parent is the variant root we care about.
        if os.path.basename( root ) in ( WORKING, FINAL ):
            dirnames[:] = []
            continue

        if not is_variant_root( root ):
            continue

        relpath = os.path.relpath( root, abs_build_root )
        parts = relpath.split( os.sep )
        if len( parts ) < 4:
            # toolchain / variant / arch / abi — anything shorter is not our layout.
            continue

        tool_variant = os.path.join( *parts[-4:] )
        sconscript = os.path.join( *parts[:-4] ) if len( parts ) > 4 else '.'
        found.append( BuildVariant(
            path = root,
            relpath = relpath,
            sconscript = sconscript,
            tool_variant = tool_variant,
            selected = os.path.normpath( tool_variant ) in selected,
        ) )
        # Children of a variant root are working/final (and their contents); skip them.
        dirnames[:] = []

    return sorted( found, key=lambda entry: entry.relpath )


def _path_ends_with( relpath, suffix ):
    relpath = os.path.normpath( relpath )
    return relpath == suffix or relpath.endswith( os.sep + suffix )


def paths_ending_with( abs_build_root, suffix ):
    """Directories under ``abs_build_root`` whose relative path ends with ``suffix``.

    ``os.walk(..., followlinks=False)`` does not visit symlink directories, so symlink
    children are checked explicitly — callers (removal) need to see them in order to refuse.
    """
    suffix = os.path.normpath( suffix )
    matches = []
    if not abs_build_root or not os.path.isdir( abs_build_root ):
        return matches

    abs_build_root = os.path.realpath( abs_build_root )
    for root, dirnames, _filenames in os.walk( abs_build_root, followlinks=False ):
        relpath = os.path.relpath( root, abs_build_root )
        if _path_ends_with( relpath, suffix ):
            matches.append( root )
            dirnames[:] = []
            continue

        for name in list( dirnames ):
            child = os.path.join( root, name )
            if not os.path.islink( child ):
                continue
            child_rel = os.path.relpath( child, abs_build_root )
            if _path_ends_with( child_rel, suffix ):
                matches.append( child )
                dirnames.remove( name )
    return sorted( matches )
