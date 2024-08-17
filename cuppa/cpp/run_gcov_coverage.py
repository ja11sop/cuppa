
#          Copyright Jamie Allsop 2011-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunGcovCoverage
#-------------------------------------------------------------------------------

# python standard library imports
from subprocess import Popen, PIPE
import os
import shlex
import re
import itertools
import glob
import sys
import six

from jinja2 import Environment, PackageLoader, select_autoescape

from SCons.Script import Glob, Flatten, Dir

# construct imports
from cuppa.output_processor import IncrementalSubProcess, command_available
from cuppa.colourise import as_notice, as_info, as_error, colour_items
from cuppa.log import logger
from cuppa.progress import NotifyProgress
from cuppa.utility.python2to3 import as_str
import cuppa.recursive_glob
import cuppa.path

from cuppa.utility.python2to3 import Pattern

url_block_sep = '--'
coverage_id = 'coverage'
index_id = 'index'
coverage_marker = coverage_id + url_block_sep
coverage_index_marker = coverage_id + '-' + index_id + url_block_sep


def gcov_offset_path( file_path, env ):
    path, filename = os.path.split( file_path )
    offset_path = os.path.relpath( path, env['build_dir'] )
    offset_path = offset_path.strip('.')
    if offset_path.startswith( os.path.sep ):
        offset_path = offset_path[1:]
    offset_path = offset_path and offset_path.replace( os.path.sep, '#' ) + '#' or ""
    return offset_path + filename + '##'


#def coverage_output( source, env ):
#    build_dir  = env['build_dir'].replace( os.path.sep, '#' )
#    offset_dir = env['offset_dir'].replace( os.path.sep, '#' )


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
    process_output = WriteToString()
    return_code = IncrementalSubProcess.Popen( process_output,
                                               shlex.split( command ),
                                               cwd=working_dir,
                                               scons_env=env )
    return return_code, process_output.string()


