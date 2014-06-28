
#          Copyright Jamie Allsop 2012-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RelativeRecursiveGlob
#-------------------------------------------------------------------------------
import recursive_glob

import os
import fnmatch


class GlobFromSconscriptMethod:

    def __call__( self, env, start, pattern ):

        if start and start != '.':
            start = os.path.join( env['sconscript_dir'], start )
        else:
            start = env['sconscript_dir']

        return recursive_glob.glob( start, pattern )


    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls(), "GlobFromSconscript" )



class GlobFromBaseMethod:

    def __call__( self, env, start, pattern ):

        if start and start != '.':
            start = os.path.join( env['base_path'], start )
        else:
            start = env['base_path']

        return recursive_glob.glob( start, pattern )


    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls(), "GlobFromBase" )



class RecursiveGlobMethod:

    def __call__( self, env, start, pattern ):
        return recursive_glob.glob( start, pattern )


    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls(), "RecursiveGlob" )



class GlobFilesMethod:

    def __call__( self, env, pattern ):
        filenames = []
        for filename in os.listdir(env['sconscript_dir']):
            if fnmatch.fnmatch( filename, pattern):
                filenames.append( filename )
        return filenames


    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls(), "GlobFiles" )



