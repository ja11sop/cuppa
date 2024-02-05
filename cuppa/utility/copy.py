
#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Helpers for copying
#-------------------------------------------------------------------------------

import glob
import os
import shutil

from SCons.Script import Flatten

# from cuppa.colourise import as_notice, as_info, colour_items
# from cuppa.log import logger


def copy_remote_to_local( env, source_match, remote_dir, local_dir=None ):

    if not local_dir:
        local_dir = env['sconstruct_dir']

    remote_source_match = remote_dir + source_match
    remote_sources = "*" in source_match and glob.glob( remote_source_match ) or [ remote_source_match ]

    local_sources = []
    for remote_source in Flatten( remote_sources ):

        local = os.path.relpath( remote_source, start=remote_dir )
        local = os.path.join( local_dir, local )
        local_sources.append( local )

        if not env['clean']:
            local_folder = os.path.split( local )[0]
            if not os.path.exists( local_folder ):
                os.makedirs( local_folder, exist_ok=True )
            shutil.copy2( remote_source, local )

    if local_sources and len(local_sources) > 1:
        return env.Glob( local_dir + source_match )
    elif local_sources:
        return env.File( local_dir + source_match )
    return []
