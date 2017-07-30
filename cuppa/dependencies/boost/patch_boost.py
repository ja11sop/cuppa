
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Patch Boost
#-------------------------------------------------------------------------------

import shlex
import subprocess
import os

# Cuppa Imports
from cuppa.colourise import as_info
from cuppa.log       import logger



def patched_boost_test( home ):
    patch_applied_path = os.path.join( home, "cuppa_test_patch_applied.txt" )
    return os.path.exists( patch_applied_path )



def apply_patch_if_needed( home ):

    patch_applied_path = os.path.join( home, "cuppa_test_patch_applied.txt" )
    diff_file = "boost_test_patch.diff"

    if os.path.exists( patch_applied_path ):
        logger.debug( "[{}] already applied".format( as_info( diff_file ) ) )
        return

    diff_path = os.path.join( os.path.split( __file__ )[0], "boost", diff_file )

    command = "patch --batch -p1 --input={}".format( diff_path )

    logger.info( "Applying [{}] using [{}] in [{}]".format(
            as_info( diff_file ),
            as_info( command ),
            as_info( home )
    ) )

    if subprocess.call( shlex.split( command ), cwd=home ) != 0:
        logger.error( "Could not apply [{}]".format( diff_file ) )

    with open( patch_applied_path, "w" ) as patch_applied_file:
        pass
