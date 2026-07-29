
#          Copyright Jamie Allsop 2016-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   FilterMethod
#-------------------------------------------------------------------------------

from SCons.Script import Flatten

from cuppa.utility.filter import filter_nodes
from cuppa.log import logger


class FilterMethod:

    def __call__( self, env, nodes, match, exclude=None ):

        nodes = Flatten( [ nodes ] )

        logger.trace( "nodes = [{}]".format( str(nodes) ) )

        # Filter only selects among existing nodes; it does not create build
        # actions. Do not call NotifyProgress here — progress belongs to the
        # methods that emitted those nodes. Re-attaching filtered nodes would
        # only restate (or accidentally extend) the variant Finished set.
        filtered_nodes = filter_nodes( nodes, match, exclude )
        return filtered_nodes

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Filter", cls() )

