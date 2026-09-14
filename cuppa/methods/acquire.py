#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   DownloadExtract / RemoveEmptyDirs (acquire / staging)
#-------------------------------------------------------------------------------

"""Graph nodes for fetching publisher source archives and staging cleanups.

Build-system agnostic: CMake publishers typically chain
``DownloadExtract`` → optional ``RemoveEmptyDirs`` → ``CMakeConfigure``.
"""

import os

from SCons.Script import Action

import cuppa.progress

from cuppa.buildsys.acquire import (
        archive_basename_from_url,
        download_extract,
        remove_empty_dirs,
)
from cuppa.colourise import as_error
from cuppa.log import logger
from cuppa.utility.download import DownloadError


def _node_abspath( path ):
    from SCons.Node import Node
    if isinstance( path, Node ):
        return path.abspath
    return os.path.abspath( str( path ) )


class RemoveEmptyDirsMethod(object):
    """``env.RemoveEmptyDirs(source, parent=…, names=None, gitmodules=None, …)``.

    Stamped graph node that removes empty immediate subdirectories of
    ``parent`` (see ``cuppa.buildsys.acquire.remove_empty_dirs``).

    - ``names=`` — definitive list (overrides ``gitmodules``)
    - ``gitmodules=True`` — restrict to submodule paths from
      ``<dirname(parent)>/.gitmodules`` when ``names`` is omitted
    - both omitted — every empty immediate child of ``parent``

    Use after extracting a source archive whose empty submodule placeholders
    defeat an upstream ``NOT EXISTS`` download gate, then feed the stamp into
    the next configure/build step.
    """

    def __call__(
            self,
            env,
            source,
            parent,
            names=None,
            gitmodules=None,
            target=None,
    ):
        if target is None:
            target = 'remove_empty_dirs.complete'
        parent = str( parent )
        if names is not None:
            names = tuple( str( name ) for name in names )

        def _action( target, source, env ):
            removed = remove_empty_dirs(
                    parent,
                    names=names,
                    gitmodules=gitmodules,
            )
            with open( str( target[0] ), 'w' ) as stamp:
                if removed:
                    stamp.write(
                            'removed empty dirs: {names}\n'
                            .format( names=', '.join( removed ) )
                    )
                else:
                    stamp.write( 'no empty dirs to remove\n' )
            return 0

        nodes = env.Command(
                target,
                source,
                Action(
                        _action,
                        'Removing empty directories under [{}]'.format( parent ),
                ),
        )
        cuppa.progress.NotifyProgress.add( env, nodes )
        return nodes

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'RemoveEmptyDirs', cls() )


class DownloadExtractMethod(object):
    """``env.DownloadExtract(url, extract_dir=…, marker=…, …)``.

    Downloads ``url`` with Cuppa progress into the variant working tree (or
    ``archive=`` basename), extracts into ``extract_dir``, flattens nested
    top directories ``strip_components`` times (default ``1`` for GitHub
    release tarballs), and stamps ``extract_dir/marker``.

    Registers ``env.Clean`` on ``extract_dir``.
    """

    def __call__(
            self,
            env,
            url,
            extract_dir,
            marker='CMakeLists.txt',
            strip_components=1,
            archive=None,
            target=None,
    ):
        extract_dir = str( extract_dir )
        marker = str( marker )
        if target is None:
            target = os.path.join( extract_dir, marker )

        archive_name = archive_basename_from_url( url, archive=archive )
        build_dir = env.get( 'build_dir' )
        if build_dir and not os.path.isabs( extract_dir ):
            archive_path = os.path.join( str( build_dir ), archive_name )
            extract_abs = os.path.join( str( build_dir ), extract_dir )
        else:
            extract_abs = _node_abspath( extract_dir )
            archive_path = os.path.join(
                    os.path.dirname( extract_abs ),
                    archive_name,
            )

        def _action( target, source, env ):
            try:
                download_extract(
                        url,
                        archive_path,
                        extract_abs,
                        strip_components=strip_components,
                        marker=marker,
                )
            except ( DownloadError, ValueError, OSError ) as error:
                logger.error( "DownloadExtract failed: {}".format(
                        as_error( str( error ) )
                ) )
                return 1
            return 0

        nodes = env.Command(
                target,
                [],
                Action(
                        _action,
                        'Downloading and extracting [{}]'.format( url ),
                ),
        )
        env.Clean( nodes, extract_dir )
        cuppa.progress.NotifyProgress.add( env, nodes )
        return nodes

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'DownloadExtract', cls() )
