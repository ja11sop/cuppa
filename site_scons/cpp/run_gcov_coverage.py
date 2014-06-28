
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunGcovCoverage
#-------------------------------------------------------------------------------
from subprocess     import call
from os.path        import split
from sys            import stderr
from SCons.Script   import Glob


class RunGcovCoverageEmitter:

    def __init__( self, final_dir ):
        self.__final_dir = final_dir


    def __call__( self, target, source, env ):
#        program_file = self.__final_dir + split( source[0].path )[1]
#        target.append( test_log_from_program( program_file ) )
        return target, source


#def builder_for_coverage( target, source, env ):
#    import subprocess
#    import os
#    for s in source:
#        full_path = str(s)
#        output_path, source_file = os.path.split( full_path )
#        summary_file = open( full_path + '.summary.gcov', 'w' )
#        if not subprocess.call( ['gcov', '-o', output_path, '-l', '-p', '-c', full_path], stdout=summary_file):
#            gcov_files = Glob( '*.gcov' )
#            for gcov_file in gcov_files:
#                gcov_file_name = str( gcov_file )
#                os.rename( gcov_file_name, output_path + '/' + gcov_file_name )
#            open( full_path + '.coverage', 'w' ).write( "COVERAGE\n" )
#    return 0


class RunGcovCoverage:

    def __call__( self, target, source, env ):
        for s in source:
            full_path = str(s)
            output_path, source_file = os.path.split( full_path )
            summary_file = open( full_path + '.summary.gcov', 'w' )
            if not subprocess.call( ['gcov', '-o', output_path, '-l', '-p', '-c', full_path], stdout=summary_file):
                gcov_files = Glob( '*.gcov' )
                for gcov_file in gcov_files:
                    gcov_file_name = str( gcov_file )
                    os.rename( gcov_file_name, output_path + '/' + gcov_file_name )
    #            open( full_path + '.coverage', 'w' ).write( "COVERAGE\n" )

        return None



