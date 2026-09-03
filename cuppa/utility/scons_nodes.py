
#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Resolve SCons nodes that live under VariantDir
#-------------------------------------------------------------------------------

"""Map a SCons node to a filesystem path that actually exists.

A relative generated directory (for example ``boost/1.92/lib`` or a
``BuildStaticLib(..., final_dir='package_lib')`` output) has ``str(node)``
under the variant ``working/`` tree. ``node.srcnode()`` is the project-root
counterpart, which often does not exist for build products.

Package publishers must copy from the generated tree when it is present.
Unconditionally using ``srcnode()`` is the usual failure mode under
``--parallel`` package builds.
"""

import os


def resolve_existing_node_path( node ):
    """Return an existing generated node path, or its source-tree counterpart.

    Preference:

    1. ``str(node)`` when that path exists (variant / generated).
    2. ``srcnode()`` when that path exists (headers / source tree).
    3. ``str(node)`` otherwise, so missing-path errors name the generated side.
    """
    path = str( node )
    if os.path.exists( path ):
        return path
    srcnode = getattr( node, 'srcnode', None )
    if callable( srcnode ):
        source_path = str( srcnode() )
        if os.path.exists( source_path ):
            return source_path
    return path
