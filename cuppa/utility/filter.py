
#          Copyright Jamie Allsop 2017-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   filter
#-------------------------------------------------------------------------------

import fnmatch
import os
import re

from cuppa.utility.types import is_string
from cuppa.colourise import as_notice, colour_items, as_warning
from cuppa.log import logger

from SCons.Node import  Node
from SCons.Script import Flatten


def _node_path_forms( node ):
    """Path strings worth matching against for Filter patterns.

    StaticGlob often yields sconscript-relative ``node.path`` while SCons
    ``Glob`` / absolute ``File`` nodes stringify as absolute paths. Patterns
    written in either style should work for both sources.
    """
    seen = set()
    forms = []
    for raw in ( str( node ), getattr( node, 'path', None ), getattr( node, 'abspath', None ) ):
        if not raw:
            continue
        candidates = ( raw, raw.replace( '\\', '/' ) )
        for candidate in candidates:
            if candidate not in seen:
                seen.add( candidate )
                forms.append( candidate )
    return forms


def _any_form_matches( forms, patterns ):
    for form in forms:
        for pattern in patterns:
            if pattern.match( form ):
                return True
    return False


def _node_exists_as_file( node, forms ):
    """True if the node looks like a non-directory file (or a not-yet-written file)."""
    probe = getattr( node, 'abspath', None ) or ( forms and forms[0] ) or str( node )
    if not os.path.exists( probe ):
        if os.path.splitext( probe )[1] == "":
            logger.warn( "filtered node is probably a directory [{}]".format( as_warning( str( node ) ) ) )
            return False
        return True
    if os.path.isdir( probe ):
        logger.warn( "filtered node is a directory [{}]".format( as_warning( str( node ) ) ) )
        return False
    return True


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
        if not isinstance( node, Node ):
            continue
        forms = _node_path_forms( node )
        path = forms[0] if forms else str( node )

        logger.trace( "node in nodes to filter = [{}][{}]".format( as_notice(path), as_notice( getattr( node, 'path', '' ) ) ) )

        if exclude_patterns and _any_form_matches( forms, exclude_patterns ):
            continue

        if not match_patterns:
            filtered_nodes.append( node )
        elif _any_form_matches( forms, match_patterns ) and _node_exists_as_file( node, forms ):
            filtered_nodes.append( node )

        logger.trace( "filtered nodes = [{}]".format( colour_items( [ str(f) for f in filtered_nodes ] ) ) )

    return filtered_nodes
