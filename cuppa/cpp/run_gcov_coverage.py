
#          Copyright Jamie Allsop 2011-2019
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

from jinja2 import Environment, PackageLoader, select_autoescape

from SCons.Script import Glob, Flatten

# construct imports
from cuppa.output_processor import IncrementalSubProcess, command_available
from cuppa.colourise import as_notice, as_info, as_warning, as_error
from cuppa.log import logger
from cuppa.progress import NotifyProgress


url_block_sep = '--'


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



def run_command( command, working_dir, env ):
    print command
    process_output = WriteToString()
    return_code = IncrementalSubProcess.Popen( process_output,
                                               shlex.split( command ),
                                               cwd=working_dir,
                                               scons_env=env )
    return return_code, process_output.string()


def lazy_create_path( path ):
    if not os.path.exists( path ):
        try:
            os.makedirs( path )
        except os.error as e:
            if not os.path.exists( path ):
                logger.error( "Could not create path [{}]. Failed with error [{}]".format( as_notice(path), as_error(str(e)) ) )


class CoverageSuite(object):

    @classmethod
    def create( cls, program_id, name, scons_env, final_dir, include_patterns=[], exclude_patterns=[] ):
        return CoverageSuite( program_id, name, scons_env, final_dir, include_patterns=include_patterns, exclude_patterns=exclude_patterns )


    @classmethod
    def regexes_from_patterns( cls, patterns ):
        regexes = []
        patterns = Flatten( [ patterns ] )
        for pattern in patterns:
            if isinstance( pattern, re._pattern_type ):
                regexes.append( pattern._pattern )
            elif pattern:
                regexes.append( pattern )
        return regexes


    def __init__( self, program_id, name, scons_env, final_dir, include_patterns=[], exclude_patterns=[] ):
        self._program_id = program_id
        self._url_program_id = self._program_id.replace( '##', url_block_sep )
        self._name = name
        self._scons_env = scons_env
        self._final_dir = final_dir
        self._index_file = os.path.join( self._final_dir, self._url_program_id + "index.html" )

        self._include_regexes = self.regexes_from_patterns( include_patterns )
        self._exclude_regexes = self.regexes_from_patterns( exclude_patterns )


    def run_suite( self, target ):
        env = self._scons_env
        self._run_gcovr( target, env['build_dir'], self._final_dir, env['working_dir'], env['sconscript_toolchain_build_dir'], self._include_regexes, self._exclude_regexes )


    def _run_gcovr( self, target, build_dir, output_dir, working_dir, sconscript_id, include_regexes, exclude_regexes ):

        lazy_create_path( output_dir )

        command = 'gcovr -h'
        if not command_available( command ):
            logger.warning( "Skipping gcovr output as not available" )
            return

        html_base_name = url_coverage_base_name( sconscript_id ) + "." + self._program_id[2:]

        index_file = html_base_name + ".html"
        regex_filter = re.escape( os.path.join( build_dir, "" ) ).replace( "\_", "_" ).replace( "\#", "#" )
        regex_filter = ".*" + regex_filter + ".*" + self._program_id + "\.gcov"

        gcov_includes = ""
        for include_regex in include_regexes:
            gcov_includes += ' --gcov-filter="{}"'.format( include_regex )

        if not gcov_includes:
            gcov_includes = ' --gcov-filter="{}"'.format( regex_filter )

        gcov_excludes = ""
        for exclude_regex in exclude_regexes:
            gcov_excludes += ' --gcov-exclude="{}"'.format( exclude_regex )

        command = 'gcovr -g {gcov_includes} {gcov_excludes} -s -k -r . --html --html-details -o {index_file}'.format(
            regex_filter=regex_filter,
            gcov_includes = gcov_includes,
            gcov_excludes = gcov_excludes,
            index_file=index_file )

        return_code, output = run_command( command, working_dir, self._scons_env )

        coverage_index_basename = "coverage" + self._url_program_id + ".html"
        new_index_file = os.path.join( output_dir, coverage_index_basename )
        try:
            os.rename( index_file, new_index_file )
        except OSError as e:
            logger.error( "Failed moving coverage file from [{}] to [{}] with error: {}".format(
                        as_notice( index_file ),
                        as_notice( new_index_file ),
                        as_error( str(e) )
            ) )

        coverage_summary_path = os.path.splitext( new_index_file )[0] + ".log"
        with open( coverage_summary_path, 'w' ) as coverage_summary_file:
            coverage_summary_file.write( coverage_index_basename + "\n" + output  )

        logger.trace( "gcovr HTML file filter = [{}]".format( as_notice(html_base_name) ) )
        coverage_files = Glob( html_base_name + '*.html' )

        for coverage_file in coverage_files:
            new_coverage_file = os.path.join( output_dir, str( coverage_file ) )
            target.append( new_coverage_file )
            try:
                os.rename( str( coverage_file ), new_coverage_file )
            except OSError as e:
                logger.error( "Failed moving coverage file from [{}] to [{}] with error: {}".format(
                        as_notice( str( coverage_file ) ),
                        as_notice( new_coverage_file ),
                        as_error( str(e) )
                ) )

        coverage_filter_path = os.path.join( output_dir, "coverage" + self._url_program_id + ".cov_filter" )
        with open( coverage_filter_path, 'w' ) as coverage_filter_file:
            coverage_filter_file.write( html_base_name + '*.html' )

        print output


