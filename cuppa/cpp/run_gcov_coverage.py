
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunGcovCoverage
#-------------------------------------------------------------------------------

# python standard library imports
import os
import shlex
import re
import itertools
import glob

from SCons.Script import Glob

# construct imports
import cuppa.progress
from cuppa.output_processor import IncrementalSubProcess, command_available



def offset_path( path, env ):

    build_dir  = env['build_dir']
    offset_dir = env['offset_dir']
    path = offset_dir + os.path.sep + os.path.relpath( path, build_dir )

    if path.startswith( "." + os.path.sep ):
        path = path[2:]
    return path



def coverage_base_name( sconscript_file ):
    if sconscript_file.startswith( "." + os.path.sep ):
        sconscript_file = sconscript_file[2:]

    sconscript_file = sconscript_file.replace( ".", '' )
    sconscript_file = sconscript_file.replace( "sconscript", '' )
    sconscript_file = sconscript_file.replace( os.path.sep, '.' )

    return sconscript_file + ".coverage"



class WriteToString(object):

    def __init__( self ):
        self._output = []

    def __call__( self, line ):
        self._output.append( line )

    def string( self ):
        return "\n".join( self._output )



def run_command( command, working_dir ):
    print "cuppa: gcov: executing [{}]".format( command )
    process_output = WriteToString()
    return_code = IncrementalSubProcess.Popen( process_output,
                                               shlex.split( command ),
                                               cwd=working_dir )
    return return_code, process_output.string()



class CoverageSuite(object):

    suites = {}

    @classmethod
    def create( cls, name, scons_env, final_dir ):
        if not name in cls.suites:
            cls.suites[name] = CoverageSuite( name, scons_env, final_dir )
        return cls.suites[name]


    def __init__( self, name, scons_env, final_dir ):
        self._name = name
        self._scons_env = scons_env
        self._final_dir = final_dir
        cuppa.progress.NotifyProgress.register_callback( scons_env, self.on_progress )
        self._suite = {}


    def on_progress( self, progress, sconscript, variant, env, target, source ):
        if progress == 'finished':
            self.exit_suite()
            del self.suites[self._name]


    def exit_suite( self ):
        env = self._scons_env
        self._run_gcovr( env['build_dir'], self._final_dir, env['working_dir'], env['sconscript_toolchain_build_dir'] )


    def _run_gcovr( self, build_dir, output_dir, working_dir, sconscript_id ):
        command = 'gcovr -h'
        if not command_available( command ):
            print "cuppa: gcov: Skipping gcovr output as not available"
            return

        base_name = coverage_base_name( sconscript_id )

        index_file = base_name + ".html"

        regex_filter = re.escape( os.path.join( build_dir, "" ) )
        regex_filter = ".*" + regex_filter + ".*\.gcov"

        command = 'gcovr -g --gcov-filter="{}" -k -r . --html --html-details -o {}'.format( regex_filter, index_file )

        return_code, output = run_command( command, working_dir )

        new_index_file = os.path.join( output_dir, "coverage.html" )
        try:
            os.rename( index_file, new_index_file )
        except OSError as e:
            print "cuppa: gcov: Failed moving coverage file from [{}] to [{}] with error: {}".format(
                        index_file,
                        new_index_file,
                        str(e)
                )

        coverage_files = Glob( base_name + '*.html' )
        for coverage_file in coverage_files:
            new_coverage_file = os.path.join( output_dir, str( coverage_file ) )
            try:
                os.rename( str( coverage_file ), new_coverage_file )
            except OSError as e:
                print "cuppa: gcov: Failed moving coverage file from [{}] to [{}] with error: {}".format(
                        str( coverage_file ),
                        new_coverage_file,
                        str(e)
                )
        print output


class RunGcovCoverageEmitter(object):

    def __init__( self, program, final_dir ):
        self._program = program
        self._final_dir = final_dir
        self._program_id = '##' + os.path.split(str(program[0]))[1]


    def __call__( self, target, source, env ):

        for s in source:
            source_file = os.path.relpath(  s.path, env['build_dir'] )

            offset_source = offset_path( s.path, env )

            gcov_source_path = offset_source.replace( os.path.sep, '#' )

            gcno_file = os.path.splitext( source_file )[0] + '.gcno'
            gcda_file = os.path.splitext( source_file )[0] + '.gcda'

            gcov_log = source_file + self._program_id + '_gcov.log'

            env.Clean( source_file, [gcno_file, gcda_file] )

            target.append( gcov_log )

            gcov_files = Glob( gcov_source_path + '*' )
            env.Clean( source_file, gcov_files )

            env.Clean( source_file, os.path.join( self._final_dir, "coverage.html" ) )
            base_name = coverage_base_name( env['sconscript_toolchain_build_dir'] )

            coverage_files = Glob( os.path.join( self._final_dir, base_name + '*.html' ) )
            env.Clean( source_file, coverage_files )

        return target, source


def iter_grouped( items, step=2, fillvalue=None ):
    it = iter( items )
    return itertools.izip_longest( *[it]*step, fillvalue=fillvalue )


class RunGcovCoverage(object):

    def __init__( self, program, final_dir ):
        self._program = program
        self._final_dir = final_dir
        self._program_id = '##' + os.path.split(str(program[0]))[1]


    def __call__( self, target, source, env ):

        for s, t in itertools.izip( source, target ):

            gcov_path = os.path.splitext( os.path.splitext( t.path )[0] )[0]
            gcov_log = t.path
            self._run_gcov( env, s.path, gcov_path, gcov_log )

        return None


    def _run_gcov( self, env, source_path, gcov_path, gcov_log_path ):
        working_dir       = env['working_dir']
        build_dir         = env['build_dir']
        final_dir         = self._final_dir
        if not os.path.isabs( self._final_dir ):
            final_dir = os.path.normpath( os.path.join( build_dir, self._final_dir ) )

        suite_name = working_dir
        coverage_suite = CoverageSuite.create( suite_name, env, final_dir )

        command = 'gcov -o {} -l -p -r -c -b {}'.format( gcov_path, source_path )

        return_code, output = run_command( command, working_dir )

        if return_code == 0:
            gcov_source_path = source_path.replace( os.path.sep, '#' )
            gcov_files = glob.glob( gcov_source_path + '*gcov' )

            for gcov_file in gcov_files:

                filename, ext = os.path.splitext( str(gcov_file) )
                filename = filename + self._program_id + ext

                new_gcov_file = os.path.join( build_dir, filename )
                try:
                    os.rename( str(gcov_file), new_gcov_file )
                except OSError as e:
                    print "cuppa: gcov: Failed moving gcov file [{}] to [{}] with error: {}".format(
                            str(gcov_file),
                            new_gcov_file,
                            str(e)
                    )

            with open( gcov_log_path, 'w' ) as summary_file:
                summary_file.write( output )
        else:
            print output
            os.remove( gcov_log_path )

