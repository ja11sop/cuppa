
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildMethod
#-------------------------------------------------------------------------------

import cuppa.sconscript_progress
import os.path


class BuildMethod:

    @classmethod
    def build( cls, env, target, source, final_dir = None, append_variant = False ):
        if final_dir == None:
            final_dir = env['final_dir']
        exe = os.path.join( final_dir, target )
        if append_variant and env['variant'] != 'rel':
            exe += '_' + env['variant']
        env.AppendUnique( DYNAMICLIBS = env['LIBS'] )

        program = env.Program( exe,
                               source,
                               CPPPATH = env['SYSINCPATH'] + env['INCPATH'],
                               LIBS = env['DYNAMICLIBS'] + env['STATICLIBS'] )

        cuppa.sconscript_progress.SconscriptProgress.add( env, program )

        return program


    def __call__( self, env, target, source, final_dir = None, append_variant = False ):
        return self.build( env, target, source, final_dir=final_dir, append_variant=append_variant )


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "Build" )