class CoverageSuite(object):

    @classmethod
    def create( cls, program_id, name, scons_env, final_dir, include_patterns=[], exclude_patterns=[] ):
        return CoverageSuite( program_id, name, scons_env, final_dir, include_patterns=include_patterns, exclude_patterns=exclude_patterns )


    @classmethod
    def regexes_from_patterns( cls, patterns ):
        regexes = []
        patterns = Flatten( [ patterns ] )
        for pattern in patterns:
            if isinstance( pattern, Pattern ):
                regexes.append( pattern._pattern )
            elif pattern:
                regexes.append( pattern )
        return regexes


    @classmethod
    def get_gcovr_version( cls ):
        command = "gcovr --version"
        if command_available( command ):
            reported_version = None
            version_string = as_str( Popen( shlex.split( command ), stdout=PIPE).communicate()[0] )
            matches = re.search( r'gcovr (?P<major>\d+)\.(?P<minor>\d)', version_string )
            if matches:
                major = matches.group('major')
                minor = matches.group('minor')
                reported_version = {}
                reported_version['major'] = int(major)
                reported_version['minor'] = int(minor)
                reported_version['version'] = major + "." + minor
            return reported_version
        return None


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

        cuppa.path.lazy_create_path( output_dir )

        gcovr_version = self.get_gcovr_version()
        if not gcovr_version:
            logger.warning( "Skipping gcovr output as not available" )
            return

        html_base_name = url_coverage_base_name( sconscript_id ) + "." + self._program_id[2:]

        index_file = html_base_name + ".html"
        regex_filter = re.escape( os.path.join( build_dir, "" ) ).replace( r"\_", r"_" ).replace( r"\#", r"#" )
        regex_filter = r".*" + regex_filter + r".*" + self._program_id + r"\.gcov"

        gcov_includes = ""
        for include_regex in include_regexes:
            gcov_includes += ' --gcov-filter="{}"'.format( include_regex )

        if not gcov_includes:
            gcov_includes = ' --gcov-filter="{}"'.format( regex_filter )

        gcov_excludes = ""
        for exclude_regex in exclude_regexes:
            gcov_excludes += ' --gcov-exclude="{}"'.format( exclude_regex )

        command = 'gcovr -g {gcov_includes} {gcov_excludes} -s -k -r . --html --html-details {self_contained_html} {html_theme} -o {index_file}'.format(
            gcov_includes = gcov_includes,
            gcov_excludes = gcov_excludes,
            self_contained_html = gcovr_version['major'] >= 5 and "--html-self-contained" or "",
            html_theme = gcovr_version['major'] >= 5 and "--html-theme blue" or "",
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

        sys.stdout.write( output + "\n" )


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

        logger.trace( "target = {}".format( colour_items( [str(t) for t in target] ) ) )
        logger.trace( "source = {}".format( colour_items( [str(s) for s in source] ) ) )

        cuppa.path.lazy_create_path( os.path.join( env['base_path'], env['build_dir'] ) )

        self._target = target

        # Each source will result in one or more targets so we need to slice the targets to pick up
        # the gcov target (the first one) before we perform the zip iteration
        for s, t in zip( source, itertools.islice( target, 0, None, len(target)//len(source) ) ):

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
            sys.stdout.write( output + "\n" )
            os.remove( gcov_log_path )


def destination_subdir( env ):
    return env['flat_tool_variant_dir_offset']


def get_toolchain_variant_dir( env ):
    return env['tool_variant_dir']


def get_offset_dir( env ):
    return os.path.normpath( env['offset_dir'] )


class CollateCoverageFilesEmitter(object):

    report_regex = re.compile(
        coverage_marker + r"[#%@$~\w&_:+/\.-]+[.]html$"
    )

    def __init__( self, destination=None ):
        self._destination = destination

    def __call__( self, target, source, env ):

        if not self._destination:
            self._destination = env['abs_final_dir']
        else:
            self._destination = self._destination + destination_subdir( env )

        report_node = next( ( s for s in source if re.match( self.report_regex, os.path.split(str(s))[1] ) ), None )
        filter_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_filter" ), None )

        logger.trace( "Report node = [{}]".format( as_notice( str(report_node) ) ) )
        logger.trace( "Filter node = [{}]".format( as_notice( str(filter_node) ) ) )

        if report_node and filter_node:
            output_summary = os.path.splitext(str(filter_node))[0] + ".cov_files"
            target.append( output_summary )

            env.Clean( source, os.path.join( self._destination, os.path.split(str(report_node))[1] ) )

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
        self.report_regex = CollateCoverageFilesEmitter.report_regex


    def __call__( self, target, source, env ):

        if not self._destination:
            self._destination = env['abs_final_dir']
        else:
            self._destination = self._destination + destination_subdir( env )

        report_node = next( ( s for s in source if re.match( self.report_regex, os.path.split(str(s))[1] ) ), None )
        filter_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_filter" ), None )

        if report_node and filter_node:

            env.CopyFiles( self._destination, report_node )

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


def sconscript_name( env ):
    sconscript_file = os.path.splitext( os.path.split( env['sconscript_file'] )[1] )[0]
    return sconscript_file.lower() == "sconscript" and "" or sconscript_file.lower()


def coverage_index_name_from( env ):
    index_base_name = destination_subdir( env )
    if index_base_name.startswith("./"):
        index_base_name = index_base_name[2:]
    index_base_name = index_base_name.rstrip('/')
    index_base_name = index_base_name.replace('/', '.')
    name = sconscript_name( env )
    if name:
        return coverage_index_marker + index_base_name + "." + name + ".html"
    else:
        return coverage_index_marker + index_base_name + ".html"


class CollateCoverageIndexEmitter(object):

    def __init__( self, destination=None ):
        self._destination = destination

    def __call__( self, target, source, env ):
        destination = self._destination
        if not destination:
            destination = env['abs_final_dir']
            env.Clean( source, os.path.join( self._destination, "coverage-index.html" ) )
        else:
            env.Clean( source, os.path.join( self._destination, "coverage-index.html" ) )
            destination = self._destination + destination_subdir( env )

        files_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_files" ), None )
        if files_node:
            variant_index_file = os.path.join( env['abs_final_dir'], coverage_index_name_from( env ) )
            target.append( variant_index_file )
            env.Clean( source, os.path.join( destination, os.path.split( variant_index_file )[1] ) )

            variant_summary_file = os.path.splitext( variant_index_file )[0] + ".log"
            target.append( variant_summary_file )

            CoverageIndexBuilder.register_coverage_folders( final_dir=env['abs_final_dir'], destination_dir=self._destination )

        logger.trace( "sources = [{}]".format( colour_items( [str(s) for s in source] ) ) )
        logger.trace( "targets = [{}]".format( colour_items( [str(t) for t in target] ) ) )

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
        r"(?P<coverage_file>coverage[-#][#%@$~\w&_ :+/\.-]+)"
        r"\nlines: (?P<lines_percent>[\d.]+)% [(](?P<lines_covered>\d+)[\D]+(?P<lines_total>\d+)[)]"
        r"(\nfunctions: (?P<functions_percent>[\d.]+)% [(](?P<functions_covered>\d+)[\D]+(?P<functions_total>\d+)[)])?"
        r"\nbranches: (?P<branches_percent>[\d.]+)% [(](?P<branches_covered>\d+)[\D]+(?P<branches_total>\d+)[)]"
        r"(\ntoolchain_variant_dir: (?P<toolchain_variant_dir>[#%@$~\w&_ +/\.-]+))?"
        r"(\noffset_dir: (?P<offset_dir>[#%@$~\w&_ +/\.-]+))?"
        r"(\nsubdir: (?P<subdir>[#%@$~\w&_ +/\.-]+))?"
        r"(\nname: (?P<name>[#%@$~\w&_ +/\.-]+))?",
         re.MULTILINE
    )

    @classmethod
    def get_progress_lines_status( cls, percent ):
        percent = float(percent)
        if percent < 75.0:
            return "bg-danger"
        elif percent < 90.0:
            return "bg-warning"
        return "bg-success"

    @classmethod
    def get_lines_status( cls, percent ):
        percent = float(percent)
        if percent < 75.0:
            return "alert-danger"
        elif percent < 90.0:
            return "alert-warning"
        return "alert-success"

    @classmethod
    def get_progress_branches_status( cls, percent ):
        percent = float(percent)
        if percent < 40.0:
            return "bg-danger"
        elif percent < 50.0:
            return "bg-warning"
        return "bg-success"

    @classmethod
    def get_branches_status( cls, percent ):
        percent = float(percent)
        if percent < 40.0:
            return "alert-danger"
        elif percent < 50.0:
            return "alert-warning"
        return "alert-success"


    @classmethod
    def create_from_string( cls, string, destination=None ):
        return cls( entry_string = string, destination=destination )


    @classmethod
    def name_from_file( cls, filename ):
        name = os.path.splitext( filename )[0]
        if name.startswith( coverage_marker ):
            name = name.replace( coverage_marker, "" )
        return name


    def summary_name( cls, filename, toolchain_variant_dir, offset_dir, sconscript_name ):
        name = os.path.splitext( filename )[0]
        if name.startswith( coverage_index_marker ):
            name = name.replace( coverage_index_marker, "" )

        logger.trace( "filename = [{}], toolchain_variant_dir = [{}], offset_dir = [{}], sconscript_name = [{}]".format(
            as_info(filename),
            as_notice(toolchain_variant_dir),
            as_info(offset_dir),
            as_info(sconscript_name),
        ) )

        return "./{}/{}".format( offset_dir, sconscript_name and sconscript_name or "*" )


    def __init__( self, coverage_file=None, entry_string=None, destination=None ):

        self.coverage_file = coverage_file and coverage_file or ""
        self.coverage_name = coverage_file and self.name_from_file( coverage_file ) or ""
        self.coverage_context = ""
        self.subdir = ""
        self.name = ""
        self.toolchain_variant_dir = ""
        self.offset_dir = ""
        self.lines_percent = "0.0"
        self.lines_covered = 0
        self.lines_total   = 0
        self.branches_percent = "0.0"
        self.branches_covered = 0
        self.branches_total   = 0
        self.progress_lines_status = ""
        self.lines_status = ""
        self.entries = []

        if entry_string:
            matches = re.match( self.entry_regex, entry_string )
            if matches:
                self.coverage_file = matches.group( 'coverage_file' )
                self.coverage_name = self.coverage_file and self.name_from_file( self.coverage_file ) or ""
                self.subdir = matches.group( 'subdir' ) and matches.group( 'subdir' ) or ""
                self.name = matches.group( 'name' ) and matches.group( 'name' ) or ""
                self.toolchain_variant_dir = matches.group( 'toolchain_variant_dir' ) and matches.group( 'toolchain_variant_dir' ) or ""
                self.offset_dir = matches.group( 'offset_dir' ) and matches.group( 'offset_dir' ) or ""
                self.lines_percent = "{:.1f}".format( float( matches.group( 'lines_percent' ) ) )
                self.lines_covered = int( matches.group( 'lines_covered' ) )
                self.lines_total = int( matches.group( 'lines_total' ) )
                self.branches_percent = "{:.1f}".format( float( matches.group( 'branches_percent' ) ) )
                self.branches_covered = int( matches.group( 'branches_covered' ) )
                self.branches_total = int( matches.group( 'branches_total' ) )
                self.progress_lines_status = self.get_progress_lines_status( self.lines_percent )
                self.lines_status = self.get_lines_status( self.lines_percent )
                self.progress_branches_status = self.get_progress_branches_status( self.branches_percent )
                self.branches_status = self.get_branches_status( self.branches_percent )

        if self.subdir:
            self.coverage_file = os.path.join( self.subdir, self.coverage_file )
            self.coverage_name = os.path.join( self.subdir, self.coverage_name )

        if self.toolchain_variant_dir and self.offset_dir:
            self.coverage_name = self.summary_name( self.coverage_file, self.toolchain_variant_dir, self.offset_dir, self.name )
            self.coverage_context = self.toolchain_variant_dir

        self.destination_file = destination and os.path.join( destination, os.path.split(self.coverage_file)[1] ) or ""


    def append( self, entry ):
        self.entries.append( entry )
        self.lines_covered += entry.lines_covered
        self.lines_total += entry.lines_total
        if self.lines_total:
            self.lines_percent = "{:.1f}".format( 100.0 * float(self.lines_covered) / float(self.lines_total) )
        self.branches_covered += entry.branches_covered
        self.branches_total += entry.branches_total
        if self.branches_total:
            self.branches_percent = "{:.1f}".format( 100.0 * float(self.branches_covered) / float(self.branches_total) )
        self.progress_lines_status = self.get_progress_lines_status( self.lines_percent )
        self.lines_status = self.get_lines_status( self.lines_percent )
        self.progress_branches_status = self.get_progress_branches_status( self.branches_percent )
        self.branches_status = self.get_branches_status( self.branches_percent )


    @classmethod
    def create_from_summary( cls, summary, tool_variant_dir, offset_dir, destination, subdir=None, name=None ):
        entry_string = "{}\n{}\n{}{}{}".format(
            summary.strip(),
            tool_variant_dir.strip(),
            offset_dir.strip(),
            subdir and "\n" + subdir.strip() or "",
            name and "\n" + name.strip() or "",
        )
        logger.info( "coverage entry from\n{}\nin {}".format( as_info( entry_string ), as_notice( destination ) ) )
        return coverage_entry.create_from_string( entry_string, destination )


def lines_of_code_format( number ):
    number = float('{:.5g}'.format(number))
    base = 0
    while abs(number) >= 1000:
        base += 1
        number /= 1000.0
    return '{}{}'.format( '{:f}'.format(number).rstrip('0').rstrip('.'), ['', 'k', 'M', 'B', 'T'][base] )


class CollateCoverageIndexAction(object):

    def __init__( self, destination=None ):
        self._destination = destination


    def __call__( self, target, source, env ):

        logger.trace( "target = [{}]".format( colour_items( [ str(node) for node in target ] ) ) )
        logger.trace( "source = [{}]".format( colour_items( [ str(node) for node in source ] ) ) )

        files_node = next( ( s for s in source if os.path.splitext(str(s))[1] == ".cov_files" ), None )
        if files_node:

            if not self._destination:
                self._destination = env['abs_final_dir']
            else:
                self._destination = self._destination + destination_subdir( env )

            variant_index_path = os.path.join( env['abs_final_dir'], coverage_index_name_from( env ) )
            variant_summary_path = os.path.splitext( variant_index_path )[0] + ".log"
            summary_files = env.Glob( os.path.join( env['abs_final_dir'], "coverage--*.log" ) )

            logger.trace( "summary_files = [{}]".format( colour_items( [ str(node) for node in summary_files ] ) ) )

            with open( variant_index_path, 'w' ) as variant_index_file:

                coverage = coverage_entry( coverage_file=self.summary_name(env) )
                coverage.coverage_context = get_toolchain_variant_dir( env )

                for path in summary_files:
                    with open( str(path), 'r' ) as summary_file:

                        contents = summary_file.read()

                        coverage.append(
                            coverage_entry.create_from_summary(
                                contents,
                                get_toolchain_variant_dir( env ),
                                get_offset_dir( env ),
                                self._destination
                        ) )

                template = CoverageIndexBuilder.get_template()

                variant_index_file.write(
                    template.render(
                        coverage_summary = coverage,
                        coverage_entries = sorted( coverage.entries, key=lambda entry: entry.coverage_name ),
                        LOC = lines_of_code_format,
                    )
                )

                #coverage--value.html
                #lines: 100.0% (99 out of 99)
                #branches: 50.0% (301 out of 602)

                with open( variant_summary_path, 'w' ) as variant_summary_file:
                    variant_summary_file.write(
                        "{filename}\n"
                        "lines: {lines_percent}% ({lines_covered} out of {lines_total})\n"
                        "branches: {branches_percent}% ({branches_covered} out of {branches_total})\n"
                        "toolchain_variant_dir: {toolchain_variant_dir}\n"
                        "offset_dir: {offset_dir}\n"
                        "subdir: {subdir}\n"
                        "name: {name}\n"
                        .format(
                            filename = os.path.split( variant_index_path )[1],
                            lines_percent     = coverage.lines_percent,
                            lines_covered     = coverage.lines_covered,
                            lines_total       = coverage.lines_total,
                            branches_percent  = coverage.branches_percent,
                            branches_covered  = coverage.branches_covered,
                            branches_total    = coverage.branches_total,
                            toolchain_variant_dir = get_toolchain_variant_dir( env ),
                            offset_dir            = get_offset_dir( env ),
                            subdir                = destination_subdir( env ),
                            name                  = sconscript_name( env ),
                    ) )

                CoverageIndexBuilder.update_coverage( coverage )

            logger.trace( "self._destination = [{}], variant_index_path = [{}]".format( as_info( str(self._destination) ), as_notice( str(variant_index_path) ) ) )

            env.CopyFiles( self._destination, variant_index_path )

        return None

    @classmethod
    def summary_name( cls, env ):
        return os.path.split( env['sconscript_toolchain_build_dir'] )[0] + "/*"


class CoverageIndexBuilder(object):

    all_lines_covered = 0
    all_lines_total   = 0
    all_coverage      = []
    destination_dirs  = {}

    @classmethod
    def register_coverage_folders( cls, final_dir=None, destination_dir=None ):

        destination_dir = str(Dir(destination_dir))
        final_dir = str(Dir(final_dir))

        if not destination_dir in cls.destination_dirs:
            cls.destination_dirs[destination_dir] = set()
            cls.destination_dirs[destination_dir].add( final_dir )
        else:
            new_common = None
            new_folder = None
            for path in cls.destination_dirs[destination_dir]:
                common, tail1, tail2 = cuppa.path.split_common( path, final_dir )
                if common and (not tail1 or not tail2):
                    new_common = common
                    new_folder = final_dir
                    break
                else:
                    new_folder = final_dir
            if new_common:
                cls.destination_dirs[destination_dir].add(new_common)
                cls.destination_dirs[destination_dir].remove(new_folder)
            elif new_folder:
                cls.destination_dirs[destination_dir].add(new_folder)


    @classmethod
    def get_template( cls ):
        return jinja2_templates().get_template('coverage_index.html')


    @classmethod
    def update_coverage( cls, coverage ):
        cls.all_lines_covered += coverage.lines_covered
        cls.all_lines_total += coverage.lines_total
        cls.all_coverage.append( coverage )


    @classmethod
    def on_progress( cls, progress, sconscript, variant, env, target, source ):
        if progress == 'sconstruct_end':

            logger.debug( "COVERAGE = {:d}/{:d}\n".format( cls.all_lines_covered, cls.all_lines_total ) )

            if not cls.all_lines_total > 0:
                return
            lines_percent = 100.0 * float(cls.all_lines_covered) / float(cls.all_lines_total)
            sys.stdout.write( "COVERAGE = {:.1f}% : {:d}/{:d}\n".format( lines_percent, cls.all_lines_covered, cls.all_lines_total ) )

            for destination_dir, final_dirs in six.iteritems(cls.destination_dirs):

                coverage = coverage_entry( coverage_file=os.path.split( env['sconstruct_dir'] )[1] )

                for folder in final_dirs:
                    logger.debug( "Create coverage index file for [{}]".format( as_notice( folder ) ) )
                    index_files = cuppa.recursive_glob.glob( folder, coverage_index_marker + "*.html" )

                    for index_file in index_files:
                        logger.debug( "Read coverage index file for [{}]".format( as_notice( str(index_file) ) ) )
                        summary_path = os.path.splitext( str(index_file) )[0] + ".log"
                        logger.debug( "Read coverage summary file for [{}]".format( as_notice( str(summary_path) ) ) )

                        with open( str(summary_path), 'r' ) as summary_file:
                            summary = summary_file.read()
                            coverage.append(
                                coverage_entry( entry_string=summary, destination=destination_dir )
                            )

                master_index_path = os.path.join( destination_dir, "coverage-index.html" )

                logger.debug( "Master coverage index path = [{}]".format( as_notice( master_index_path ) ) )

                template = cls.get_template()

                with open( master_index_path, 'w' ) as master_index_file:

                    master_index_file.write(
                        template.render(
                            coverage_summary = coverage,
                            coverage_entries = sorted( coverage.entries, key=lambda entry: entry.coverage_name ),
                            LOC = lines_of_code_format,
                        )
                    )


NotifyProgress.register_callback( None, CoverageIndexBuilder.on_progress )
