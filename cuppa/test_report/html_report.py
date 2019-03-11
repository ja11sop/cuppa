
#          Copyright Jamie Allsop 2019-2019
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
import cgi
from jinja2 import Environment, PackageLoader, select_autoescape

import cuppa.progress
import cuppa.timer
from cuppa.colourise import as_notice, as_info, as_warning, as_error, colour_items, emphasise_time_by_digit
from cuppa.log import logger


jinja2_env = None

def jinja2_templates():
    global jinja2_env
    if jinja2_env:
        return jinja2_env
    else:
        jinja2_env = Environment(
            loader=PackageLoader( 'cuppa', 'test_report/templates' ),
            autoescape=select_autoescape(['html', 'xml'])
        )
        return jinja2_env



class GenerateHtmlReportBuilder(object):

    def __init__( self, final_dir, sort_test_cases=False, auto_link_tests=True, link_style="local" ):
        self._final_dir = final_dir
        self._sort_test_cases = sort_test_cases
        self._auto_link_tests = auto_link_tests
        self._link_style = link_style


    def emitter( self, target, source, env ):
        sources = []
        targets = []
        try:
            for s in source:
                if os.path.splitext( str(s) )[1] == ".json":
                    sources.append( str(s) )
                    target_report = os.path.splitext( str(s) )[0] + ".html"
                    targets.append( target_report )
        except StopIteration:
            pass
        return targets, sources


    def GenerateHtmlTestReport( self, target, source, env ):

        self._initialise_test_linking( env )

        for s, t in itertools.izip( source, target ):
            test_suites = {}

            logger.trace( "source = [{}]".format( as_info(str(s)) ) )
            logger.trace( "target = [{}]".format( as_info(str(t)) ) )

            test_cases = self._read( s.abspath )
            for test_case in test_cases:

                if not 'assertions_count' in test_case:
                    test_case['assertions_count'] = test_case['assertions']
                    test_case['assertions_passed'] = test_case['passed']
                    test_case['assertions_failed'] = test_case['failed']
                    test_case['assertions_aborted'] = test_case['aborted']

                self._add_to_test_suites( test_suites, test_case )
            self._write( str(t), env, test_suites, sort_test_cases=self._sort_test_cases )
        return None


    @classmethod
    def _initialise_test_summary( cls, name, report={} ):

        report = cls._initialise_test_suite( name, report )

        report['test_suites_count'] = 0
        report['test_suites_passed'] = 0
        report['test_suites_failed'] = 0
        report['test_suites_expected_failures'] = 0
        report['test_suites_aborted'] = 0
        report['test_suites_skipped'] = 0

        return report


    @classmethod
    def _initialise_test_suite( cls, name, report={} ):

        report['name'] = name

        report['test_cases'] = []

        report['tests_count'] = 0
        report['tests_passed'] = 0
        report['tests_failed'] = 0
        report['tests_expected_failures'] = 0
        report['tests_aborted'] = 0
        report['tests_skipped'] = 0

        report['status'] = "passed"

        report['assertions_count'] = 0
        report['assertions_passed'] = 0
        report['assertions_failed'] = 0
        report['assertions_aborted'] = 0

        report['cpu_times'] = {
            "process_time": 0,
            "system_time": 0,
            "user_time": 0,
            "wall_time": 0
        }

        report['wall_cpu_percent'] = 'n/a'

        return report


    @classmethod
    def _add_to_test_suites( cls, test_suites, test_case ):
        logger.trace( "test_case = [{}]".format( as_notice( str(test_case) ) ) )
        suite = test_case['suite']
        if not suite in test_suites:
            test_suites[suite] = cls._initialise_test_suite( suite )
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
        time_text = cuppa.timer.as_duration_string( nanoseconds )
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
        hasher.update( name )
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


    def _initialise_test_linking( self, env ):
        self._base_uri = ""
        if not self._auto_link_tests:
            return
        if self._link_style == "local":
            # TODO: escape properly and make sure this works on Windows
            self._base_uri = "file://" + env['sconstruct_dir']
        elif self._link_style == "gitlab":
            # NOTE: Might need to do VCS detection per test file
            from cuppa.location import Location
            vcs_info = Location.detect_vcs_info( env['sconstruct_dir'] )
            self._base_uri = os.path.join( os.path.splitext(vcs_info[0])[0], "blob", vcs_info[4] )


    def _create_uri( self, filepath, lineno ):
        if not self._auto_link_tests:
            return None
        if self._link_style == "local":
            return self._base_uri + "/" + filepath
        elif self._link_style == "gitlab":
            return self._base_uri + "/" + filepath + "#L" + str(lineno)


    def _write( self, destination_path, env, test_suites, sort_test_cases=False ):

        logger.debug( "Write HTML report for {}".format( destination_path ) )

        tests_title = env['offset_dir'] + "/*"
        test_summary = self._initialise_test_summary( "Summary" )
        test_suite_list = sorted( test_suites.values(), key=lambda test_suite: test_suite["name"] )

        for test_suite in test_suite_list:

            self._add_render_fields( test_suite )
            if sort_test_cases:
                test_suite['test_cases'] = sorted( test_suite['test_cases'], key=lambda test: test["name"] )

            for test_case in test_suite['test_cases']:
                self._add_render_fields( test_case )
                if test_case['stdout']:
                    escaped_stdout = ( cgi.escape(line).rstrip() for line in test_case['stdout'] )
                    test_case['stdout'] = escaped_stdout
                test_case['uri'] = self._create_uri( test_case['file'], test_case['line'] )

            self._update_summary_stats( test_summary, test_suite, "test_suite" )

        self._add_render_fields( test_summary )

        template = self.get_template()

        with open( destination_path, 'w' ) as test_suite_index:
            test_suite_index.write(
                template.render(
                    tests_title = tests_title,
                    test_summary = test_summary,
                    test_suites = test_suite_list,
                ).encode('utf-8')
            )


class GenerateHtmlReportMethod(object):

    def __call__( self, env, source, final_dir=None, sort_test_cases=False, auto_link_tests=True, link_style="local" ):
        builder = GenerateHtmlReportBuilder( final_dir, sort_test_cases=sort_test_cases, auto_link_tests=auto_link_tests, link_style=link_style )
        env['BUILDERS']['GenerateHtmlReport'] = env.Builder( action=builder.GenerateHtmlTestReport, emitter=builder.emitter )
        report = env.GenerateHtmlReport( [], source )
        cuppa.progress.NotifyProgress.add( env, report )
        return report


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "GenerateHtmlTestReport", cls() )

