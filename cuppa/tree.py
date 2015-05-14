#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Tree
#-------------------------------------------------------------------------------


def get_all_children( node ):
    return node.all_children()


# process_callback should have the signature process( node )
def process_tree( root, process_callback, visited=set() ):
    path = str( root )
    children = get_all_children( root )

    if path in visited and children:
        return

    visited.add( path )
    process_callback( root )

    if children:
        for child in children[:-1]:
            process_tree( child, process_callback, visited )
        process_tree( children[-1], process_callback, visited )
