
#          Copyright Jamie Allsop 2019-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Generate Html Report
#-------------------------------------------------------------------------------

import json
import os
import itertools
import hashlib
import six

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse
from jinja2 import Environment, PackageLoader, select_autoescape

from SCons.Script import Flatten, Dir, Copy

# cuppa imports
from cuppa.colourise import as_notice, as_info, as_error, colour_items, emphasise_time_by_digit
from cuppa.log import logger
from cuppa.path import split_common
from cuppa.progress import NotifyProgress
from cuppa.timer import as_duration_string
from cuppa.utility.python2to3 import escape
from cuppa.utility.python2to3 import encode


jinja2_env = None

def jinja2_itervalues( s ):
    return six.itervalues( s )

def jinja2_templates():
    global jinja2_env
    if jinja2_env:
        return jinja2_env
    else:
        jinja2_env = Environment(
            loader=PackageLoader( 'cuppa', 'test_report/templates' ),
            autoescape=select_autoescape(['html', 'xml'])
        )
        jinja2_env.globals['itervalues'] = jinja2_itervalues
        return jinja2_env


cached_vcs_info = {}

def vcs_info_from_location( location, default_branch, default_revision ):
    global cached_vcs_info
    if location in cached_vcs_info:
        return cached_vcs_info[location]

    from cuppa.location import Location

    vcs_info = Location.detect_vcs_info( location )

    def clean_user_info( url_string ):
        if url_string:
            url = urlparse( url_string )
            if url.scheme:
                url_string = url.scheme + "://" + url.netloc.split("@")[-1] + url.path
        return url_string

    branch = vcs_info[2]
    if not branch and default_branch:
        branch = default_branch

    revision = vcs_info[4]
    if not revision and default_revision:
        revision = default_revision

    vcs_info = ( clean_user_info( vcs_info[0] ), clean_user_info( vcs_info[1] ), branch, vcs_info[3], revision )

    cached_vcs_info[location] = vcs_info
    return vcs_info


def initialise_test_linking( env, link_style=None ):
    base_uri = ""
    if link_style == "local":
        # TODO: escape properly and make sure this works on Windows
        base_uri = "file://" + env['sconstruct_dir']
    else:
        url, repository, branch, remote, revision = vcs_info_from_location( env['sconstruct_dir'], env['current_branch'], env['current_revision'] )

        if link_style == "gitlab" and url and branch:
            # NOTE: Might need to do VCS detection per test file
            base_uri = os.path.join( os.path.splitext(url)[0], "blob", branch )
        elif link_style == "raw":
            base_uri = url, repository, branch, remote, revision
        elif url:
            base_uri = url
    return base_uri


