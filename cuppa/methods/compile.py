
#          Copyright Jamie Allsop 2013-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CompileMethod
#-------------------------------------------------------------------------------

import os.path
import cuppa.progress
from SCons.Script import Flatten


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

        for source in sources:
            if os.path.splitext(str(source))[1] == obj_suffix:
                objects.append( source )
            else:
                target = None
                if not str(source).startswith( env['build_root'] ):
                    target = os.path.splitext( os.path.split( str(source) )[1] )[0]
                    target = os.path.join( env['build_dir'], obj_prefix + target + obj_suffix )

                objects.append(
                    obj_builder(
                        source = source,
                        target = target,
                        CPPPATH = env['SYSINCPATH'] + env['INCPATH'],
                        **kwargs ) )

        cuppa.progress.NotifyProgress.add( env, objects )

        return objects


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Compile", cls( False ) )
        cuppa_env.add_method( "CompileStatic", cls( False ) )
        cuppa_env.add_method( "CompileShared", cls( True ) )

