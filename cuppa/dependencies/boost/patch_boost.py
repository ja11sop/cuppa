
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
from cuppa.colourise import as_info, as_notice
from cuppa.log       import logger


def patched_boost_test( home ):
    patch_applied_path = os.path.join( home, "cuppa_test_patch_applied.txt" )
    return os.path.exists( patch_applied_path )


def apply_patches_if_needed( patch_boost_test, home, version_string ):
    if patch_boost_test:
        apply_patch( "test_patch", home, version_string )
    apply_patch( "patch", home, version_string )
    apply_patch( "hot_fix", home, version_string )
    apply_patch( "bug_fix", home, version_string )


def apply_patch( name, home, version_string ):
    patch_applied_path = os.path.join( home, "cuppa_{}_applied.txt".format( name ) )

    expected_diff_file = os.path.join(
            os.path.split( __file__ )[0],
            "boost_{}_{}.diff".format( name, version_string )
    )

    available_diff_files = sorted( glob.glob( os.path.join(
            os.path.split( __file__ )[0],
            "boost_{}_*.diff".format( name )
    ) ), reverse=True )

    diff_file_to_use = None
    for diff_file in available_diff_files:
        if name == "test_patch":
            if diff_file <= expected_diff_file:
                diff_file_to_use = diff_file
                break
        elif name == "patch":
            if diff_file <= expected_diff_file:
                diff_file_to_use = diff_file
                break
        # Note: Only apply fixes to the exact version of boost.
        elif name == "hot_fix":
            if diff_file == expected_diff_file:
                diff_file_to_use = diff_file
                break
        elif name == "bug_fix":
            if diff_file == expected_diff_file:
                diff_file_to_use = diff_file
                break

    if not diff_file_to_use:
        logger.debug( "Nothing to [{}] for: [{}]".format( as_notice( name ), as_info( version_string ) ) )
        return

    logger.debug( "Using diff file [{}]".format( as_info( diff_file_to_use ) ) )

    if os.path.exists( patch_applied_path ):
        logger.debug( "[{}] already applied".format( as_info( diff_file_to_use ) ) )
        return
    else:
        logger.info( "Applying [{}] for: [{}]".format( as_notice( name ), as_info( version_string ) ) )

    command = "patch --batch -p1 --input={}".format( diff_file_to_use )

    logger.info( "Applying [{}] using [{}] in [{}]".format(
            as_info( diff_file_to_use ),
            as_info( command ),
            as_info( home )
    ) )

    if subprocess.call( shlex.split( command ), cwd=home ) != 0:
        logger.error( "Could not apply [{}]".format( diff_file_to_use ) )
    else:
        with open( patch_applied_path, "w" ):
            logger.debug( 'Write "patch_applied_file" to record the patch has been applied.' )
