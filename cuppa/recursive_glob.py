
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

from cuppa.utility.types import is_string
from cuppa.log import logger
from cuppa.colourise import as_notice


def glob( start, file_pattern, exclude_dirs_pattern=None, discard_pattern=None ):

    if is_string( file_pattern ):
        file_pattern = re.compile( fnmatch.translate( file_pattern ) )

    if exclude_dirs_pattern:
        if is_string( exclude_dirs_pattern ):
            exclude_dirs_pattern = re.compile( fnmatch.translate( exclude_dirs_pattern ) )

    if discard_pattern:
        if is_string( discard_pattern ):
            discard_pattern = re.compile( fnmatch.translate( discard_pattern ) )

    matches = []
    subdir = False

    logger.trace( "file_pattern = [{}], start = [{}]".format( as_notice( file_pattern.pattern ), as_notice( start ) ) )

    for root, dirnames, filenames in os.walk( start ):

        if exclude_dirs_pattern:
            # remove any directories from the search that match the exclude regex
            dirnames[:] = [ d for d in dirnames if not exclude_dirs_pattern.match(d) ]

        exclude_this_dir = False
        matches_in_this_dir = []

        for filename in filenames:
            if subdir and discard_pattern and discard_pattern.match( filename ):
                # if we are in a subdir and it contains a file that matches the discard_pattern
                # set exclude_this_dir to True so later we can discard any local matches we'd
                # already encountered while walking the directory
                exclude_this_dir = True
                break
            if file_pattern.match( filename ):
                matches_in_this_dir.append( os.path.join( root, filename ) )

        if not exclude_this_dir:
            matches += matches_in_this_dir
        else:
            # We are excluding this directory and therefore all of its subdirs
            dirnames[:] = []

        # After the first pass through the loop we will be in a subdirectory
        subdir = True

    return matches
