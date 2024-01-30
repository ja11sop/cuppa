
#          Copyright Jamie Allsop 2023-2023
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Helpers for handling Variables in Builders
#-------------------------------------------------------------------------------

import os.path
import json
import yaml
from cuppa.utility.file_types import is_json_ext, is_yaml_ext
from cuppa.colourise import as_notice, colour_items
from cuppa.log import logger


def process_variables( env, variables_file_id, variables=None, variables_file=None, yaml_loader=None ):

    if variables:
        variables_file = env.File( os.path.join( env['abs_build_dir'], "_j2_variables_file_{}.json".format( str(variables_file_id) ) ) )
        with open( str(variables_file), 'w' ) as variables_fp:
            json.dump( variables, variables_fp )

    if variables_file:
        file_path = str(variables_file)
        file_ext = str(os.path.splitext( file_path )[1] )
        if not variables:
            variables = {}
        data = {}
        with open( file_path, 'r' ) as variables_data:
            if is_json_ext( file_ext ):
                data = json.load( variables_data )
            elif is_yaml_ext( file_ext ):
                if yaml_loader:
                    data = yaml.load( variables_data, yaml_loader )
                else:
                    data = yaml.safe_load( variables_data )
        if data:
            logger.debug( "loaded variables [{}] from file [{}]".format( colour_items( data ), as_notice( file_path ) ) )
            variables.update( data )

    using_variables_file = variables_file and True or False
    return using_variables_file, variables_file, variables
