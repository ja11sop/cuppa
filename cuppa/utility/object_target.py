#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   object_target_for / artifact_target_for
#-------------------------------------------------------------------------------

import os


def source_subdir_for( env, source ):
    """
    Directory offset where outputs for source should be mirrored.

    Sources already mirrored under build_root keep their offset from build_dir.
    Project-relative sources mirror their path under the chosen output root so
    nested files with the same basename do not collide. Absolute sources stay flat.

    Use ``source.path`` for layout (SCons ``str(source)`` is often an absolute
    path even when ``source.path`` is project-relative).
    """
    source_path = source.path.replace( '\\', '/' )
    build_root = env['build_root'].replace( '\\', '/' )
    build_dir = env['build_dir'].replace( '\\', '/' )

    if source_path.startswith( build_root ):
        return os.path.relpath( os.path.split( source_path )[0], build_dir )

    if os.path.isabs( source_path ):
        return ''

    source_dir = os.path.dirname( source_path )
    if source_dir in ( '', '.' ):
        return ''
    return source_dir


# Backward-compatible alias used by object emitters.
_object_subdir_for_source = source_subdir_for


def object_target_for( env, source, obj_prefix, obj_suffix, *, interface_suffixes=() ):
    """
    Map a source to its object node under the variant working directory.

    Returns a path **relative to** ``env['build_dir']`` (the sconscript
    ``variant_dir``), for example ``src/detail/router/test.o``. SCons places
    that at ``{build_dir}/src/detail/router/test.o`` on disk — e.g.
    ``_build/gcc153/dbg/x86_64/cxx2c/working/src/detail/router/test.o`` from
    the project root.

    Do **not** embed ``build_dir`` in the node path passed to ``env.File``;
    doing so duplicates the working tree (``working/_build/.../working/...``).

    Module interface suffixes (.cppm / .cxxm / .ccm) keep the extension in the
    object stem (e.g. calc.cppm → calc.cppm.o) so they do not collide with a
    same-basename implementation unit (calc.cpp → calc.o).
    """
    basename = os.path.split( str( source ) )[1]
    stem, ext = os.path.splitext( basename )
    if ext.lower() in interface_suffixes:
        object_stem = basename
    else:
        object_stem = stem

    object_name = obj_prefix + object_stem + obj_suffix
    object_subdir = source_subdir_for( env, source )
    source_path = source.path.replace( '\\', '/' )

    if object_subdir:
        return env.File( os.path.join( object_subdir, object_name ) )

    if os.path.isabs( source_path ):
        return env.File( os.path.join( obj_prefix + object_stem + obj_suffix ) )

    return env.File( object_name )


def artifact_target_for( env, source, suffix, *, output_dir=None, root='final' ):
    """
    Map a source to an artefact path under ``final/`` (or ``working/``).

    Mirrors nested project-relative sources so same-basename inputs do not
    collide — the doc/asset counterpart of :func:`object_target_for`.

    ``suffix`` is the new extension including the leading dot (for example
    ``.html`` or ``.out``). Returns an **absolute** path string under the
    chosen root. Pass ``output_dir`` when the emitter uses a custom
    ``final_dir``; otherwise ``root='final'`` uses ``env['abs_final_dir']``
    and ``root='working'`` uses ``env['build_dir']``.
    """
    if suffix and not suffix.startswith( '.' ):
        suffix = '.' + suffix

    basename = os.path.split( source.path )[1]
    stem = os.path.splitext( basename )[0]
    name = stem + ( suffix or '' )

    if output_dir is None:
        if root == 'final':
            output_dir = env['abs_final_dir']
        elif root == 'working':
            output_dir = env['build_dir']
        else:
            raise ValueError(
                "artifact_target_for root must be 'final' or 'working', got {!r}"
                .format( root )
            )

    subdir = source_subdir_for( env, source )
    if subdir:
        return os.path.normpath( os.path.join( output_dir, subdir, name ) )
    return os.path.normpath( os.path.join( output_dir, name ) )
