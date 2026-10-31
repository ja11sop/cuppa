#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Per-binary GCC/Clang ``.gcda`` isolation via ``GCOV_PREFIX``.

``.gcno`` is the notes file, written beside the ``.o`` at compile time.
``.gcda`` is the data file, written when the instrumented binary exits.
Tests that link the same object would otherwise share one ``.gcda``.

``GCOV_PREFIX`` sends each binary's ``.gcda`` under ``gcov-data/{program}/``.
``gcov`` does not read that variable: it opens the ``.gcno`` and ``.gcda``
next to ``-o``, and writes ``*.gcov`` into its current directory. Collection
links the ``.gcno`` beside the ``.gcda`` already written there, and starts
``gcov`` in ``gcov-data/{program}/gcov-run`` so two binaries do not write the
same ``*.gcov`` name. Project headers are not on that command line. After the
first run, each relative source ``gcov`` could not open is copied into
``gcov-run`` and ``gcov`` is run again so those ``.gcov`` files contain lines.
"""

import os
import re
import shutil

_ANSI = re.compile( r"\x1b\[[0-9;]*m" )
_CANNOT_OPEN_SOURCE = re.compile( r"^Cannot open source file (.+)$" )


def coverage_active( env ):
    return "cov" in ( env.get( "variant_actions" ) or {} )


def coverage_data_dir( env, program_path ):
    """``GCOV_PREFIX`` for this binary, or ``None``.

    ``abs_build_dir`` is already unique per sconscript and variant, and a
    program name is unique within it. libgcov creates the ``.gcda`` path.
    """
    if not coverage_active( env ):
        return None
    name = os.path.basename( str( program_path ) )
    return os.path.join( env["abs_build_dir"], "gcov-data", name )


def coverage_env_step( env, program_path ):
    """``prepare_env`` step for a measured test or benchmark process, or ``None``.

    Adds the relocation variables to the environment the spawn already chose.
    It does not decide what else the child inherits, and it does not change
    the working directory the sconscript gave the test.
    """
    data_dir = coverage_data_dir( env, program_path )
    if not data_dir:
        return None

    def add_gcov_prefix( child_env ):
        child_env["GCOV_PREFIX"] = data_dir
        child_env["GCOV_PREFIX_STRIP"] = "0"
        return child_env

    return add_gcov_prefix


def relocated_gcda_path( data_dir, object_stem ):
    """``.gcda`` path libgcov writes when ``GCOV_PREFIX_STRIP`` is ``0``.

    The prefix is prepended to the absolute note path. ``os.path.join`` cannot
    be used directly: an absolute second part discards the prefix.
    """
    gcda = os.path.abspath( str( object_stem ) + ".gcda" )
    return os.path.join( data_dir, gcda.lstrip( os.sep ) )


def gcov_run_dir( data_dir ):
    """Directory ``gcov`` is started in for one binary."""
    path = os.path.join( data_dir, "gcov-run" )
    os.makedirs( path, exist_ok=True )
    return path


def gcovr_output_dir( build_dir, program_name, data_dir=None ):
    """Directory where one program's gcovr HTML and JSON are written.

    gcovr puts the index, the detail pages, and the JSON beside ``-o``.
    Two programs must not share that directory: a glob of ``lim*.html`` also
    matches ``lim_table``. With ``cov`` active this is ``gcov-data/{program}/gcovr``.
    """
    if data_dir:
        path = os.path.join( data_dir, "gcovr" )
    else:
        path = os.path.join( build_dir, "gcovr", program_name )
    os.makedirs( path, exist_ok=True )
    return path


def stage_gcov_source( run_dir, source_path ):
    """Copy a relative source into ``gcov``'s working directory.

    ``gcov -r`` drops absolute sources and names ``*.gcov`` after the source
    argument, so the argument has to stay relative. The copy is Cuppa's: the
    build tree does not point back at the real source. An absolute path is
    returned unchanged and nothing is copied.
    """
    if os.path.isabs( source_path ):
        return source_path
    dest = os.path.join( run_dir, source_path )
    os.makedirs( os.path.dirname( dest ) or run_dir, exist_ok=True )
    shutil.copy2( os.path.abspath( source_path ), dest )
    return source_path


def missing_gcov_sources( output ):
    """Relative paths from ``Cannot open source file`` lines.

    ``gcov`` prints that when a path stored in the notes is not under its
    working directory. Absolute paths are omitted: ``gcov -r`` does not report
    them, and a private directory cannot stand in for a path opened as-is.
    """
    found = []
    seen = set()
    for line in ( output or "" ).splitlines():
        plain = _ANSI.sub( "", line ).strip()
        match = _CANNOT_OPEN_SOURCE.match( plain )
        if not match:
            continue
        path = match.group( 1 ).strip()
        if not path or os.path.isabs( path ) or path in seen:
            continue
        seen.add( path )
        found.append( path )
    return found


def stage_reported_gcov_sources( run_dir, output ):
    """Copy sources ``gcov`` could not open into its working directory.

    Returns true when at least one file was copied, so ``gcov`` can be run
    again and the regenerated ``.gcov`` files contain those source lines. A
    relative path that is not a file on disk is skipped.
    """
    staged = False
    for path in missing_gcov_sources( output ):
        if not os.path.isfile( os.path.abspath( path ) ):
            continue
        stage_gcov_source( run_dir, path )
        staged = True
    return staged


def _link_or_copy( source, dest ):
    if os.path.lexists( dest ):
        os.remove( dest )
    try:
        os.symlink( source, dest )
    except OSError:
        shutil.copy2( source, dest )


def stage_gcno( object_stem, data_dir ):
    """Link the ``.gcno`` beside this binary's relocated ``.gcda``.

    Returns the ``gcov -o`` stem. The ``.gcda`` is left where libgcov wrote it.
    Without that file, the absolute original stem is returned and ``gcov``
    reads the notes beside the object as before.
    """
    stem = os.path.abspath( object_stem )
    if stem.endswith( ( ".gcda", ".gcno", ".o" ) ):
        stem = os.path.splitext( stem )[0]
    gcno = stem + ".gcno"
    gcda = relocated_gcda_path( data_dir, stem )
    if not os.path.isfile( gcno ) or not os.path.isfile( gcda ):
        return stem
    beside = os.path.splitext( gcda )[0] + ".gcno"
    _link_or_copy( gcno, beside )
    return os.path.splitext( gcda )[0]
