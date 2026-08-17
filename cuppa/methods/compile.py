
#          Copyright Jamie Allsop 2013-2026
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
from cuppa.utility.object_target import object_target_for


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

        if env.get( 'modules' ):
            from cuppa.cpp.cxx_modules import compile_with_modules
            return compile_with_modules(
                env,
                sources,
                obj_builder,
                obj_prefix,
                obj_suffix,
                dependencies,
                { k: v for k, v in kwargs.items() if k != 'depends_on' },
            )

        for source in sources:
            if not isinstance( source, Node ):
                source = env.File( source )

            if dependencies:
                env.Depends( source, Flatten( [ dependencies ] ) )

            logger.trace( "Object source = [{}]/[{}]".format( as_notice(str(source)), as_notice(source.path) ) )

            if os.path.splitext(str(source))[1] == obj_suffix:
                objects.append( source )
            else:
                target = object_target_for( env, source, obj_prefix, obj_suffix )

                logger.trace( "Object target = [{}]/[{}]".format( as_notice(str(target)), as_notice(target.path) ) )

                build_kwargs = dict( kwargs )
                if env.get( '_cuppa_profiles_enforce_header' ):
                    from cuppa.cpp.cxx_profiles import apply_profiles_enforce_compile
                    source, cxx_flags = apply_profiles_enforce_compile(
                        env,
                        source,
                        list( build_kwargs.get( 'CXXFLAGS', env.get( 'CXXFLAGS', [] ) ) ),
                    )
                    build_kwargs['CXXFLAGS'] = cxx_flags

                objects.append(
                    obj_builder(
                        target = target,
                        source = source,
                        CPPPATH = env['SYSINCPATH'] + env['INCPATH'],
                        **build_kwargs ) )

        cuppa.progress.NotifyProgress.add( env, objects )

        return objects


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Compile", cls( False ) )
        cuppa_env.add_method( "CompileStatic", cls( False ) )
        cuppa_env.add_method( "CompileShared", cls( True ) )

