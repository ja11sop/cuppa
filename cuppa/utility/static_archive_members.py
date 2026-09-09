#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Unique static-archive members for BuildStaticLib
#-------------------------------------------------------------------------------
#
# Compile mirrors nested sources under working/ (#213), but traditional ar / lib.exe
# store archive members by basename. When two objects share a basename, the second
# silently replaces the first. Stage colliding inputs under unique names derived
# from the build_dir-relative path before StaticLibrary runs.

import os

from SCons.Defaults import Copy
from SCons.Errors import StopError
from SCons.Script import Flatten


def object_relpath_under_build( env, object_node ):
    """Return the object path relative to ``env['build_dir']``, using ``/`` separators."""
    build_dir = os.path.abspath( env['build_dir'] )
    if hasattr( object_node, 'get_abspath' ):
        obj_path = object_node.get_abspath()
    else:
        obj_path = os.path.abspath( str( object_node ) )
    try:
        rel = os.path.relpath( obj_path, build_dir )
    except ValueError:
        rel = os.path.basename( obj_path )
    return rel.replace( '\\', '/' )


def archive_member_name( relpath ):
    """Flatten a working/-relative object path into a single archive member basename."""
    return relpath.replace( '/', '_' )


def basenames_collide( objects ):
    """True when two or more object nodes share the same basename."""
    seen = set()
    for obj in objects:
        base = os.path.basename( str( obj ) )
        if base in seen:
            return True
        seen.add( base )
    return False


def stage_objects_for_static_archive( env, library_target, objects ):
    """
    Ensure StaticLibrary inputs have unique archive member basenames.

    When every object basename is already unique, return ``objects`` unchanged.
    On collision, copy each object to ``working/.archive_members/<target>/<flat>``
    so ``ar`` / the MSVC librarian keep one member per object. Flattened name
    collisions raise ``StopError``.
    """
    objects = [ node for node in Flatten( [ objects ] ) if node ]
    if not objects or not basenames_collide( objects ):
        return objects

    stage_root = os.path.join( '.archive_members', str( library_target ) )
    used_names = {}
    staged = []

    for obj in objects:
        rel = object_relpath_under_build( env, obj )
        member = archive_member_name( rel )
        if member in used_names:
            raise StopError(
                "Static library [{target}]: archive member [{member}] collides for "
                "objects [{first}] and [{second}] under working/. "
                "Rename one source or shorten a path segment so flattened names differ."
                .format(
                    target=library_target,
                    member=member,
                    first=used_names[member],
                    second=rel,
                )
            )
        used_names[member] = rel
        dest = os.path.join( stage_root, member )
        staged.extend( env.Command( dest, obj, Copy( '$TARGET', '$SOURCE' ) ) )

    return staged
