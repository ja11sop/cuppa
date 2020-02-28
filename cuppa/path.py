#          Copyright Jamie Allsop 2015-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Path
#-------------------------------------------------------------------------------

# Python Standard
import os
import hashlib

from cuppa.log import logger
from cuppa.colourise import as_notice, as_error
from cuppa.utility.python2to3 import as_byte_str


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



def unique_short_filename( filename, max_length=48 ):
    hasher = hashlib.md5()
    hasher.update( as_byte_str( filename ) )
    digest = hasher.hexdigest()
    short_digest = "~" + digest[-8:]
    splice_length = min( len(filename), max_length-len(short_digest) )
    return filename[:splice_length] + short_digest



def lazy_create_path( path ):
    if not os.path.exists( path ):
        try:
            os.makedirs( path )
        except os.error as e:
            if not os.path.exists( path ):
                logger.error( "Could not create path [{}]. Failed with error [{}]".format( as_notice(path), as_error(str(e)) ) )
