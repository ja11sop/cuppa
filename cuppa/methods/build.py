
#          Copyright Jamie Allsop 2011-2016
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildMethod
#-------------------------------------------------------------------------------

import cuppa.progress
import os.path


class BuildMethod:

    @classmethod
    def build( cls, env, target, source, final_dir = None, append_variant = False, LIBS=[], SHAREDLIBS=[], DYNAMICLIBS=[], STATICLIBS=[], **kwargs ):
        if final_dir == None:
            final_dir = env['abs_final_dir']
        exe = os.path.join( final_dir, target )
        if append_variant and env['variant'] != 'rel':
            exe += '_' + env['variant']

        env.AppendUnique( DYNAMICLIBS = env['LIBS'] )

        if 'SHAREDLIBS' in env:
            env.AppendUnique( DYNAMICLIBS = env['SHAREDLIBS'] )

        all_libs = env['DYNAMICLIBS'] + env['STATICLIBS'] + LIBS + DYNAMICLIBS + SHAREDLIBS + STATICLIBS

        program = env.Program( exe,
                               env.Compile( source ),
                               LIBS = all_libs,
                               DYNAMICLIBS = env['DYNAMICLIBS'] + LIBS + DYNAMICLIBS + SHAREDLIBS,
                               STATICLIBS = env['STATICLIBS'] + STATICLIBS,
                               **kwargs )

        cuppa.progress.NotifyProgress.add( env, program )

        return program


    def __call__( self, env, target, source, final_dir = None, append_variant = False, **kwargs ):
        return self.build( env, target, source, final_dir=final_dir, append_variant=append_variant, **kwargs )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Build", cls() )


