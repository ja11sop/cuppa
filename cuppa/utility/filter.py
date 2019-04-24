#          Copyright Jamie Allsop 2017-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   filter
#-------------------------------------------------------------------------------

import fnmatch
import re

from cuppa.utility.types import is_string
from cuppa.colourise import as_notice
from cuppa.log import logger

from SCons.Script import Flatten


def filter_nodes( nodes, match_patterns, exclude_patterns=[] ):

    nodes = Flatten( nodes )

    if not match_patterns and not exclude_patterns:
        return nodes

    if match_patterns:
        match_patterns = Flatten( [ match_patterns ] )
        for i, match_pattern in enumerate(match_patterns):
            if is_string( match_pattern ):
                match_patterns[i] = re.compile( fnmatch.translate( match_pattern ) )

    if exclude_patterns:
        exclude_patterns = Flatten( [ exclude_patterns ] )
        for i, exclude_pattern in enumerate(exclude_patterns):
            if is_string( exclude_pattern ):
                exclude_patterns[i] = re.compile( fnmatch.translate( exclude_pattern ) )

    filtered_nodes = []

    for node in nodes:
        path = str( node )
        logger.trace( "Node in nodes to filter = [{}][{}]".format( as_notice(path), as_notice(node.path) ) )

        if exclude_patterns:
            excluded = False
            for exclude_pattern in exclude_patterns:
                if exclude_pattern.match( path ):
                    excluded = True
                    break
            if excluded:
                continue

        if not match_patterns:
            filtered_nodes.append( node )
        else:
            for match_pattern in match_patterns:
                if match_pattern.match( path ):
                    filtered_nodes.append( node )

    return filtered_nodes
