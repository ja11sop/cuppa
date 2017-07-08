
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
from cuppa.log import logger
from cuppa.colourise import as_notice, colour_items



class RecursiveGlobMethod:

    default = ()

    def __call__( self, env, pattern, start=default, exclude_dirs=default ):

        base_path = os.path.realpath( env['sconscript_dir'] )

        if start == self.default:
            start = base_path

        start = os.path.expanduser( start )

        rel_start = os.path.relpath( base_path, start )

        logger.trace(
            "paths: start = [{}], base_path = [{}], rel_start = [{}]"
            .format( as_notice( start ), as_notice( base_path ), as_notice( rel_start ) )
        )

        if not os.path.isabs( start ):
            start = rel_start

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

        logger.trace(
            "matches = [{}]."
            .format( colour_items( [ str(match) for match in matches ] ) )
        )

        make_relative = True
        if rel_start.startswith( os.pardir ):
            make_relative = False

        logger.trace( "make_relative = [{}].".format( as_notice( str(make_relative) ) ) )

        nodes = [ env.File( make_relative and os.path.relpath( match, base_path ) or match ) for match in matches ]

        logger.trace(
            "nodes = [{}]."
            .format( colour_items( [ str(node) for node in nodes ] ) )
        )

        return nodes

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "RecursiveGlob", cls() )



class GlobFilesMethod:

    def __call__( self, env, pattern ):
        filenames = []
        for filename in os.listdir(env['sconscript_dir']):
            if fnmatch.fnmatch( filename, pattern):
                filenames.append( filename )
        nodes = [ env.File(f) for f in filenames ]
        return nodes


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "GlobFiles", cls() )



