
#          Copyright Jamie Allsop 2016-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CopyFilesMethod
#-------------------------------------------------------------------------------

import os.path

from SCons.Node import Node

from cuppa.utility.filter import filter_nodes

from cuppa.colourise import colour_items
from cuppa.log import logger


class CopyFilesMethod:

    def __call__( self, env, target, source, match=None, exclude=None ):
        destination = target
        if not isinstance( destination, Node ):
            if destination[0] != '#' and not os.path.isabs( destination ):
                destination = os.path.join( env['abs_final_dir'], destination )

        filtered_nodes = filter_nodes( source, match, exclude )

        if filtered_nodes:

            logger.trace( "filtered_nodes = [{}]".format( colour_items( [str(n) for n in filtered_nodes ] ) ) )

            # Progress comes from MethodWithProgress wrapping Install on the
            # sconscript env — do not NotifyProgress.add again here.
            return env.Install( destination, filtered_nodes )
        return []

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CopyFiles", cls() )

