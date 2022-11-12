
#          Copyright Jamie Allsop 2022-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RenderJinjaTemplateMethod
#-------------------------------------------------------------------------------

import cuppa.progress
from cuppa.log import logger
from cuppa.colourise import as_notice


class RenderTemplateAction(object):

    def __init__( self, base_path, **variables ):
        self._base_path = base_path
        self._variables = variables

    def __call__( self, target, source, env ):
        import os.path
        from jinja2 import Environment, FileSystemLoader

        path_offset = os.path.relpath( os.path.split( source[0].abspath )[0], start=self._base_path )
        logger.debug( "path_offset for rendered template files calculated as [{}]".format( as_notice( path_offset ) ) )
        templates_path = os.path.split( source[0].abspath )[0]
        logger.debug( "creating jinja2 environment using templates_path [{}]".format( as_notice( templates_path ) ) )
        self._jinja_env = Environment( loader=FileSystemLoader( templates_path ) )

        for s in source:
            source_file = os.path.split( s.abspath )[1]
            logger.debug( "reading and rendering template file [{}]...".format( as_notice( source_file ) ) )
            template = self._jinja_env.get_template( source_file )
            rendered_string = template.render( **self._variables )
            t = os.path.join( env['abs_final_dir'], path_offset, source_file )
            with open( t, "w" ) as output:
                output.write( rendered_string )

        return None


class RenderTemplateEmitter(object):

    def __init__( self, base_path ):
        self._base_path = base_path

    def __call__( self, target, source, env ):
        import os.path
        path_offset = os.path.relpath( os.path.split( source[0].abspath )[0], start=self._base_path )

        for s in source:
            source_file = os.path.split( s.abspath )[1]
            t = os.path.join( env['abs_final_dir'], path_offset, source_file )
            target.append( t )

        return target, source


class RenderJinjaTemplateMethod(object):

    def __call__( self, env, target, source, final_dir=None, base_path=None, **variables ):
        if final_dir == None:
            final_dir = env['abs_final_dir']

        if base_path == None:
            base_path = env['sconstruct_dir']

        env.AppendUnique( BUILDERS = {
            'RenderJinjaTemplateBuilder' : env.Builder(
                action = RenderTemplateAction( base_path, **variables ),
                emitter = RenderTemplateEmitter( base_path )
        ) } )

        from SCons.Script import Flatten
        source = Flatten( source )

        rendered_templates = env.RenderJinjaTemplateBuilder( target, source )
        cuppa.progress.NotifyProgress.add( env, rendered_templates )
        return rendered_templates

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "RenderJinjaTemplate", cls() )
