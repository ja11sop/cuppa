
#          Copyright Jamie Allsop 2022-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   AsciidocToHtmlMethod
#-------------------------------------------------------------------------------

# Python imports
import json
import os.path
import re
import shlex
import sys

from SCons.Script import Flatten

# cuppa imports
import cuppa.progress
from cuppa.output_processor import IncrementalSubProcess
from cuppa.log import logger
from cuppa.colourise import as_notice, as_error, as_info, colour_items
from cuppa.utility.file_types import is_json, is_html, is_asciidoc, is_j2_template
from cuppa.utility.jinja2_renderer import render_template, target_from_template


def process_stdout( line ):
    sys.stdout.write( line + '\n' )


def process_stderr( line ):
    sys.stderr.write( line + '\n' )


def _value_from_node( node ):
    if node and isinstance( node, list ):
        return node[0]
    return node


def _get_variables_from_file( path, env ):
    if not env['clean']:
        logger.debug( "Reading variables file [{}]".format( str(path) ) )
        if os.path.exists( str(path) ):
            with open( str(path), 'r' ) as variables_file:
                return json.load( variables_file )
    return {}


def _get_variables_file( paths ):
    for path in paths:
        if is_json( str(path) ):
            return path
    return None


def _get_variables_from( paths, env ):
    variables_file = _get_variables_file( paths )
    if variables_file:
        return _get_variables_from_file( variables_file, env )
    return {}


class AsciidocToHtmlRunner(object):

    def __init__( self, env, plantuml_config=None, template_file=None, css_file=None, base_dir=None ):

        self._plantuml_config = _value_from_node( plantuml_config )
        self._template_file = _value_from_node( template_file )
        self._css_file = _value_from_node( css_file )
        if not base_dir:
            base_dir = env['sconstruct_dir']
        elif not os.path.isabs( str(base_dir) ):
            base_dir = os.path.join( env['sconstruct_dir'], str(base_dir) )

        self._ignore_sources = set()

        self._plantuml_config and self._ignore_sources.add( self._plantuml_config )
        self._template_file and self._ignore_sources.add( self._template_file )
        self._css_file and self._ignore_sources.add( self._css_file )

        self._command_template = "asciidoctor -r asciidoctor-diagram -B {}".format( base_dir )

        if self._plantuml_config:
            self._command_template += " -a config={}".format( str(self._plantuml_config) )
        self._command_template += " -o {} {}"


    def __call__( self, target, source, env ):

        targets = Flatten( [target] )
        sources = [ s for s in Flatten( [source] ) if str(s) not in self._ignore_sources ]

        variables = _get_variables_from( sources, env )

        html_targets = []
        for t in targets:
            is_html( str(t) ) and html_targets.append( t )
            logger.debug( "AsciidocToHtmlRunner: target = {}"
                          .format( as_info( str(t) ) ) )

        asciidoc_sources = []
        for s in sources:
            is_asciidoc( str(s) ) and asciidoc_sources.append( s )
            logger.debug( "AsciidocToHtmlRunner: source = {}"
                          .format( as_info( str(s) ) ) )

        target_iter = iter( targets )
        asciidoc_source_iter = iter( asciidoc_sources )

        for html_target in html_targets:

            current_target = next( target_iter )
            current_source = next( asciidoc_source_iter )
            html_asciidoc_source = current_source
            targets_created = []

            if self._template_file and str(current_target).endswith( "_template.asciidoc" ):

                logger.debug( "Rendering template file [{}] given [{}]"
                              .format( as_info( str(current_source) ), as_info( str(current_target) ) ) )

                targets_created = render_template( env, current_source, 0, variables, template_file=self._template_file, write=True )
                html_asciidoc_source = targets_created[-1]
                next( target_iter )
                current_target = next( target_iter )

            elif is_j2_template( current_target ) and is_asciidoc( current_target ):

                logger.debug( "Rendering template file [{}] given [{}]"
                              .format( as_info( str(current_source) ), as_info( str(current_target) ) ) )

                targets_created = render_template( env, current_source, 0, variables, write=True )
                html_asciidoc_source = targets_created[-1]
                next( target_iter )
                current_target = next( target_iter )

            elif str(current_target).endswith( "_rendered.asciidoc" ):
                targets_created = render_template( env, current_source, 0, variables, write=True )
                html_asciidoc_source = targets_created[-1]
                current_target = next( target_iter )

            logger.debug( "Created targets [{}]".format( colour_items( targets_created ) ) )

            html_target = current_target

            logger.debug( "HTML target = [{}]".format( as_info( str(html_target) ) ) )

            working_dir = os.getcwd()
            command = self._command_template.format( html_target.abspath, str(html_asciidoc_source) )
            logger.debug( "Creating HTML files using command [{}] in working directory [{}]".format( as_notice( command ), as_notice(working_dir) ) )

            try:
                return_code = IncrementalSubProcess.Popen2(
                        process_stdout,
                        process_stderr,
                        shlex.split( command ),
                        cwd=working_dir
                )

                if return_code < 0:
                    logger.error( "Execution of [{}] terminated by signal: {}".format( as_notice( command ), as_error( str(-return_code) ) ) )
                elif return_code > 0:
                    logger.error( "Execution of [{}] returned with error code: {}".format( as_notice( command ), as_error( str(return_code) ) ) )

            except OSError as error:
                logger.error( "Execution of [{}] failed with error: {}".format( as_notice( command ), as_error( str(error) ) ) )

        return None


