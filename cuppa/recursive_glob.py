
#          Copyright Jamie Allsop 2012-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RecursiveGlob
#-------------------------------------------------------------------------------
import fnmatch
import re
import os

import cuppa.utility


def glob( start, pattern ):
    if cuppa.utility.is_string( pattern ):
        pattern = re.compile( fnmatch.translate( pattern ) )
    matches = []
    for root, dirnames, filenames in os.walk( start ):
        for filename in filenames:
            if pattern.match( filename ):
                matches.append( os.path.join( root, filename ) )
    return matches
