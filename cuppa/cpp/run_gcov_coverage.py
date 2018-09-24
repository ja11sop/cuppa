
#          Copyright Jamie Allsop 2011-2018
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
from cuppa.colourise import as_notice, as_info, as_warning, as_error
from cuppa.log import logger


def gcov_offset_path( file_path, env ):
    path, filename = os.path.split( file_path )
    offset_path = os.path.relpath( path, env['build_dir'] )
    offset_path = offset_path.strip('.')
    if offset_path.startswith( os.path.sep ):
        offset_path = offset_path[1:]
    offset_path = offset_path and offset_path.replace( os.path.sep, '#' ) + '#' or ""
    return offset_path + filename + '##'


def coverage_output( source, env ):

    build_dir  = env['build_dir'].replace( os.path.sep, '#' )
    offset_dir = env['offset_dir'].replace( os.path.sep, '#' )


def url_coverage_base_name( sconscript_file ):
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
    print command
    process_output = WriteToString()
    return_code = IncrementalSubProcess.Popen( process_output,
                                               shlex.split( command ),
                                               cwd=working_dir )
    return return_code, process_output.string()



class CoverageSuite(object):

    suites = {}

    @classmethod
    def create( cls, program_id, name, scons_env, final_dir ):
        if not name in cls.suites:
            cls.suites[name] = CoverageSuite( program_id, name, scons_env, final_dir )
        return cls.suites[name]


    def __init__( self, program_id, name, scons_env, final_dir ):
        self._program_id = program_id
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
            logger.warning( "Skipping gcovr output as not available" )
            return

        html_base_name = url_coverage_base_name( sconscript_id )

        index_file = html_base_name + ".html"
        regex_filter = re.escape( os.path.join( build_dir, "" ) ).replace( "\_", "_" ).replace( "\#", "#" )
        regex_filter = ".*" + regex_filter + ".*" + self._program_id + "\.gcov"

        command = 'gcovr -g --gcov-filter="{}" -k -r . --html --html-details -o {}'.format( regex_filter, index_file )

        return_code, output = run_command( command, working_dir )

        new_index_file = os.path.join( output_dir, "coverage" + self._program_id + ".html" )
        try:
            os.rename( index_file, new_index_file )
        except OSError as e:
            logger.error( "Failed moving coverage file from [{}] to [{}] with error: {}".format(
                        as_notice( index_file ),
                        as_notice( new_index_file ),
                        as_error( str(e) )
            ) )

        logger.trace( "gcovr HTML file filter = [{}]".format( as_notice(html_base_name) ) )
        coverage_files = Glob( html_base_name + '*.html' )

        for coverage_file in coverage_files:
            new_coverage_file = os.path.join( output_dir, str( coverage_file ) )
            try:
                os.rename( str( coverage_file ), new_coverage_file )
            except OSError as e:
                logger.error( "Failed moving coverage file from [{}] to [{}] with error: {}".format(
                        as_notice( str( coverage_file ) ),
                        as_notice( new_coverage_file ),
                        as_error( str(e) )
                ) )
        print output


def gcov_program_id( program ):
    return '##' + os.path.split(str(program[0]))[1]


class RunGcovCoverageEmitter(object):

    def __init__( self, program, final_dir, coverage_tool ):
        self._program = program
        self._final_dir = final_dir
        self._coverage_tool = coverage_tool
        self._program_id = gcov_program_id( program )


    def __call__( self, target, source, env ):

        for s in source:
            source_file = os.path.relpath( s.path, env['build_dir'] )

            gcno_file = os.path.splitext( source_file )[0] + '.gcno'
            gcda_file = os.path.splitext( source_file )[0] + '.gcda'

            logger.trace( "gcov data paths = [{}] and [{}]".format( as_notice(gcno_file), as_notice(gcda_file) ) )

            gcov_log = source_file + self._program_id + '_gcov.log'

            env.Clean( source_file, [gcno_file, gcda_file] )

            target.append( gcov_log )

            gcov_base_name = gcov_offset_path( s.path, env )
            gcov_file_filter = gcov_base_name + '*' + self._program_id[2:] + ".gcov"

            logger.trace( "gcov file filter = [{}]".format( as_notice(gcov_file_filter) ) )

            gcov_files = Glob( gcov_file_filter )
            env.Clean( source_file, gcov_files )

            env.Clean( source_file, os.path.join( self._final_dir, "coverage" + self._program_id + ".html" ) )

            coverage_filter = os.path.join( self._final_dir, url_coverage_base_name( env['sconscript_toolchain_build_dir'] ) + '*.html' )

            logger.trace( "coverage filter = [{}]".format( as_notice(coverage_filter) ) )

            coverage_files = Glob( coverage_filter )
            env.Clean( source_file, coverage_files )

        return target, source


def iter_grouped( items, step=2, fillvalue=None ):
    it = iter( items )
    return itertools.izip_longest( *[it]*step, fillvalue=fillvalue )


class RunGcovCoverage(object):

    def __init__( self, program, final_dir, coverage_tool ):
        self._program = program
        self._final_dir = final_dir
        self._coverage_tool = coverage_tool
        self._program_id = gcov_program_id( program )


    def __call__( self, target, source, env ):

        for s, t in itertools.izip( source, target ):

            gcov_path = os.path.splitext( os.path.splitext( t.path )[0] )[0]
            gcov_log = t.path
            logger.trace( "gcov_path = [{}]".format( as_notice( str(gcov_path) ) ) )
            self._run_gcov( env, s.path, gcov_path, gcov_log )

        return None


    def _run_gcov( self, env, source_path, gcov_path, gcov_log_path ):
        working_dir       = env['working_dir']
        build_dir         = env['build_dir']
        final_dir         = self._final_dir
        qualified_base    = env['build_dir'].replace( os.path.sep, '#' )

        if not os.path.isabs( self._final_dir ):
            final_dir = os.path.normpath( os.path.join( build_dir, self._final_dir ) )

        suite_name = working_dir + self._program_id
        coverage_suite = CoverageSuite.create( self._program_id, suite_name, env, final_dir )

        relative_only = "-r"
        if self._coverage_tool.startswith( "llvm-cov" ):
            relative_only = ""

        command = '{gcov} -o {path} -l -p {relative} -c -b {source}'.format( gcov=self._coverage_tool, path=gcov_path, relative=relative_only, source=source_path )

        return_code, output = run_command( command, working_dir )

        if return_code == 0:
            gcov_source_path = source_path.replace( os.path.sep, '#' )
            gcov_files = glob.glob( gcov_source_path + '*gcov' )

            for gcov_file in gcov_files:

                filename, ext = os.path.splitext( str(gcov_file) )
                filename = filename + self._program_id + ext
                new_filename = filename[ len(qualified_base)+1:]

                new_gcov_file = os.path.join( build_dir, new_filename )
                try:
                    os.rename( str(gcov_file), new_gcov_file )
                except OSError as e:
                    logger.error( "Failed moving gcov file [{}] to [{}] with error: {}".format(
                            as_notice( str(gcov_file) ),
                            as_notice( new_gcov_file ),
                            as_error( str(e) )
                    ) )

            with open( gcov_log_path, 'w' ) as summary_file:
                summary_file.write( output )
        else:
            print output
            os.remove( gcov_log_path )

