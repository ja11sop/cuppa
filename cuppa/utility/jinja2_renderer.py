
#          Copyright Jamie Allsop 2023-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Helpers for rendering Jinja2 templates
#-------------------------------------------------------------------------------

import os.path
import shutil

from cuppa.colourise import as_info, as_notice, as_error, as_error_label, colour_items
from cuppa.log import logger
from cuppa.utility.variables import process_variables


_jinja_extensions = set([
    ".j2",
    ".jinja2",
    ".jinja"
])


def target_from_template( path ):
    inner_path, outer_extension = os.path.splitext( path )
    file_path, inner_extension = os.path.splitext( inner_path )
    if outer_extension in _jinja_extensions:
        return inner_path
    elif inner_extension in _jinja_extensions:
        return file_path + outer_extension
    return path


def is_template( path ):
    inner_path, outer_extension = os.path.splitext( path )
    file_path, inner_extension = os.path.splitext( inner_path )
    if outer_extension in _jinja_extensions:
        return True
    elif inner_extension in _jinja_extensions:
        return True
    return False


def _process_variables( env, variables_id, template_variables ):
    if variables_id != 0:
        if isinstance( template_variables, dict ):
            return process_variables( env, variables_id, variables=template_variables )
        else:
            return process_variables( env, variables_id, variables_file=template_variables )
    return False, None, template_variables


def _path_is_outside_build_dir( env, path ):
    return os.path.relpath( path, start=env['abs_build_dir'] ).startswith( ".." )


def _get_build_path_from( env, path ):
    if _path_is_outside_build_dir( env, str(path) ):
        path = str(path)
        offset_path = os.path.relpath( path, start=env['sconstruct_dir'] )
        path = os.path.join( env['abs_build_dir'], offset_path )
    return path


def _copy_if_needed_to_build_dir( env, source_path, target_path=None ):
    source_path = str(source_path)
    target_path = target_path and str(target_path) or None
    if not target_path and not _path_is_outside_build_dir( env, source_path ):
        return None
    elif not target_path:
        target_path = _get_build_path_from( env, source_path )
    else:
        target_path = _get_build_path_from( env, target_path )
    target_dir = os.path.split( target_path )[0]
    if not os.path.exists( target_dir ):
        logger.debug( "target directory [{}] under [{}] does not exist, creating".format( as_info( target_dir ), as_notice( os.getcwd() ) ) )
        os.makedirs( target_dir )
    logger.debug( "Copying [{}] to [{}]".format( as_notice( source_path ), as_notice( target_path ) ) )
    shutil.copy2( source_path, target_path )
    return target_path


def render_template( env, source, variables_id, template_variables, template_file=None, write=False ):

    base_path = env['sconstruct_dir']
    templates_search_path = env['abs_build_dir']

    logger.debug( "source             = {}".format( as_info( str(source) ) ) )
    logger.debug( "template_file      = {}".format( as_info( str(template_file) ) ) )
    logger.debug( "variables_id       = {}".format( as_info( str(variables_id) ) ) )
    logger.debug( "template_variables = {}".format( as_info( str(template_variables) ) ) )
    logger.debug( "abs_build_dir      = {}".format( as_info( str(env['abs_build_dir']) ) ) )

    logger.debug( "templates_search_path is [{}]".format( as_notice( os.path.abspath( str(templates_search_path) ) ) ) )

    from jinja2 import Environment, FileSystemLoader, TemplateNotFound

    target_files = []

    use_file, variables_file, variables = _process_variables( env, variables_id, template_variables )

    source_path = None

    if _path_is_outside_build_dir( env, source.abspath ):
        source_path = os.path.join( templates_search_path, os.path.relpath( source.abspath, start=base_path ) )
        logger.debug( "source_path [{}] outside templates_search_path [{}] making source_path=[{}]"
                      .format( as_notice( str(source) ), as_notice( templates_search_path ), as_info(source_path) ) )
    else:
        source_path = source.abspath
        logger.debug( "source_path [{}] already inside templates_search_path [{}] making source_path=[{}]"
                      .format( as_notice( str(source) ), as_notice( templates_search_path ), as_info(source_path) ) )

    source_template = template_file and os.path.splitext( target_from_template( source_path ) )[0] + "_template.asciidoc" or source_path
    target_rendered_template = os.path.splitext( target_from_template( source_path ) )[0] + "_rendered.asciidoc"

    target_files.append( source_template )

    if write:
        if template_file:
            logger.debug( "copying template [{}] to [{}]".format( as_notice( str(template_file) ), as_notice( str(source_template) ) ) )
            _copy_if_needed_to_build_dir( env, template_file, source_template )
        elif source.abspath != source_template:
            logger.debug( "copying template [{}] to [{}]".format( as_notice( str(source) ), as_notice( str(source_template) ) ) )
            _copy_if_needed_to_build_dir( env, str(source), source_template )

    logger.debug( "target_rendered_template = [{}]".format( as_info(target_rendered_template) ) )
    target_files.append( target_rendered_template )

    if write:

        logger.debug( "creating jinja2 environment using templates_search_path [{}]".format( as_notice( templates_search_path ) ) )

        jinja_env = Environment( loader=FileSystemLoader( templates_search_path ) )

        if os.path.isabs( source_template ):
            source_template = os.path.relpath( source_template, start=templates_search_path )

        logger.debug( "reading and rendering template file [{}] to [{}]...".format( as_notice( source_template ), as_notice( target_rendered_template ) ) )

        try:
            template = jinja_env.get_template( source_template )

            logger.debug( "using variables {{{}}}".format( colour_items( variables ) ) )

            rendered_string = template.render( **variables )

            logger.debug( "template to be rendered to [{}]".format( as_notice( target_rendered_template ) ) )

            logger.debug( "writing rendered file [{}]".format( as_notice( target_rendered_template ) ) )
            with open( target_rendered_template, "w" ) as output:
                output.write( rendered_string )

        except TemplateNotFound as error:
            logger.error( "{} {}".format( as_error_label( "TemplateNotFound:"), as_error( str(error) ) ) )

    return target_files
