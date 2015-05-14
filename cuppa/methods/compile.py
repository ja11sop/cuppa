
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CompileMethod
#-------------------------------------------------------------------------------

import cuppa.progress
import os

from SCons.Script import Flatten

class CompileMethod:

    def __call__( self, env, source, **kwargs ):
        sources = Flatten( [ source ] )
        objects = []
        for source in sources:
            objects.append(
                env.Object(
                    os.path.join( env['build_dir'], os.path.splitext( source )[0] ),
                    source,
                    CPPPATH = env['SYSINCPATH'] + env['INCPATH'],
                    **kwargs ) )

        cuppa.progress.NotifyProgress.add( env, objects )

        return objects

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "Compile" )
