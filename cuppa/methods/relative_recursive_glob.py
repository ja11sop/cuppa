
#          Copyright Jamie Allsop 2012-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RelativeRecursiveGlob
#-------------------------------------------------------------------------------
import os
import fnmatch

import cuppa.recursive_glob


class GlobFromSconscriptMethod:

    def __call__( self, env, start, pattern ):

        if start and start != '.':
            start = os.path.join( env['sconscript_dir'], start )
        else:
            start = env['sconscript_dir']

        return cuppa.recursive_glob.glob( start, pattern )


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "GlobFromSconscript" )



class GlobFromBaseMethod:

    def __call__( self, env, start, pattern ):

        if start and start != '.':
            start = os.path.join( env['base_path'], start )
        else:
            start = env['base_path']

        return cuppa.recursive_glob.glob( start, pattern )


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "GlobFromBase" )



class RecursiveGlobMethod:

    def __call__( self, env, start, pattern ):
        return cuppa.recursive_glob.glob( start, pattern )


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "RecursiveGlob" )



class GlobFilesMethod:

    def __call__( self, env, pattern ):
        filenames = []
        for filename in os.listdir(env['sconscript_dir']):
            if fnmatch.fnmatch( filename, pattern):
                filenames.append( filename )
        return filenames


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "GlobFiles" )