def gcov_program_id( program ):
    return '##' + os.path.split(str(program[0]))[1]


class RunGcovCoverageEmitter(object):

    def __init__( self, program, final_dir, coverage_tool ):
        self._program = program
        self._final_dir = final_dir
        self._coverage_tool = coverage_tool
        self._program_id = gcov_program_id( program )
        self._url_program_id = self._program_id.replace( '##', url_block_sep )


    def __call__( self, target, source, env ):

        for s in source:
            source_file = os.path.relpath( s.path, env['build_dir'] )

            logger.trace( "Determine coverage files for source file [{}]".format( as_notice(source_file) ) )

            gcno_file = os.path.splitext( source_file )[0] + '.gcno'
            gcda_file = os.path.splitext( source_file )[0] + '.gcda'
            logger.trace( "gcov data paths = [{}] and [{}]".format( as_notice(gcno_file), as_notice(gcda_file) ) )
            env.Clean( source_file, [gcno_file, gcda_file] )

            gcov_log = source_file + self._program_id + '_gcov.log'
            logger.trace( "Adding target gcov_log = [{}]".format( as_notice(gcov_log) ) )
            target.append( gcov_log )

            gcov_base_name = gcov_offset_path( s.path, env )
            gcov_file_filter = gcov_base_name + '*' + self._program_id[2:] + ".gcov"

            logger.trace( "gcov file filter = [{}]".format( as_notice(gcov_file_filter) ) )

            gcov_files = Glob( gcov_file_filter )
            env.Clean( source_file, gcov_files )

            coverage_index_file = os.path.join( self._final_dir, "coverage" + self._url_program_id + ".html" )
            logger.trace( "Adding target gcovr index file =[{}]".format( as_notice(coverage_index_file) ) )
            target.append( coverage_index_file )

            coverage_summary_file = os.path.join( self._final_dir, "coverage" + self._url_program_id + ".log" )
            logger.trace( "Adding target gcovr summary file =[{}]".format( as_notice(coverage_summary_file) ) )
            target.append( coverage_summary_file )

            coverage_filter_file = os.path.join( self._final_dir, "coverage" + self._url_program_id + ".cov_filter" )
            logger.trace( "Adding target gcovr filter file =[{}]".format( as_notice(coverage_filter_file) ) )
            target.append( coverage_filter_file )

            coverage_filter = os.path.join( self._final_dir, url_coverage_base_name( env['sconscript_toolchain_build_dir'] ) + "." + self._program_id[2:] + '*.html' )

            logger.trace( "coverage filter = [{}]".format( as_notice(coverage_filter) ) )

            coverage_files = Glob( coverage_filter )
            env.Clean( source_file, coverage_files )

        return target, source


    def html_filter( self, env, coverage_targets ):
        source = os.path.splitext( os.path.split( str(coverage_targets[1]) )[1] )[0].replace( 'coverage' + url_block_sep, '' )
        return os.path.join( self._final_dir, url_coverage_base_name( env['sconscript_toolchain_build_dir'] ) + "." + source + '*.html' )


