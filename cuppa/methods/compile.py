
#          Copyright Jamie Allsop 2013-2016
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

    def __call__( self, env, source, **kwargs ):
        sources = Flatten( [ source ] )
        objects = []
        if 'CPPPATH' in env:
            env.AppendUnique( INCPATH = env['CPPPATH'] )

        obj_suffix = env.subst('$OBJSUFFIX')
        for source in sources:
            if os.path.splitext(str(source))[1] == obj_suffix:
                objects.append( source )
            else:
                target = None
                if not str(source).startswith( env['build_root'] ):
                    target = os.path.splitext( os.path.split( str(source) )[1] )[0]
                    target = os.path.join( env['build_dir'], env.subst('$OBJPREFIX') + target + env.subst('$OBJSUFFIX') )

                objects.append(
                    env.Object(
                        source = source,
                        target = target,
                        CPPPATH = env['SYSINCPATH'] + env['INCPATH'],
                        **kwargs ) )

        cuppa.progress.NotifyProgress.add( env, objects )

        return objects

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Compile", cls() )
