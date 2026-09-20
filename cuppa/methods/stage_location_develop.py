#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   StageLocationDevelop — package-shaped stage for location L3 tip consume
#-------------------------------------------------------------------------------

"""Install ``include/`` + ``lib/`` (+ optional ``modules/``) under
``final/<name>/<version>/`` so tip ``--develop`` can resolve a location stage.
"""

from __future__ import annotations

import os

from SCons.Script import Flatten

from cuppa.colourise import as_info, as_notice
from cuppa.log import logger


class StageLocationDevelopMethod:
    """Stage a location project for tip consume (L3 baseline).

    Writes ``abs_final_dir/<name>/<version>/{include,lib}`` and, when modules are
    active, ``modules/`` via ``install_packaged_modules``.
    """

    def __call__(
            self,
            env,
            name,
            libs,
            include_dir="#/include",
            version=None,
            **_kwargs,
    ):
        version = str( version or "develop" )
        stage = os.path.join( env["abs_final_dir"], name, version )
        lib_dir = os.path.join( stage, "lib" )
        include_dest_root = os.path.join( stage, "include" )

        installed = []
        for lib in Flatten( [ libs ] ):
            installed.extend( env.Install( lib_dir, lib ) )

        include_root = env.Dir( include_dir ).get_abspath()
        if os.path.isdir( include_root ):
            for dirpath, _dirnames, filenames in os.walk( include_root ):
                for filename in filenames:
                    source = os.path.join( dirpath, filename )
                    relative = os.path.relpath( source, include_root )
                    destination = os.path.join( include_dest_root, relative )
                    installed.extend( env.InstallAs( destination, source ) )

        if env.get( "modules" ):
            from cuppa.cpp.cxx_modules import install_packaged_modules
            module_nodes = install_packaged_modules( env, stage )
            if module_nodes:
                installed.extend( Flatten( [ module_nodes ] ) )
                for lib_node in Flatten( [ libs ] ):
                    env.Depends( lib_node, module_nodes )

        logger.info(
                "Staged location develop [{}] under [{}]".format(
                        as_info( name ),
                        as_notice( stage ),
                )
        )
        return installed


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "StageLocationDevelop", cls() )