def iter_grouped( items, step=2, fillvalue=None ):
    it = iter( items )
    return itertools.izip_longest( *[it]*step, fillvalue=fillvalue )


class RunGcovCoverage(object):

    def __init__( self, program, final_dir, coverage_tool, include_patterns=[], exclude_patterns=[] ):
        self._program = program
        self._final_dir = final_dir
        self._coverage_tool = coverage_tool
        self._program_id = gcov_program_id( program )
        self._include_patterns = include_patterns
        self._exclude_patterns = exclude_patterns
        self._target = None


    def __call__( self, target, source, env ):
        lazy_create_path( os.path.join( env['base_path'], env['build_dir'] ) )

        self._target = target

        for s, t in itertools.izip( source, target ):

            gcov_path = os.path.splitext( os.path.splitext( t.path )[0] )[0]
            gcov_log = t.path
            logger.trace( "gcov_path = [{}]".format( as_notice( str(gcov_path) ) ) )
            self._run_gcov( env, s.path, gcov_path, gcov_log )

        target = self._target

        return None

    # Example gcov commands
    # gcov-8 -o _build/include/xstd/property_tree/properties_parser/gcc82/cov/x86_64/c++2a/working/properties_parser_test -l -p -r -c -b include/xstd/property_tree/properties_parser_test.cpp
    # gcov-8 -o _build/include/xstd/application/main_test/gcc82/cov/x86_64/c++2a/working/main_test -l -p -r -c -b _build/include/xstd/application/main_test/gcc82/cov/x86_64/c++2a/working/main_test.o

    def _run_gcov( self, env, source_path, gcov_path, gcov_log_path ):
        working_dir       = env['working_dir']
        build_dir         = env['build_dir']
        final_dir         = self._final_dir

        qualified_base = source_path.startswith( env['build_dir'] ) and env['build_dir'] or env['offset_dir']
        if qualified_base.startswith( "./" ):
            qualified_base = qualified_base[2:]
        qualified_base = qualified_base.replace( os.path.sep, '#' )

        logger.trace( "Qualified base = [{}]".format( as_notice(str(qualified_base)) ) )

        if not os.path.isabs( self._final_dir ):
            final_dir = os.path.normpath( os.path.join( build_dir, self._final_dir ) )

        suite_name = working_dir + self._program_id
        coverage_suite = CoverageSuite.create( self._program_id, suite_name, env, final_dir, include_patterns=self._include_patterns, exclude_patterns=self._exclude_patterns )

        relative_only = "-r"
        if self._coverage_tool.startswith( "llvm-cov" ):
            relative_only = ""

        command = '{gcov} -o {path} -l -p {relative} -c -b {source}'.format( gcov=self._coverage_tool, path=gcov_path, relative=relative_only, source=source_path )

        return_code, output = run_command( command, working_dir, env )

        if return_code == 0:
            gcov_source_path = source_path.replace( os.path.sep, '#' )
            gcov_files = glob.glob( gcov_source_path + '*gcov' )

            for gcov_file in gcov_files:

                filename, ext = os.path.splitext( str(gcov_file) )
                filename = filename + self._program_id + ext
                new_filename = filename[len(qualified_base)+1:]

                logger.trace( "Move GCOV [{}] to [{}]...".format( as_notice(str(gcov_file)), as_notice(new_filename) ) )

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

                coverage_suite.run_suite( self._target )
        else:
            print output
            os.remove( gcov_log_path )



