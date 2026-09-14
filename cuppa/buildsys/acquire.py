#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Acquire / staging helpers (download, extract, empty-dir cleanup)
#-------------------------------------------------------------------------------

"""Build-system-agnostic helpers for publisher source trees.

``download_extract`` fetches an archive (Cuppa progress) and unpacks it into a
working directory. ``remove_empty_dirs`` clears empty submodule placeholders
left by GitHub-style source archives. Graph methods live in
``cuppa.methods.acquire`` (``env.DownloadExtract`` / ``env.RemoveEmptyDirs``).

These are not CMake-specific: CMake publishers compose them with
``env.CMakeConfigure``, but Autotools / Meson / b2 publishers can use the same
acquire path.
"""

from __future__ import annotations

import os
import shutil
import tarfile
import zipfile

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse  # type: ignore

from cuppa.log import logger
from cuppa.colourise import as_info, as_notice
from cuppa.utility.download import (
        DownloadError,
        download_file,
        extract_tar_archive,
        extract_zip_archive,
)


def gitmodules_paths( gitmodules_path ):
    """Return submodule ``path =`` values from a ``.gitmodules`` file.

    Only reads ``path =`` lines (tolerates tabs/spaces). Missing file → empty
    list. Does not validate that the paths exist on disk.
    """
    path = str( gitmodules_path )
    if not os.path.isfile( path ):
        return []
    paths = []
    with open( path ) as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped.lower().startswith( 'path' ):
                continue
            if '=' not in stripped:
                continue
            key, value = stripped.split( '=', 1 )
            if key.strip().lower() != 'path':
                continue
            value = value.strip()
            if value:
                paths.append( value )
    return paths


def resolve_gitmodules_path( parent, gitmodules ):
    """Resolve a ``.gitmodules`` path for ``remove_empty_dirs``.

    ``gitmodules``:

    - ``True``: ``<dirname(parent)>/.gitmodules`` (extract root when
      ``parent`` is ``…/third_party``)
    - ``str`` / path: that file
    - ``False`` / ``None``: no file (caller skips gitmodules filtering)
    """
    if not gitmodules:
        return None
    if gitmodules is True:
        return os.path.join(
                os.path.dirname( os.path.abspath( str( parent ) ) ),
                '.gitmodules',
        )
    return str( gitmodules )


def gitmodules_child_names( parent, gitmodules_path ):
    """Immediate child names of ``parent`` that appear as submodule paths.

    For each ``path =`` in ``.gitmodules`` (repo-relative to the file's
    directory), if that path resolves to an immediate child of ``parent``,
    include its basename. Nested submodule paths (for example
    ``third_party/cares/cares`` when ``parent`` is ``third_party``) are
    skipped — only direct children are candidates for ``remove_empty_dirs``.
    """
    gitmodules_path = str( gitmodules_path )
    repo_root = os.path.dirname( os.path.abspath( gitmodules_path ) )
    parent = os.path.abspath( str( parent ) )
    names = []
    seen = set()
    for rel in gitmodules_paths( gitmodules_path ):
        full = os.path.abspath( os.path.join( repo_root, rel ) )
        if os.path.dirname( full ) != parent:
            continue
        name = os.path.basename( full )
        if name not in seen:
            seen.add( name )
            names.append( name )
    return names


