#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Tree
#-------------------------------------------------------------------------------


def get_all_children( node ):
    return node.all_children()


def filter_out( path, ignore_filter ):
    for ignore in ignore_filter:
        if path.startswith( ignore ):
            return True
    return False


# process_callback should have the signature process( node )
def process_tree( root, process_callback, ignore_filter=[], visited=set() ):
    path = str( root )
    children = get_all_children( root )

    if path in visited and children:
        process_callback( root )
        return

    visited.add( path )

    if filter_out( path, ignore_filter ):
        return

    process_callback( root )

    if children:
        for child in children[:-1]:
            process_tree( child, process_callback, ignore_filter, visited )
        process_tree( children[-1], process_callback, ignore_filter, visited )


def print_tree( root, ignore_filter=[], margin=[0], visited=set() ):
    path = str( root )
    children = get_all_children( root )

    def get_margin(m):
        return [" ","| "][m]

    margins = list(map(get_margin, margin[:-1]))

    if path in visited and children:
        print ''.join(margins + ['+-[', path, ']'])
        return

    visited.add( path )

    if filter_out( path, ignore_filter ):
        return

    print ''.join(margins + ['+-', path])

    if children:
        margin.append(1)
        for child in children[:-1]:
            print_tree( child, ignore_filter, margin, visited )
        margin[-1] = 0
        print_tree( children[-1], ignore_filter, margin, visited )
        margin.pop()