class AsciidocToHtmlEmitter(object):

    def __init__( self, final_dir=None, plantuml_config=None, template_file=None, css_file=None ):

        self._final_dir = final_dir
        self._plantuml_config = _value_from_node( plantuml_config )
        self._template_file = _value_from_node( template_file )
        self._css_file = _value_from_node( css_file )


    def get_image_targets( self, asciidoc_path, working_path ):

        if not os.path.exists( asciidoc_path ):
            return []

        image_pattern = re.compile( r'\[mermaid,\s*target="(\w+)",\s*format=(\w+)\]' )
        include_pattern = re.compile( r'include::(.*)\[.*\]' )

        logger.debug( "search asciidoc file [{}] for image references".format( as_notice(asciidoc_path) ) )
        images = []
        with open( asciidoc_path, 'r' ) as asciidoc_file:

            for line in asciidoc_file:
                matches_image = re.match( image_pattern, line )
                if matches_image:
                    image = matches_image.group(1) + "." + matches_image.group(2)
                    logger.debug( "found image reference for [{}]".format( image ) )
                    images.append( image )
                else:
                    matches_include = re.match( include_pattern, line )
                    if matches_include:
                        include_path = matches_include.group(1)
                        logger.debug( "found include directive for asciidoc file [{}]".format( as_notice(include_path) ) )
                        if not os.path.isabs( include_path ):
                            include_path = os.path.join( os.path.split( asciidoc_path )[0], include_path )
                            logger.debug( "determining real path for asciidoc file as [{}]".format( as_notice(include_path) ) )
                        if include_path != asciidoc_path:
                            images.extend( self.get_image_targets( include_path, working_path ) )

        logger.debug( "{} image references where found and are {}".format( len(images), str(images) ) )
        return images


    def __call__( self, target, source, env ):

        targets = Flatten( [target] )
        sources = Flatten( [source] )

        for t in targets:
            logger.debug( "AsciidocToHtmlEmitter: target = {}"
                          .format( as_info( str(t) ) ) )

        for s in sources:
            logger.debug( "AsciidocToHtmlEmitter: source = {}"
                          .format( as_info( str(s) ) ) )

        if not self._final_dir:
            self._final_dir = env['abs_final_dir']
        elif not os.path.isabs( self._final_dir ):
            if self._final_dir.startswith( ".." ):
                self._final_dir = os.path.normpath( os.path.join( env['abs_build_dir'], self._final_dir ) )
            else:
                self._final_dir = os.path.join( env['abs_final_dir'], self._final_dir )

        variables = _get_variables_from( sources, env )

        asciidoc_to_search_for_images = []
        new_targets = []

        for source_node in sources:

            source_path = str(source_node)

            if is_asciidoc( source_path ):

                if is_j2_template( source_path ):
                    asciidoc_to_search_for_images.append( source_path )
                    new_targets.extend( render_template( env, source_node, 0, variables, write=False ) )
                else:
                    asciidoc_to_search_for_images.append( source_path )
                    if self._template_file:
                        new_targets.extend( render_template( env, source_node, 0, variables, template_file=self._template_file, write=False ) )

                if len(targets):
                    new_targets.append( targets[0] )
                    targets = targets[1:]
                else:
                    logger.debug( "Generating HTML target from source [{}]".format( as_notice(str(source_node)) ) )
                    path = os.path.join( self._final_dir, os.path.split( str(source_node) )[1] )
                    html_target = os.path.splitext( target_from_template( path ) )[0]
                    if html_target.endswith("_"):
                        html_target = html_target[:-1]
                    html_target += ".html"
                    new_targets.append( html_target )

        logger.debug( "new_targets = [{}]".format( str(new_targets) ) )

        target = []
        target.extend( new_targets )

        logger.debug( "asciidoc_to_search_for_images = [{}]".format( str(asciidoc_to_search_for_images) ) )

        image_targets = []
        for asciidoc_source in asciidoc_to_search_for_images:
            source.append( asciidoc_source )
            images = self.get_image_targets( asciidoc_source, env['abs_build_dir'] )
            for t in images:
                image_targets.append(t)

        if image_targets:
            logger.debug( "image_targets = [{}]".format(  colour_items( image_targets ) ) )
            for image_target in image_targets:
                t = os.path.join( self._final_dir, image_target )
                target.append( t )
                logger.debug( "appending_target [{}]".format( as_info(str(t)) ) )

        self._plantuml_config and source.append( self._plantuml_config )
        self._template_file and source.append( self._template_file )
        self._css_file and source.append( self._css_file )

        return target, source



class AsciidoctorToHtmlMethod(object):

    def __call__( self, env, target, source, final_dir=None, plantuml_config_file=None, template_file=None, css_file=None, base_dir=None ):

        env.AppendUnique( BUILDERS = {
            'AsciidocToHtml' : env.Builder(
                action  = AsciidocToHtmlRunner(
                        env,
                        plantuml_config=plantuml_config_file,
                        template_file=template_file,
                        css_file=css_file,
                        base_dir=base_dir
                ),
                emitter = AsciidocToHtmlEmitter(
                        final_dir=final_dir,
                        plantuml_config=plantuml_config_file,
                        template_file=template_file,
                        css_file=css_file
                )
            )
        } )

        html = env.AsciidocToHtml( target, source )

        cuppa.progress.NotifyProgress.add( env, html )
        return html


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "AsciidocToHtml", cls() )