def remove_empty_dirs( parent, names=None, gitmodules=None ):
    """Remove empty immediate subdirectories of ``parent``.

    Returns the names that were removed, in candidate order. Non-existent
    paths and non-empty directories are left untouched.

    Candidate selection:

    - ``names`` given (non-``None``): **definitive** — only those names
      (``gitmodules`` is ignored)
    - ``names is None`` and ``gitmodules`` set (``True`` or path): only
      immediate children of ``parent`` listed in that ``.gitmodules``
    - ``names is None`` and no ``gitmodules``: every empty immediate
      child of ``parent``

    Reach for this after extracting a GitHub (or similar) source archive that
    leaves **empty** submodule placeholders. Some upstream build systems only
    fetch those trees when the path does not exist (for example gRPC's
    ``gRPC_DOWNLOAD_ARCHIVES``). Prefer ``env.RemoveEmptyDirs`` so the step
    is a stamped graph node.
    """
    removed = []
    parent = str( parent )
    if not os.path.isdir( parent ):
        return removed

    if names is not None:
        candidates = [ str( name ) for name in names ]
    else:
        gitmodules_path = resolve_gitmodules_path( parent, gitmodules )
        if gitmodules_path is not None:
            candidates = gitmodules_child_names( parent, gitmodules_path )
        else:
            candidates = sorted(
                    name for name in os.listdir( parent )
                    if os.path.isdir( os.path.join( parent, name ) )
            )

    for name in candidates:
        path = os.path.join( parent, name )
        if os.path.isdir( path ) and not os.listdir( path ):
            os.rmdir( path )
            removed.append( name )
    return removed


def archive_basename_from_url( url, archive=None ):
    """Return a local archive filename for ``url`` (or an explicit ``archive``)."""
    if archive:
        return os.path.basename( str( archive ) )
    path = urlparse( str( url ) ).path
    name = os.path.basename( path )
    if not name or name in ( 'download', '/' ):
        raise ValueError(
                "cannot derive archive basename from url [{}]; pass archive="
                .format( url )
        )
    return name


def flatten_single_top_directory( path ):
    """If ``path`` has exactly one subdirectory entry, move its children up.

    Returns ``True`` when a top directory was removed. Empty ``path`` returns
    ``False`` (caller decides whether that is an error).
    """
    path = str( path )
    if not os.path.isdir( path ):
        return False
    entries = os.listdir( path )
    if not entries:
        return False
    top = os.path.join( path, entries[0] )
    if len( entries ) != 1 or not os.path.isdir( top ):
        return False
    for name in os.listdir( top ):
        shutil.move( os.path.join( top, name ), os.path.join( path, name ) )
    shutil.rmtree( top )
    return True


def _extract_archive( archive_path, extract_root ):
    if tarfile.is_tarfile( archive_path ):
        extract_tar_archive( archive_path, extract_root )
        return
    if zipfile.is_zipfile( archive_path ):
        extract_zip_archive( archive_path, extract_root )
        return
    raise DownloadError(
            "unsupported archive format for [{}]".format( archive_path )
    )


def download_extract(
        url,
        archive_path,
        extract_root,
        strip_components=1,
        marker=None,
):
    """Download ``url`` to ``archive_path`` and extract into ``extract_root``.

    Replaces ``extract_root`` when it already exists (SCons only runs the
    action when the marker is missing or sources are newer). Applies
    ``flatten_single_top_directory`` up to ``strip_components`` times (GitHub
    release tarballs usually need ``1``).

    When ``marker`` is set, requires ``os.path.join(extract_root, marker)`` to
    exist after extract and returns that path; otherwise returns
    ``extract_root``.
    """
    url = str( url )
    archive_path = str( archive_path )
    extract_root = str( extract_root )

    logger.info( "Downloading [{}] to [{}]...".format(
            as_info( url ),
            as_notice( archive_path ),
    ) )
    download_file( url, archive_path )

    if os.path.isdir( extract_root ):
        shutil.rmtree( extract_root )
    elif os.path.exists( extract_root ):
        os.remove( extract_root )
    os.makedirs( extract_root )

    logger.info( "Extracting [{}] into [{}]...".format(
            as_info( archive_path ),
            as_notice( extract_root ),
    ) )
    _extract_archive( archive_path, extract_root )

    remaining = int( strip_components or 0 )
    while remaining > 0:
        if not flatten_single_top_directory( extract_root ):
            break
        remaining -= 1

    if marker:
        marker_path = os.path.join( extract_root, str( marker ) )
        if not os.path.exists( marker_path ):
            raise DownloadError(
                    "extract of [{}] into [{}] did not produce marker [{}]"
                    .format( url, extract_root, marker )
            )
        return marker_path
    return extract_root
