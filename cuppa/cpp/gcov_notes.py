#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Per-test GCC/Clang ``.gcda`` isolation via ``GCOV_PREFIX``.

Instrumented objects write notes beside the ``.o`` unless the test process
sets ``GCOV_PREFIX``. Tests that link the same library would otherwise share
one ``.gcda`` and corrupt it under ``-j``. ``gcov`` itself does not read
``GCOV_PREFIX`` (it opens ``.gcda`` next to the ``-o`` stem), so collection
symlinks the relocated note beside a private copy of the ``.gcno``.
"""

import hashlib
import os
import shutil


def coverage_variant_active( env ):
    actions = env.get( "variant_actions" ) if hasattr( env, "get" ) else None
    if actions is None:
        try:
            actions = env["variant_actions"]
        except Exception:
            return False
    if not actions:
        return False
    try:
        return "cov" in actions
    except Exception:
        return False


def coverage_notes_prefix( env, program ):
    """Absolute directory for this binary's relocated ``.gcda`` notes.

    ``None`` when coverage is not active. The same path is used for the test
    process and for the later gcov / gcovr invocation.
    """
    if not coverage_variant_active( env ):
        return None
    # A SCons NodeList stringifies as "['path']", which is not a path. Index
    # it the same way gcov_program_id does. A plain string must not be indexed.
    try:
        if isinstance( program, ( str, bytes ) ):
            program_text = str( program )
        else:
            program_text = str( program[0] )
    except Exception:
        program_text = str( program )
    name = os.path.splitext( os.path.basename( program_text ) )[0] or "program"
    script = ""
    try:
        script = str( env["sconscript_file"] )
    except Exception:
        script = ""
    script_key = os.path.splitext( os.path.basename( script ) )[0] or "sconscript"
    root = None
    for key in ( "abs_build_dir", "build_dir" ):
        try:
            candidate = env[key]
        except Exception:
            candidate = None
        if candidate:
            root = str( candidate )
            break
    if not root:
        root = os.path.abspath( "_build" )
    elif not os.path.isabs( root ):
        root = os.path.abspath( root )
    path = os.path.join( root, "gcov-notes", script_key, name )
    try:
        os.makedirs( path, exist_ok=True )
    except OSError:
        pass
    return path


def gcov_text_dir( notes_prefix ):
    """Where ``gcov`` writes ``*.gcov`` for one binary (not the shared working dir)."""
    if not notes_prefix:
        return None
    path = os.path.join( notes_prefix, "gcov-text" )
    try:
        os.makedirs( path, exist_ok=True )
    except OSError:
        pass
    return path


def stage_gcov_source( text_dir, source_path ):
    """Make a relative source path openable from ``text_dir``.

    ``gcov`` writes ``*.gcov`` into its cwd and names them from the source
    argument. ``-r`` drops absolute paths. A symlink keeps the relative
    spelling (so the ``#`` filename stays the one coverage already renames)
    while cwd is a private directory.
    """
    if not text_dir or not source_path or os.path.isabs( source_path ):
        return source_path
    dest = os.path.join( text_dir, source_path )
    if os.path.lexists( dest ):
        return source_path
    parent = os.path.dirname( dest )
    if parent and not os.path.isdir( parent ):
        os.makedirs( parent )
    try:
        os.symlink( os.path.abspath( source_path ), dest )
    except OSError:
        return os.path.abspath( source_path )
    return source_path


def relocated_gcda_path( notes_prefix, object_stem ):
    """``.gcda`` path libgcov writes when ``GCOV_PREFIX_STRIP`` is ``0``.

    The prefix is prepended to the absolute note path. ``os.path.join`` cannot
    be used: an absolute second part discards the prefix.
    """
    if not notes_prefix or not object_stem:
        return None
    gcda = object_stem if str( object_stem ).endswith( ".gcda" ) else str( object_stem ) + ".gcda"
    if not os.path.isabs( gcda ):
        gcda = os.path.abspath( gcda )
    return os.path.join( notes_prefix, gcda.lstrip( os.sep ) )


def _place_file( source, dest ):
    if os.path.lexists( dest ):
        os.remove( dest )
    try:
        os.symlink( source, dest )
    except OSError:
        shutil.copy2( source, dest )


def stage_gcov_object( text_dir, object_stem, notes_prefix ):
    """Private ``-o`` stem whose ``.gcno`` and ``.gcda`` are the notes gcov should read.

    Returns the stem to pass as ``gcov -o``. Falls back to ``object_stem`` when
    there is nothing to stage.
    """
    if not text_dir or not object_stem or not notes_prefix:
        return object_stem
    stem = object_stem if os.path.isabs( object_stem ) else os.path.abspath( object_stem )
    if stem.endswith( ".gcda" ) or stem.endswith( ".gcno" ) or stem.endswith( ".o" ):
        stem = os.path.splitext( stem )[0]
    gcno = stem + ".gcno"
    beside = stem + ".gcda"
    relocated = relocated_gcda_path( notes_prefix, stem )
    gcda = relocated if relocated and os.path.isfile( relocated ) else beside
    if not os.path.isfile( gcno ) and not os.path.isfile( gcda ):
        return object_stem
    digest = hashlib.sha1( stem.encode( "utf-8", "replace" ) ).hexdigest()[:12]
    private = os.path.join( text_dir, "obj", digest, os.path.basename( stem ) )
    parent = os.path.dirname( private )
    if not os.path.isdir( parent ):
        os.makedirs( parent )
    if os.path.isfile( gcno ):
        _place_file( os.path.abspath( gcno ), private + ".gcno" )
    if os.path.isfile( gcda ):
        _place_file( os.path.abspath( gcda ), private + ".gcda" )
    return private


def apply_gcov_prefix( env_dict, notes_prefix ):
    """Set ``GCOV_PREFIX`` / ``GCOV_PREFIX_STRIP`` on a subprocess environment."""
    if not notes_prefix or env_dict is None:
        return env_dict
    env_dict["GCOV_PREFIX"] = notes_prefix
    env_dict["GCOV_PREFIX_STRIP"] = "0"
    return env_dict
