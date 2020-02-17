
#          Copyright Jamie Allsop 2019-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ExpandTemplateFileMethod
#-------------------------------------------------------------------------------

import cuppa.progress
from cuppa.log import logger
from cuppa.colourise import as_notice

class ExpandTemplateFileAction(object):

    def __init__( self, kwargs ):
        self._kwargs = kwargs

    def __call__( self, target, source, env ):
        from SCons.Script import Flatten
        logger.debug( "reading template file [{}]".format( as_notice( str(source[0]) ) ) )
        with open( str(Flatten(source)[0]), 'r' ) as template_file:
            logger.debug( "open target file [{}]".format( as_notice(str(target[0])) ) )
            with open( str(target[0]), 'w' ) as expanded_file:
                logger.debug( "expand variables matching [{}]".format( as_notice(str(self._kwargs)) ) )
                expanded_file.write( template_file.read().format( **self._kwargs ) )
        return None


class ExpandTemplateFileMethod(object):

    def __call__( self, env, target, source, final_dir=None, **kwargs ):
        if final_dir == None:
            final_dir = env['abs_final_dir']

        env.AppendUnique( BUILDERS = {
            'ExpandTemplateFile' : env.Builder(
                action = ExpandTemplateFileAction( kwargs )
        ) } )

        expanded_template = env.ExpandTemplateFile( target, source )
        cuppa.progress.NotifyProgress.add( env, expanded_template )
        return expanded_template

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "ExpandTemplateFile", cls() )
