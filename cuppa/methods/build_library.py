
#          Copyright Jamie Allsop 2014-2016
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildLibMethods
#-------------------------------------------------------------------------------

import cuppa.progress
import os.path


class BuildStaticLibMethod:

    def __call__( self, env, target, source, final_dir=None, **kwargs ):
        if final_dir == None:
            final_dir = env['abs_final_dir']
        lib = env.StaticLibrary( os.path.join( final_dir, target ), env.Compile(source), **kwargs )

        cuppa.progress.NotifyProgress.add( env, lib )

        return lib

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "BuildStaticLib", cls() )


class BuildSharedLibMethod:

    def __call__( self, env, target, source, final_dir=None, **kwargs ):
        if final_dir == None:
            final_dir = env['abs_final_dir']
        lib = env.SharedLibrary( os.path.join( final_dir, target ), env.Compile(source), **kwargs )

        cuppa.progress.NotifyProgress.add( env, lib )

        return lib

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "BuildSharedLib", cls() )
