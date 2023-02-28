
#          Copyright Jamie Allsop 2023-2023
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   File Types
#-------------------------------------------------------------------------------

import os.path


def is_json_ext( ext ):
    if ext:
        return ext.lower() == ".json"
    return False


def is_yaml_ext( ext ):
    if ext:
        ext = ext.lower()
        return ext == ".yaml" or ext == ".yml"
    return False


def is_json( file_path ):
    return is_json_ext( os.path.splitext( file_path )[1] )


def is_yaml( file_path ):
    return is_yaml_ext(  os.path.splitext( file_path )[1] )