class CollateCoverageFilesEmitter(object):

    def __init__( self, destination=None ):
        self._destination = destination


    def __call__( self, target, source, env ):

        if not self._destination:
            self._destination = env['abs_final_dir']

        filter_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_filter" ), None )

        if filter_node:
            output_summary = os.path.splitext(str(filter_node))[0] + ".cov_files"
            target.append( output_summary )

            logger.trace( "Filter node = [{}]".format( as_notice( str(filter_node) ) ) )

            clean_pattern = None
            if filter_node:
                if os.path.exists( str(filter_node) ):
                    with open( str(filter_node), 'r' ) as filter_file:
                        clean_pattern = filter_file.readline().strip()
                        clean_pattern = os.path.join( self._destination, clean_pattern )
                        if clean_pattern.startswith('#'):
                            clean_pattern = os.path.join( env['sconstruct_dir'], clean_pattern[1:] )
                        logger.trace( "Clean pattern = [{}]".format( as_notice(clean_pattern) ) )

            if clean_pattern:
                env.Clean( source, Glob( clean_pattern ) )

        return target, source


class CollateCoverageFilesAction(object):

    def __init__( self, destination=None ):
        self._destination = destination


    def __call__( self, target, source, env ):

        if not self._destination:
            self._destination = env['abs_final_dir']

        filter_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_filter" ), None )

        if filter_node:

            final_dir = os.path.split( str(filter_node) )[0]
            filter_pattern = None

            if os.path.exists( str(filter_node) ):
                with open( str(filter_node), 'r' ) as filter_file:
                    filter_pattern = filter_file.readline().strip()

            output_files = []

            if filter_pattern:
                output_files = env.Glob( os.path.join( final_dir, filter_pattern ) )
                env.CopyFiles( self._destination, output_files )

                with open( str(target[0]), 'w' ) as summary_file:
                    for f in output_files:
                        summary_file.write( str(f) )
        return None



class CollateCoverageIndexEmitter(object):

    def __init__( self, destination=None ):
        self._destination = destination
        if not self._destination:
            self._destination = env['abs_final_dir']

    def __call__( self, target, source, env ):

        files_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_files" ), None )
        if files_node:
            variant_index_file = os.path.join( env['abs_final_dir'], "coverage_index.html" )
            target.append( variant_index_file )
            env.Clean( source, os.path.join( self._destination, os.path.split( variant_index_file )[1] ) )

        return target, source


jinja2_env = None

def jinja2_templates():
    global jinja2_env
    if jinja2_env:
        return jinja2_env
    else:
        jinja2_env = Environment(
            loader=PackageLoader( 'cuppa', 'cpp/templates' ),
            autoescape=select_autoescape(['html', 'xml'])
        )
        return jinja2_env


class coverage_entry(object):

    entry_regex = re.compile(
        r"(?P<coverage_file>coverage[-#][-#][#%@$~\w&_:+/\.-]+)"
         " lines: (?P<lines_percent>[\d.]+)% [(](?P<lines_covered>\d+)[\D]+(?P<lines_total>\d+)[)]"
         " branches: (?P<branches_percent>[\d.]+)% [(](?P<branches_covered>\d+)[\D]+(?P<branches_total>\d+)[)]"
    )

    @classmethod
    def get_progress_lines_status( cls, percent ):
        if percent < 75.0:
            return "bg-danger"
        elif percent < 90.0:
            return "bg-warning"
        return "bg-success"

    @classmethod
    def get_lines_status( cls, percent ):
        if percent < 75.0:
            return "alert-danger"
        elif percent < 90.0:
            return "alert-warning"
        return "alert-success"

    @classmethod
    def get_progress_branches_status( cls, percent ):
        if percent < 40.0:
            return "bg-danger"
        elif percent < 50.0:
            return "bg-warning"
        return "bg-success"

    @classmethod
    def get_branches_status( cls, percent ):
        if percent < 40.0:
            return "alert-danger"
        elif percent < 50.0:
            return "alert-warning"
        return "alert-success"


    def __init__( self, coverage_file=None, entry_string=None ):

        self.coverage_file = coverage_file and coverage_file or ""
        self.lines_percent = 0.0
        self.lines_covered = 0
        self.lines_total   = 0
        self.branches_percent = 0.0
        self.branches_covered = 0
        self.branches_total   = 0
        self.progress_lines_status = ""
        self.lines_status = ""
        self.entries = []

        if entry_string:
            matches = re.match( self.entry_regex, entry_string )
            if matches:
                self.coverage_file = matches.group( 'coverage_file' )
                self.lines_percent = float( matches.group( 'lines_percent' ) )
                self.lines_covered = int( matches.group( 'lines_covered' ) )
                self.lines_total = int( matches.group( 'lines_total' ) )
                self.branches_percent = float( matches.group( 'branches_percent' ) )
                self.branches_covered = int( matches.group( 'branches_covered' ) )
                self.branches_total = int( matches.group( 'branches_total' ) )
                self.progress_lines_status = self.get_progress_lines_status( self.lines_percent )
                self.lines_status = self.get_lines_status( self.lines_percent )
                self.progress_branches_status = self.get_progress_branches_status( self.branches_percent )
                self.branches_status = self.get_branches_status( self.branches_percent )


    def append( self, entry ):
        self.entries.append( entry )
        self.lines_covered += entry.lines_covered
        self.lines_total += entry.lines_total
        self.lines_percent = 100.0 * float(self.lines_covered) / float(self.lines_total)
        self.branches_covered += entry.branches_covered
        self.branches_total += entry.branches_total
        self.branches_percent = 100.0 * float(self.branches_covered) / float(self.branches_total)
        self.progress_lines_status = self.get_progress_lines_status( self.lines_percent )
        self.lines_status = self.get_lines_status( self.lines_percent )
        self.progress_branches_status = self.get_progress_branches_status( self.branches_percent )
        self.branches_status = self.get_branches_status( self.branches_percent )


