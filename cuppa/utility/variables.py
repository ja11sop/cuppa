
#          Copyright Jamie Allsop 2023-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Helpers for handling Variables in Builders
#-------------------------------------------------------------------------------

import os.path
import json
import yaml

from SCons.Node import Node

from cuppa.utility.file_types import is_json_ext, is_yaml_ext
from cuppa.colourise import as_notice, as_info, colour_items
from cuppa.log import logger


def write_variables_file_for( variables, source, env ):

    if not isinstance( source, Node ):
        source = env.File( source )

    logger.debug( "str(source) = [{}]".format( as_notice( str(source) ) ) )
    logger.debug( "source.abspath = [{}]".format( as_notice( source.abspath ) ) )

    relpath = os.path.relpath( source.abspath, start=env['abs_build_dir'] )
    logger.debug( "relpath = [{}]".format( as_notice( relpath ) ) )

    path_outside_build_dir = relpath.startswith( ".." )
    logger.debug( "path outside buid dir=[{}]: path=[{}], build_dir=[{}]"
                  .format( as_info(str(path_outside_build_dir)),
                           as_notice(source.abspath),
                           as_notice(env['abs_build_dir'] ) ) )

    target = source.abspath
    if path_outside_build_dir:
        offset = os.path.relpath( source.abspath, start=env['sconstruct_dir'] )
        logger.debug( "offset = [{}]".format( as_info(offset) ) )
        target = os.path.join( env['abs_build_dir'], offset )

    target = os.path.splitext( target )[0] + "_variables.json"
    logger.debug( "variables_file for [{}] = [{}]".format( as_info(str(source)), as_info(target) ) )

    if not env['clean']:
        os.makedirs( os.path.split( target )[0], exist_ok=True )
        with open( target, 'w' ) as variables_file:
            json.dump( variables, variables_file )
    return target


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
