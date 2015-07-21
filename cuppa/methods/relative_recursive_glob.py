
#          Copyright Jamie Allsop 2012-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RelativeRecursiveGlob
#-------------------------------------------------------------------------------
import os
import fnmatch
import re

import cuppa.recursive_glob



class RecursiveGlobMethod:

    default = ()

    def __call__( self, env, pattern, start=default, exclude_dirs=default ):

        if start == self.default:
            start = env['sconscript_dir']

        start = os.path.expanduser( start )

        if not os.path.isabs( start ):
            start = os.path.join( env['sconscript_dir'], start )

        if exclude_dirs == self.default:
            exclude_dirs = [ env['download_root'], env['build_root' ] ]

        exclude_dirs_regex = None

        if exclude_dirs:
            def up_dir( path ):
                element = next( e for e in path.split(os.path.sep) if e )
                return element == ".."
            exclude_dirs = [ re.escape(d) for d in exclude_dirs if not os.path.isabs(d) and not up_dir(d) ]
            exclude_dirs = "|".join( exclude_dirs )
            exclude_dirs_regex = re.compile( exclude_dirs )

        matches = cuppa.recursive_glob.glob( start, pattern, exclude_dirs_pattern=exclude_dirs_regex )
        nodes   = [ env.File( os.path.relpath( match, env['sconscript_dir'] ) ) for match in matches ]
        return nodes

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "RecursiveGlob" )



class GlobFilesMethod:

    def __call__( self, env, pattern ):
        filenames = []
        for filename in os.listdir(env['sconscript_dir']):
            if fnmatch.fnmatch( filename, pattern):
                filenames.append( filename )
        nodes = [ env.File(f) for f in filenames ]
        return nodes


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "GlobFiles" )