class GenerateHtmlReportBuilder(object):

    def __init__( self, final_dir, sort_test_cases=False, auto_link_tests=True, link_style="local" ):
        self._final_dir = final_dir
        self._sort_test_cases = sort_test_cases
        self._auto_link_tests = auto_link_tests
        self._link_style = link_style


    @classmethod
    def _summary_path( cls, base_node ):
        return os.path.splitext( str(base_node) )[0] + "-summary.json"


    def emitter( self, target, source, env ):
        sources = []
        targets = []
        try:
            for s in source:
                if os.path.splitext( str(s) )[1] == ".json":
                    sources.append( s )
                    target_report = os.path.splitext( str(s) )[0] + ".html"
                    targets.append( target_report )
                    targets.append( self._summary_path(target_report) )
        except StopIteration:
            pass
        return targets, sources


    def GenerateHtmlTestReport( self, target, source, env ):

        self._base_uri = ""
        if self._auto_link_tests:
            self._base_uri = initialise_test_linking( env, link_style=self._link_style )

        # Each source will result in one or more targets so we need to slice the targets to pick up
        # the gcov target (the first one) before we perform the zip iteration
        for s, t in zip( source, itertools.islice( target, 0, None, len(target)//len(source) ) ):
            test_suites = {}

            logger.trace( "source = [{}]".format( as_info(str(s)) ) )
            logger.trace( "target = [{}]".format( as_info(str(t)) ) )

            test_cases = self._read( s.abspath )
            for test_case in test_cases:

                if not 'assertions_count' in test_case:
                    if 'assertions' in test_case:
                        test_case['assertions_count']   = test_case['assertions']
                        test_case['assertions_passed']  = test_case['passed']
                        test_case['assertions_failed']  = test_case['failed']
                        test_case['assertions_aborted'] = test_case['aborted']
                    else:
                        test_case['assertions_count']   = 0
                        test_case['assertions_passed']  = 0
                        test_case['assertions_failed']  = 0
                        test_case['assertions_aborted'] = 0

                self._add_to_test_suites( test_suites, test_case )
            self._write( str(t), env, test_suites, sort_test_cases=self._sort_test_cases )
        return None


    @classmethod
    def _initialise_test_suites( cls, report ):
        report['test_suites_count'] = 0
        report['test_suites_passed'] = 0
        report['test_suites_failed'] = 0
        report['test_suites_expected_failures'] = 0
        report['test_suites_aborted'] = 0
        report['test_suites_skipped'] = 0


    @classmethod
    def _initialise_test_cases( cls, report ):
        report['tests_count'] = 0
        report['tests_passed'] = 0
        report['tests_failed'] = 0
        report['tests_expected_failures'] = 0
        report['tests_aborted'] = 0
        report['tests_skipped'] = 0


    @classmethod
    def _initialise_test_assertions( cls, report ):
        report['assertions_count'] = 0
        report['assertions_passed'] = 0
        report['assertions_failed'] = 0
        report['assertions_aborted'] = 0


    @classmethod
    def _initialise_test_times( cls, report ):
        report['cpu_times'] = {
            "process_time": 0,
            "system_time": 0,
            "user_time": 0,
            "wall_time": 0
        }
        report['wall_cpu_percent'] = 'n/a'


    @classmethod
    def _create_toolchain_variant_summary( cls, name ):
        report = {}
        report['name'] = name
        report['status'] = "passed"
        #report['test_summaries'] = []
        cls._initialise_test_suites( report )
        cls._initialise_test_cases( report )
        cls._initialise_test_assertions( report )
        cls._initialise_test_times( report )
        return report


    @classmethod
    def _create_test_summary( cls, name ):
        report = {}
        cls._initialise_test_suite( name, report )
        cls._initialise_test_suites( report )
        return report


    @classmethod
    def _initialise_test_suite( cls, name, report ):
        report['name'] = name
        report['status'] = "passed"
        report['test_cases'] = []
        cls._initialise_test_cases( report )
        cls._initialise_test_assertions( report )
        cls._initialise_test_times( report )


    @classmethod
    def _add_to_test_suites( cls, test_suites, test_case ):
        logger.trace( "test_case = [{}]".format( as_notice( str(test_case) ) ) )
        suite = test_case['suite']
        if not suite in test_suites:
            test_suites[suite] = {}
            cls._initialise_test_suite( suite, test_suites[suite] )
        test_suite = test_suites[suite]
        test_suite['test_cases'].append( test_case )
        cls._update_summary_stats( test_suite, test_case )


    @classmethod
    def _update_summary_stats( cls, summary, test_stats, source="test_case" ):

        status = test_stats['status']

        key = source == "test_case" and "tests_" or "test_suites_"

        if status == 'passed':
            summary[key + 'passed'] += 1
        elif status == 'failed':
            summary[key + 'failed'] += 1
        elif status == 'expected_failure':
            summary[key + 'expected_failures'] += 1
        elif status == 'aborted':
            summary[key + 'aborted'] += 1
        elif status == 'skipped':
            summary[key + 'skipped'] += 1

        if source == "test_case":

            summary['tests_count'] += 1

        elif source == "test_suite":

            summary['test_suites_count'] += 1

            summary['tests_count']             += test_stats['tests_count']
            summary['tests_passed']            += test_stats['tests_passed']
            summary['tests_failed']            += test_stats['tests_failed']
            summary['tests_expected_failures'] += test_stats['tests_expected_failures']
            summary['tests_aborted']           += test_stats['tests_aborted']
            summary['tests_skipped']           += test_stats['tests_skipped']

        summary['assertions_count']   += test_stats['assertions_count']
        summary['assertions_passed']  += test_stats['assertions_passed']
        summary['assertions_failed']  += test_stats['assertions_failed']
        summary['assertions_aborted'] += test_stats['assertions_aborted']

        summary['cpu_times']['process_time'] += test_stats['cpu_times']['process_time']
        summary['cpu_times']['system_time']  += test_stats['cpu_times']['system_time']
        summary['cpu_times']['user_time']    += test_stats['cpu_times']['user_time']
        summary['cpu_times']['wall_time']    += test_stats['cpu_times']['wall_time']

        if summary['cpu_times']['wall_time']:
            summary['cpu_wall_percent'] = cls._cpu_over_wall_percent(
                summary['cpu_times']['process_time'],
                summary['cpu_times']['wall_time']
            )


    @classmethod
    def _read( cls, json_report_path ):
        with open( json_report_path, "r" ) as report:
            try:
                test_cases = json.load( report )
                return test_cases
            except ValueError as error:
                logger.error(
                    "Test Report [{}] does not contain valid JSON. Error [{}] encountered while parsing".format(
                    as_info( json_report_path ),
                    as_error( str(error) )
                ) )
        return []


    @classmethod
    def get_template( cls ):
        return jinja2_templates().get_template('test_suite_index.html')


    @classmethod
    def _time_string( cls, nanoseconds ):
        time_text = as_duration_string( nanoseconds )
        return emphasise_time_by_digit(
            time_text,
            start_colour=" ",
            start_highlight='<span class="font-weight-bold">',
            end_highlight='</span>'
        )


    @classmethod
    def _cpu_over_wall_percent( cls, cpu_nanoseconds, wall_nanoseconds ):
        if wall_nanoseconds:
            return 100.0*float(cpu_nanoseconds)/float(wall_nanoseconds)
        return float('NaN')


    @classmethod
    def _percent_string( cls, percent ):
        return "{:.2f}%".format( percent )


    @classmethod
    def _selector_from_name( cls, name ):
        hasher = hashlib.md5()
        try:
            hasher.update(name)
        except:
            hasher.update(name.encode('utf-8'))

        selector = "_" + hasher.hexdigest()[-8:]
        return selector


    @classmethod
    def _status_bootstrap_style( cls, status ):
        styles = {
            "passed": "success",
            "failed": "danger",
            "aborted": "danger",
            "expected_failure": "warning",
            "skipped": "warning",
        }
        return styles[ status ]

    @classmethod
    def _status_bootstrap_text_colour( cls, status ):
        colours = {
            "passed": "light",
            "failed": "light",
            "aborted": "light",
            "expected_failure": "dark",
            "skipped": "dark",
        }
        return colours[ status ]


    @classmethod
    def _add_render_fields( cls, report ):
        report['selector'] = cls._selector_from_name( report['name'] )
        report['wall_time_label'] = cls._time_string( report['cpu_times']['wall_time'] )
        report['cpu_time_label'] = cls._time_string( report['cpu_times']['process_time'] )
        report['cpu_wall_percent_label'] = cls._percent_string(
            cls._cpu_over_wall_percent(
                report['cpu_times']['process_time'],
                report['cpu_times']['wall_time']
        ) )
        report['style'] = cls._status_bootstrap_style( report['status'] )
        report['text_colour'] = cls._status_bootstrap_text_colour( report['status'] )


    def _create_uri( self, test_case ):
        filepath = 'file' in test_case and test_case['file'] or None
        lineno   = 'line' in test_case and test_case['line'] or None

        if not self._auto_link_tests:
            return None
        if self._link_style == "local":
            link = self._base_uri
            if filepath:
                link += "/" + filepath
            return link
        elif self._link_style == "gitlab":
            link = self._base_uri
            if filepath:
                link += "/" + filepath
                if lineno:
                    link += "#L" + str(lineno)
            return link


    @classmethod
    def _summary_name( cls, env, destination_path ):
        name = env['offset_dir']
        if name.startswith("."+os.path.sep):
            name = name[2:]
        # TODO: Check the assignment to sconscript_name as it is unused
        # sconscript_name = os.path.splitext( os.path.split( env['sconscript_file'] )[1] )[0]
        return name + "/" + os.path.splitext( os.path.splitext( os.path.split( destination_path )[1] )[0] )[0]


    def _write( self, destination_path, env, test_suites, sort_test_cases=False ):

        logger.debug( "Write HTML report for {}".format( destination_path ) )

        name = self._summary_name( env, destination_path )
        tests_title = name

        test_summary = self._create_test_summary( name )
        test_summary['toolchain_variant_dir'] = env['tool_variant_dir']
        test_summary['summary_rel_path'] = os.path.join( destination_subdir( env ), os.path.split( destination_path )[1] )

        test_suite_list = sorted( test_suites.values(), key=lambda test_suite: test_suite["name"] )

        for test_suite in test_suite_list:

            self._add_render_fields( test_suite )
            if sort_test_cases:
                test_suite['test_cases'] = sorted( test_suite['test_cases'], key=lambda test: test["name"] )

            for test_case in test_suite['test_cases']:
                self._add_render_fields( test_case )
                if test_case['stdout']:
                    escaped_stdout = ( escape(line).rstrip() for line in test_case['stdout'] )
                    test_case['stdout'] = escaped_stdout
                test_case['uri'] = self._create_uri( test_case )

            self._update_summary_stats( test_summary, test_suite, "test_suite" )

        self._add_render_fields( test_summary )

        summary_path = self._summary_path( destination_path )
        with open( summary_path, 'w' ) as summary_file:
            json.dump(
                test_summary,
                summary_file,
                sort_keys = True,
                indent = 4,
                separators = (',', ': ')
            )

        template = self.get_template()

        templateRendered = template.render (
            tests_title = tests_title,
            test_summary = test_summary,
            test_suites = test_suite_list)

        with open( destination_path, 'w' ) as test_suite_index:
                test_suite_index.write(encode(templateRendered))


class GenerateHtmlReportMethod(object):

    def __call__( self, env, source, final_dir=None, sort_test_cases=False, auto_link_tests=True, link_style="local" ):
        if 'test' not in env['variant_actions'].keys():
            return []
        builder = GenerateHtmlReportBuilder( final_dir, sort_test_cases=sort_test_cases, auto_link_tests=auto_link_tests, link_style=link_style )
        env['BUILDERS']['GenerateHtmlReport'] = env.Builder( action=builder.GenerateHtmlTestReport, emitter=builder.emitter )
        report = env.GenerateHtmlReport( [], source )
        NotifyProgress.add( env, report )
        return report


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "GenerateHtmlTestReport", cls() )


def destination_subdir( env ):
    return env['flat_tool_variant_dir_offset']


class CollateReportIndexEmitter(object):

    def __init__( self, destination=None ):
        self._destination = destination

    def __call__( self, target, source, env ):
        destination = self._destination
        if not destination:
            destination = env['abs_final_dir']
        else:
            destination = self._destination + destination_subdir( env )

        master_index = env.File( os.path.join( self._destination, "test-report-index.json" ) )
        master_report = env.File( os.path.join( self._destination, "test-report-index.json" ) )

        env.Clean( source, master_index )
        env.Clean( source, master_report )

        ReportIndexBuilder.register_report_folders( final_dir=env['abs_final_dir'], destination_dir=self._destination )

        for html_report, json_report in zip(*[iter(source)]*2):
            target.append( os.path.join( destination, os.path.split( str(html_report) )[1] ) )
            json_report_target = env.File( os.path.join( destination, os.path.split( str(json_report) )[1] ) )
            target.append( json_report_target )
            ReportIndexBuilder.update_index( json_report_target, os.path.split(json_report_target.abspath)[0] )

        logger.trace( "sources = [{}]".format( colour_items( [str(s) for s in source] ) ) )
        logger.trace( "targets = [{}]".format( colour_items( [str(t) for t in target] ) ) )

        env.Depends( master_report, target )
        env.Depends( master_index, target )

        return target, source


class CollateReportIndexAction(object):

    def __init__( self, destination=None ):
        self._destination = destination


    @classmethod
    def _read( cls, json_report_path, default={} ):
        with open( json_report_path, "r" ) as report:
            try:
                report = json.load( report )
                return report
            except ValueError as error:
                logger.error(
                    "Test Report [{}] does not contain valid JSON. Error [{}] encountered while parsing".format(
                    as_info( json_report_path ),
                    as_error( str(error) )
                ) )
        return default


    def __call__( self, target, source, env ):

        logger.trace( "target = [{}]".format( colour_items( [ str(node) for node in target ] ) ) )
        logger.trace( "source = [{}]".format( colour_items( [ str(node) for node in source ] ) ) )

        for html_report_src_tgt, json_report_src_tgt in zip(*[iter(zip( source, target ))]*2):

            html_report = html_report_src_tgt[0]
            json_report = json_report_src_tgt[0]

            html_target = html_report_src_tgt[1]
            json_target = json_report_src_tgt[1]

            logger.trace( "html_report = [{}]".format( as_notice( str(html_report) ) ) )
            logger.trace( "json_report = [{}]".format( as_info( str(json_report) ) ) )
            logger.trace( "html_target = [{}]".format( as_notice( str(html_target) ) ) )
            logger.trace( "json_target = [{}]".format( as_info( str(json_target) ) ) )

            # TODO: Check use of destination as it is currently unused
            # destination = env['abs_final_dir']
            # if self._destination:
                # destination = self._destination + destination_subdir( env )

            logger.trace( "report_summary = {}".format( str( self._read( str(json_report) ) ) ) )

            env.Execute( Copy( html_target, html_report ) )
            env.Execute( Copy( json_target, json_report ) )

        return None

    @classmethod
    def summary_name( cls, env ):
        return os.path.split( env['sconscript_toolchain_build_dir'] )[0] + "/*"


class ReportIndexBuilder(object):

    all_reports = {}
    destination_dirs  = {}

    @classmethod
    def register_report_folders( cls, final_dir=None, destination_dir=None ):

        destination_dir = str(Dir(destination_dir))
        final_dir = str(Dir(final_dir))

        if not destination_dir in cls.destination_dirs:
            cls.destination_dirs[destination_dir] = set()
            cls.destination_dirs[destination_dir].add( final_dir )
        else:
            new_common = None
            new_folder = None
            for path in cls.destination_dirs[destination_dir]:
                common, tail1, tail2 = split_common( path, final_dir )
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
        return jinja2_templates().get_template('test_report_index.html')


    @classmethod
    def update_index( cls, json_report, destination ):
        logger.trace( "add destination = [{}]".format( as_notice(destination) ) )
        if not destination in cls.all_reports:
            cls.all_reports[ destination ] = []
        cls.all_reports[ destination ].append( json_report )


    @classmethod
    def _update_toolchain_variant_summary( cls, summaries, toolchain_variant, summary ):

        if not toolchain_variant in summaries['toolchain_variants']:
            summaries['toolchain_variants'][toolchain_variant] = GenerateHtmlReportBuilder._create_toolchain_variant_summary(
                toolchain_variant
            )

        GenerateHtmlReportBuilder._update_summary_stats(
            summaries['toolchain_variants'][toolchain_variant],
            summary,
            "test_suite"
        )
        GenerateHtmlReportBuilder._add_render_fields(
            summaries['toolchain_variants'][toolchain_variant]
        )


    @classmethod
    def _ranked_status( cls ):
        return [ 'passed', 'skipped', 'expected_failure', 'failed', 'aborted' ]


    @classmethod
    def on_progress( cls, progress, sconscript, variant, env, target, source ):
        if progress == 'sconstruct_end':

            logger.trace( "Destination dirs = [{}]".format( colour_items( cls.destination_dirs.keys() ) ) )
            logger.trace( "cls.all_reports dirs = [{}]".format( colour_items( cls.all_reports.keys() ) ) )

            for destination_dir, final_dirs in six.iteritems(cls.destination_dirs):

                master_index_path = os.path.join( destination_dir, "test-report-index.html" )
                master_report_path = os.path.join( destination_dir, "test-report-index.json" )

                logger.debug( "Master test report index path = [{}]".format( as_notice( master_index_path ) ) )

                template = cls.get_template()

                summaries = {}
                summaries['vcs_info'] = initialise_test_linking( env, link_style="raw" )
                url, repository, branch, remote, revision = summaries['vcs_info']
                summaries['name'] = str(env.Dir(destination_dir)) + "/*"
                summaries['title'] = url and url or env['sconstruct_dir']
                summaries['branch'] = branch and branch or ""
                summaries['remote'] = remote and remote or ""
                summaries['revision'] = revision and revision or ""
                summaries['uri'] = url and url or "Local"
                summaries['toolchain_variants'] = {}
                summaries['reports'] = {}

                for report_dir, json_reports in six.iteritems(cls.all_reports):
                    common, tail1, tail2 = split_common( report_dir, destination_dir )
                    logger.trace( "common, tail1, tail2 = {}, {}, {}".format( as_info(common), as_notice(tail1), as_notice(tail2) ) )
                    if common and (not tail1 or not tail2):

                        for json_report in json_reports:

                            summary = CollateReportIndexAction._read( str(json_report) )

                            toolchain_variant = summary['toolchain_variant_dir']

                            cls._update_toolchain_variant_summary( summaries, toolchain_variant, summary )

                            summary_name = summary['name']

                            if not summary_name in summaries['reports']:
                                summaries['reports'][summary_name] = {}
                                summaries['reports'][summary_name]['variants'] = {}

                            summaries['reports'][summary_name]['variants'][toolchain_variant] = summary

                report_list = summaries['reports'].items()
                report_list = sorted(report_list)

                for name, report in report_list:
                    report['default_variant'] = None
                    report['default_summary_rel_path'] = None
                    variant_count = 0
                    status_rank = 0
                    for variant in six.itervalues(report['variants']):
                        variant_count += 1
                        index = cls._ranked_status().index(variant['status'])
                        if index > status_rank:
                            status_rank = index
                        if not report['default_variant']:
                            report['default_variant'] = variant['toolchain_variant_dir']
                            report['default_summary_rel_path'] = variant['summary_rel_path']

                    report['variant_count'] = variant_count
                    report['status'] = cls._ranked_status()[status_rank]
                    report['selector'] = GenerateHtmlReportBuilder._selector_from_name( name )
                    report['style'] = GenerateHtmlReportBuilder._status_bootstrap_style( report['status'] )
                    report['text_colour'] = GenerateHtmlReportBuilder._status_bootstrap_text_colour( report['status'] )

                summaries_json_report = json.dumps(
                    summaries,
                    sort_keys = True,
                    indent = 4,
                    separators = (',', ': ')
                )

                logger.trace( "summaries = \n{}".format( summaries_json_report ) )

                with open( master_report_path, 'w' ) as master_report_file:
                    master_report_file.write( summaries_json_report )

                templateRendered = template.render(
                    summaries=summaries,
                    report_list=report_list,
                    next=next,
                    len=len)

                with open( master_index_path, 'w' ) as master_index_file:
                    master_index_file.write( encode( templateRendered ) )


NotifyProgress.register_callback( None, ReportIndexBuilder.on_progress )


class CollateTestReportIndexMethod(object):

    def __init__( self ):
        pass

    def __call__( self, env, sources, destination=None ):
        if 'test' not in env['variant_actions'].keys():
            return []

        env['BUILDERS']['CollateTestReportIndexBuilder'] = env.Builder( action=CollateReportIndexAction( destination ), emitter=CollateReportIndexEmitter( destination ) )

        index_file = env.CollateTestReportIndexBuilder( [], Flatten( [ sources ] ) )

        NotifyProgress.add( env, index_file )
        return index_file


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CollateTestReportIndex", cls() )
