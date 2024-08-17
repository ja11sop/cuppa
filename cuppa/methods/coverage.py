
#          Copyright Jamie Allsop 2011-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CoverageMethod
#-------------------------------------------------------------------------------

import re
import os.path

from SCons.Script import Flatten

import cuppa.progress


class CoverageMethod(object):

    def __init__( self ):
        pass


    def __call__( self, env, program, sources, final_dir=None, include_patterns=None, exclude_dependencies=False, exclude_patterns=None ):

        if 'cov' not in env['variant_actions'].keys() and 'test' not in env['variant_actions'].keys():
            return []

        if final_dir == None:
            final_dir = env['abs_final_dir']

        if include_patterns:
            include_patterns = Flatten( [ include_patterns ] )

        exclude_dependency_pattern = None
        if exclude_dependencies:
            exclude_dependency_pattern = re.escape( env['download_root'] ).replace( r"\_", r"_" ).replace( r"\#", r"#" )
            if os.path.isabs( env['download_root'] ):
                exclude_dependency_pattern = exclude_dependency_pattern + "#.*"
            else:
                exclude_dependency_pattern = ".*##" + exclude_dependency_pattern + "#.*"

        if exclude_patterns and exclude_dependency_pattern:
            exclude_patterns = Flatten( [ exclude_dependency_pattern, exclude_patterns ] )
        elif exclude_dependency_pattern:
            exclude_patterns = [ exclude_dependency_pattern ]

        emitter, builder = env['toolchain'].coverage_runner( program, final_dir, include_patterns=include_patterns, exclude_patterns=exclude_patterns )

        if not emitter and not builder:
            return None

        env['BUILDERS']['CoverageBuilder'] = env.Builder( action=builder, emitter=emitter )

        coverage = env.CoverageBuilder( [], Flatten( [ sources ] ) )

        cuppa.progress.NotifyProgress.add( env, coverage )
        return coverage

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Coverage", cls() )



class CollateCoverageFilesMethod(object):

    def __init__( self ):
        pass

    def __call__( self, env, sources, destination=None ):

        if 'cov' not in env['variant_actions'].keys() and 'test' not in env['variant_actions'].keys():
            return []

        emitter, builder = env['toolchain'].coverage_collate_files( destination )

        if not emitter and not builder:
            return None

        env['BUILDERS']['CollateCoverageFilesBuilder'] = env.Builder( action=builder, emitter=emitter )

        summary_files = env.CollateCoverageFilesBuilder( [], Flatten( [ sources ] ) )

        cuppa.progress.NotifyProgress.add( env, summary_files )
        return summary_files


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CollateCoverageFiles", cls() )



class CollateCoverageIndexMethod(object):

    def __init__( self ):
        pass

    def __call__( self, env, sources, destination=None ):
        if 'cov' not in env['variant_actions'].keys() and 'test' not in env['variant_actions'].keys():
            return []

        emitter, builder = env['toolchain'].coverage_collate_index( destination )

        if not emitter and not builder:
            return None

        env['BUILDERS']['CollateCoverageIndexBuilder'] = env.Builder( action=builder, emitter=emitter )

        index_file = env.CollateCoverageIndexBuilder( [], Flatten( [ sources ] ) )

        cuppa.progress.NotifyProgress.add( env, index_file )
        return index_file


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CollateCoverageIndex", cls() )



