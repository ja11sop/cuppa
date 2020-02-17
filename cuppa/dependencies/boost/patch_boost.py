
#          Copyright Jamie Allsop 2011-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Patch Boost
#-------------------------------------------------------------------------------

import shlex
import subprocess
import os
import glob

# Cuppa Imports
from cuppa.colourise import as_info
from cuppa.log       import logger



def patched_boost_test( home ):
    patch_applied_path = os.path.join( home, "cuppa_test_patch_applied.txt" )
    return os.path.exists( patch_applied_path )



def apply_patch_if_needed( home, version_string ):

    patch_applied_path = os.path.join( home, "cuppa_test_patch_applied.txt" )

    expected_diff_file = os.path.join(
            os.path.split( __file__ )[0],
            "boost_test_patch_{}.diff".format( version_string )
    )

    available_diff_files = sorted( glob.glob( os.path.join(
            os.path.split( __file__ )[0],
            "boost_test_patch_*.diff"
    ) ), reverse=True )

    for diff_file in available_diff_files:
        if diff_file <= expected_diff_file:
            break

    logger.debug( "Using diff file [{}]".format( as_info( diff_file ) ) )

    if os.path.exists( patch_applied_path ):
        logger.debug( "[{}] already applied".format( as_info( diff_file ) ) )
        return

    command = "patch --batch -p1 --input={}".format( diff_file )

    logger.info( "Applying [{}] using [{}] in [{}]".format(
            as_info( diff_file ),
            as_info( command ),
            as_info( home )
    ) )

    if subprocess.call( shlex.split( command ), cwd=home ) != 0:
        logger.error( "Could not apply [{}]".format( diff_file ) )
    else:
        with open( patch_applied_path, "w" ):
            logger.debug( 'Write "patch_applied_file" to record the patch has been applied.' )
