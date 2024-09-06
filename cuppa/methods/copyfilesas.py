
#          Copyright Jamie Allsop 2016-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CopyFilesAsMethod
#-------------------------------------------------------------------------------

import os.path

from SCons.Node import Node
from SCons.Script import Flatten

from cuppa.utility.filter import filter_nodes

import cuppa.progress


class CopyFilesAsMethod:

    def __call__( self, env, target, source, match=None, exclude=None ):

        destinations = []
        for destination in Flatten([target]):
            if not isinstance( destination, Node ):
                if destination[0] != '#' and not os.path.isabs( destination ):
                    destination = os.path.join( env['abs_final_dir'], destination )
            destinations.append( destination )

        filtered_nodes = filter_nodes( source, match, exclude )

        installed_files = env.InstallAs( destinations, filtered_nodes )
        cuppa.progress.NotifyProgress.add( env, installed_files )
        return installed_files

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CopyFilesAs", cls() )

