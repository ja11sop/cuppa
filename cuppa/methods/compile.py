
#          Copyright Jamie Allsop 2013-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CompileMethod
#-------------------------------------------------------------------------------

import os.path
import cuppa.progress
from SCons.Script import Flatten
from SCons.Node import Node

from cuppa.colourise import as_notice
from cuppa.log import logger


class CompileMethod:

    def __init__( self, shared=False ):
        self._shared = shared


    def __call__( self, env, source, **kwargs ):
        sources = Flatten( [ source ] )
        objects = []
        if 'CPPPATH' in env:
            env.AppendUnique( INCPATH = env['CPPPATH'] )

        if self._shared:
            obj_prefix = env.subst('$SHOBJPREFIX')
            obj_suffix = env.subst('$SHOBJSUFFIX')
            obj_builder = env.SharedObject
        else:
            obj_prefix = env.subst('$OBJPREFIX')
            obj_suffix = env.subst('$OBJSUFFIX')
            obj_builder = env.Object

        logger.trace( "Build Root = [{}]".format( as_notice( env['build_root'] ) ) )

        dependencies = kwargs.get( 'depends_on', None )

        for source in sources:
            if not isinstance( source, Node ):
                source = env.File( source )

            if dependencies:
                env.Depends( source, Flatten( [ dependencies ] ) )

            logger.trace( "Object source = [{}]/[{}]".format( as_notice(str(source)), as_notice(source.path) ) )

            if os.path.splitext(str(source))[1] == obj_suffix:
                objects.append( source )
            else:
                target = None
                target = os.path.splitext( os.path.split( str(source) )[1] )[0]
                if not source.path.startswith( env['build_root'] ):
                    if os.path.isabs( str(source) ):
                        target = env.File( os.path.join( obj_prefix + target + obj_suffix ) )
                    else:
                        target = env.File( os.path.join( env['build_dir'], obj_prefix + target + obj_suffix ) )
                else:
                    offset_dir = os.path.relpath( os.path.split( source.path )[0], env['build_dir'] )
                    target = env.File( os.path.join( offset_dir, obj_prefix + target + obj_suffix ) )

                logger.trace( "Object target = [{}]/[{}]".format( as_notice(str(target)), as_notice(target.path) ) )

                objects.append(
                    obj_builder(
                        target = target,
                        source = source,
                        CPPPATH = env['SYSINCPATH'] + env['INCPATH'],
                        **kwargs ) )

        cuppa.progress.NotifyProgress.add( env, objects )

        return objects


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Compile", cls( False ) )
        cuppa_env.add_method( "CompileStatic", cls( False ) )
        cuppa_env.add_method( "CompileShared", cls( True ) )

