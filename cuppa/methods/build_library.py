
#          Copyright Jamie Allsop 2014-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildLibMethods
#-------------------------------------------------------------------------------

import os.path


class BuildStaticLibMethod:

    def __call__( self, env, target, source, final_dir=None, **kwargs ):
        if final_dir == None:
            final_dir = env['abs_final_dir']
        lib = os.path.join( final_dir, target )
        return env.StaticLibrary( lib, source, **kwargs )

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "BuildStaticLib" )


class BuildSharedLibMethod:

    def __call__( self, env, target, source, final_dir=None, **kwargs ):
        if final_dir == None:
            final_dir = env['abs_final_dir']
        lib = os.path.join( final_dir, target )

        return env.SharedLibrary( lib, source, **kwargs )

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "BuildSharedLib" )
