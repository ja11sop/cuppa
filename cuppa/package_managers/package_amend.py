#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Metadata-only package amend helpers
#-------------------------------------------------------------------------------

"""Helpers for ``--amend-package-manifest`` (rewrite traveling metadata, retar).

See ``design/plans/package-metadata-amend.md``.
"""

import os

from cuppa.colourise import as_info
from cuppa.log import logger


OPTION_NAME = 'amend-package-manifest'


def amend_package_manifest_enabled( env ):
    """True when ``--amend-package-manifest`` is set on ``env``."""
    getter = getattr( env, 'get_option', None )
    if callable( getter ):
        return bool( getter( OPTION_NAME ) )
    return False


def package_stage_has_payload( package_base_dir ):
    """True when ``package_base_dir`` has an ``include/`` or ``lib/`` tree."""
    if not package_base_dir or not os.path.isdir( package_base_dir ):
        return False
    for name in ( 'include', 'lib' ):
        if os.path.isdir( os.path.join( package_base_dir, name ) ):
            return True
    return False


def skip_builder_for_amend( env, target, label ):
    """Register a no-op stamp Command so upstream acquire/CMake nodes stay linked.

    Used when ``--amend-package-manifest`` is set so ``DownloadExtract`` /
    ``CMakeConfigure`` / ``CMakeBuild`` / ``CMakeInstall`` do not fetch or rebuild
    while ``PublishPackage`` still receives a graph predecessor.
    """
    from SCons.Script import Action

    import cuppa.progress

    logger.info(
            "Skipping [{}] because --{} is set".format(
                    as_info( label ), OPTION_NAME
            )
    )

    def _action( target, source, env ):
        path = str( target[0] )
        parent = os.path.dirname( path )
        if parent:
            os.makedirs( parent, exist_ok=True )
        with open( path, 'w', encoding='utf-8' ) as handle:
            handle.write( 'skipped: {}\n'.format( OPTION_NAME ) )
        return 0

    nodes = env.Command(
            target,
            [],
            Action( _action, 'Amend skip [{}]'.format( label ) ),
    )
    cuppa.progress.NotifyProgress.add( env, nodes )
    return nodes
