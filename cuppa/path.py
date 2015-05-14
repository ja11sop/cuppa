#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Path
#-------------------------------------------------------------------------------

# Python Standard
import os.path


def split_common( path1, path2 ):

    drive1, p1 = os.path.splitdrive( path1 )
    drive2, p2 = os.path.splitdrive( path2 )

    if drive1 != drive2:
        return None, path1, path2

    p1_elements = p1.split( os.path.sep )
    p2_elements = p2.split( os.path.sep )

    p1_len = len( p1_elements )
    p2_len = len( p2_elements )

    max_index = min( p1_len, p2_len )
    index = 0

    common = [ drive1 ]
    while index < max_index:
        if p1_elements[index] == p2_elements[index]:
            common.append( p1_elements[index] )
            index = index+1
        else:
            break;

    return os.path.join( '', *common ), os.path.join( '', *p1_elements[index:] ), os.path.join( '', *p2_elements[index:] )