def shorthand_number_format( number ):
    number = float('{:.5g}'.format(number))
    magnitude = 0
    while abs(number) >= 1000:
        magnitude += 1
        number /= 1000.0
    return '{}{}'.format( '{:f}'.format(number).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude] )


class CollateCoverageIndexAction(object):

    all_lines_covered = 0
    all_lines_total   = 0


    @classmethod
    def update_coverage( cls, covered, total ):
        cls.all_lines_covered += covered
        cls.all_lines_total += total


    def __init__( self, destination=None ):
        self._destination = destination


    def __call__( self, target, source, env ):

        files_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_files" ), None )
        if files_node:

            if not self._destination:
                self._destination = env['abs_final_dir']

            variant_index_path = os.path.join( env['abs_final_dir'], "coverage_index.html" )
            summary_files = env.Glob( os.path.join( env['abs_final_dir'], "coverage--*.log" ) )

            with open( variant_index_path, 'w' ) as variant_index_file:

                template = self.get_template()

                coverage = coverage_entry( coverage_file=self.summary_name(env) )

                for path in summary_files:
                    with open( str(path), 'r' ) as summary_file:
                        index_file = summary_file.readline()
                        lines_summary = summary_file.readline()
                        branches_summary = summary_file.readline()

                        coverage.append( self.get_entry( index_file, lines_summary, branches_summary ) )

                variant_index_file.write(
                    template.render(
                        coverage_summary = coverage,
                        coverage_entries = coverage.entries,
                        hrf = shorthand_number_format,
                    )
                )

                self.update_coverage( coverage.lines_covered, coverage.lines_total )

            env.CopyFiles( self._destination, variant_index_path )

        return None


    @classmethod
    def on_progress( cls, progress, sconscript, variant, env, target, source ):
        if progress == 'sconstruct_end' and cls.all_lines_total > 0:
            lines_percent = 100.0 * float(cls.all_lines_covered) / float(cls.all_lines_total)
            print "COVERAGE = {:.2f}% : {:d}/{:d}".format( lines_percent, cls.all_lines_covered, cls.all_lines_total )


    @classmethod
    def summary_name( cls, env ):
        return os.path.split( env['sconscript_toolchain_build_dir'] )[0] + "/*"


    def get_template( self ):
        return jinja2_templates().get_template('coverage_index.html')


    def get_entry( self, index_file, lines_summary, branches_summary ):
        return coverage_entry( entry_string="{} {} {}".format( index_file.strip(), lines_summary.strip(), branches_summary.strip() ) )


NotifyProgress.register_callback( None, CollateCoverageIndexAction.on_progress )
