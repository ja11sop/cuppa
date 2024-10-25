
#          Copyright Jamie Allsop 2015-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunBoostTest
#-------------------------------------------------------------------------------
import os
import sys
import shlex
import re
import six

from SCons.Errors import BuildError

import cuppa.timer
import cuppa.test_report.cuppa_json
import cuppa.build_platform
import cuppa.utility.preprocess
from cuppa.output_processor import IncrementalSubProcess
from cuppa.colourise import as_emphasised, as_highlighted, as_colour, start_colour, colour_reset, as_error, as_notice
from cuppa.log import logger


class Notify(object):


    def __init__( self, scons_env, show_test_output ):
        self._show_test_output = show_test_output
        self._toolchain = scons_env['toolchain']
        self.master_suite = {}
        self.master_suite['status'] = 'passed'


    def enter_suite(self, suite):
        sys.stdout.write(
            as_emphasised( "\nStarting Test Suite [%s]\n" % suite )
        )


    def exit_suite(self, suite):
        sys.stdout.write(
            as_emphasised( "\nTest Suite Finished [%s] " % suite['name'] )
        )

        passed_tests      = suite['passed_tests']
        failed_tests      = suite['failed_tests']
        expected_failures = suite['expected_failures']
        skipped_tests     = suite['skipped_tests']
        aborted_tests     = suite['aborted_tests']
        total_assertions  = suite['total_assertions']
        passed_assertions = suite['passed_assertions']
        warned_assertions = suite['warned_assertions']
        failed_assertions = suite['failed_assertions']

        label   = suite['status'].upper()
        meaning = suite['status']

        if meaning == 'passed' and warned_assertions:
            meaning = 'warning'

        sys.stdout.write(
            as_highlighted( meaning, " = {} = ".format( suite['status'].upper() ) )
        )

        sys.stdout.write('\n')

        sys.stdout.write(
            as_emphasised( "\nSummary\n" )
        )

        for test in suite['tests']:
            sys.stdout.write(
                as_emphasised( "\nTest case [{}]".format( test['name'] ) ) + '\n'
            )
            self._write_test_case( test )

        sys.stdout.write('\n')

        sys.stdout.write(
            as_highlighted( meaning, " = %s = " % label )
        )

        cuppa.timer.write_time( suite['total_cpu_times'] )

        if total_assertions > 0:
            if suite['status'] == 'passed':
                if not warned_assertions:
                    sys.stdout.write(
                        as_highlighted(
                            meaning,
                            " ( %s of %s Assertions Passed )" % (passed_assertions, total_assertions)
                        )
                    )
                else:
                    sys.stdout.write(
                        as_highlighted(
                            meaning,
                            " ( %s Passed + %s Warned out of %s Assertions Passed )" % (passed_assertions, warned_assertions, total_assertions)
                        )
                    )
            else:
                sys.stdout.write(
                    as_highlighted(
                        meaning,
                        " ( %s of %s Assertions Failed )" % (failed_assertions, total_assertions)
                    )
                )
        else:
            sys.stdout.write(
                as_colour(
                    'notice',
                    " ( No Assertions Checked )"
                )
            )

        if suite['status'] == 'passed' and passed_tests > 0:
            sys.stdout.write(
                as_highlighted(
                    meaning,
                    " ( %s %s Passed ) "
                    % (passed_tests, passed_tests > 1 and 'Test Cases' or 'Test Case')
                )
            )
        elif suite['status'] != 'passed':
            self.master_suite['status'] = 'failed'

        if failed_tests > 0:
            sys.stdout.write(
                as_highlighted(
                    meaning,
                    " ( %s %s Failed ) "
                    % (failed_tests, failed_tests > 1 and 'Test Cases' or 'Test Case')
                )
            )

        if expected_failures > 0:
            sys.stdout.write(
                as_highlighted(
                    meaning,
                    " ( %s %s Expected ) "
                    % (expected_failures, expected_failures > 1 and 'Failures' or 'Failure')
                )
            )

        if len( skipped_tests ):
            number = len( skipped_tests )
            sys.stdout.write(
               as_highlighted(
                    meaning,
                    " ( %s %s Skipped ) "
                    % (number, number > 1 and 'Test Cases' or 'Test Case')
                )
            )

        if aborted_tests > 0:
            sys.stdout.write(
                as_highlighted(
                    meaning,
                    " ( %s %s Aborted ) "
                    % (aborted_tests, aborted_tests > 1 and 'Test Cases Were' or 'Test Case Was')
                )
            )

        sys.stdout.write( '\n\n')


    def _write_test_case( self, test_case ):
        label   = test_case['status']
        meaning = test_case['status']

        assertions = test_case['total']
        passed     = test_case['passed']
        warned     = test_case['warned']
        failed     = test_case['failed']

        if meaning == 'passed' and warned:
            meaning = warned

        sys.stdout.write(
            as_highlighted( meaning, " = %s = " % label )
        )

        cuppa.timer.write_time( test_case['cpu_times'] )

        if test_case['status'] == 'passed' and passed and not warned:
            sys.stdout.write(
                as_colour(
                    meaning,
                    " ( %s of %s Assertions Passed )" % ( passed, assertions )
                )
            )
        elif test_case['status'] == 'passed' and warned:
            sys.stdout.write(
                as_colour(
                    meaning,
                    " ( %s Passed + %s Warned out of %s Assertions )" % ( passed, warned, assertions )
                )
            )

        if failed > 0:
            sys.stdout.write(
                as_colour(
                    meaning,
                    " ( %s of %s Assertions Failed )" % ( failed, assertions )
                )
            )

        if test_case['total'] == 0:
            sys.stdout.write(
                as_colour( 'notice'," ( No Assertions )" )
            )

        sys.stdout.write('\n')


    def enter_test_case(self, test_case):
        sys.stdout.write(
            as_emphasised( "\nRunning Test Case [%s] ...\n" % test_case['key'] )
        )
        test_case['timer'] = cuppa.timer.Timer()


    def exit_test_case( self, test ):
        self._write_test_case( test )


    def display_assertion(self, line, level ):

        def start( level ):
            return start_colour( level )

        matches = re.match(
            r'(?P<file>[a-zA-Z0-9.@_/\s\-]+)[(](?P<line>[0-9]+)[)]: '
            r'(?P<message>[a-zA-Z0-9(){}:%.*&_<>/\-+=!," \[\]]+)',
            line )

        if matches:
            path = matches.group( 'file' )
            line = matches.group( 'line' )
            message = matches.group( 'message')
            display = self._toolchain.error_format()
            sys.stdout.write( display.format(
                    start(level) + as_emphasised( path ) + start(level),
                    as_emphasised( line ) + start(level),
                    message + colour_reset()
                ) + "\n"
            )
        else:
            sys.stdout.write(
                as_colour( level, line ) + "\n"
            )


    def message(self, line):
        if self._show_test_output:
            sys.stdout.write(
                line + "\n"
            )


class State:
    waiting, test_suite, test_case = range(3)



class ProcessStdout:

    def __init__( self, log, notify, preprocess ):
        self.log = open( log, "w" )
        self.preprocess = preprocess
        self.notify = notify
        self.state = State.waiting
        self.test_case_names = []
        self.test_cases = {}
        self.test_suites = {}
        self.master_test_suite = 'Master Test Suite'


    def entered_test_suite( self, line ):
        matches = re.match(
            r'(?:(?P<file>[a-zA-Z0-9.@_/\s\-]+)?[(](?P<line>[0-9]+)[)]: )?'
            r'Entering test (suite|module) "(?P<suite>[a-zA-Z0-9(){}:&_<>/\-, ]+)"',
            line.strip() )

        if matches and matches.group('suite') != self.master_test_suite:
            self.suite = matches.group('suite')
            self.test_suites[self.suite] = {}

            self.test_suites[self.suite]['name'] = self.suite

            self.test_suites[self.suite]['total_tests']       = 0
            self.test_suites[self.suite]['expected_failures'] = 0
            self.test_suites[self.suite]['passed_tests']      = 0
            self.test_suites[self.suite]['failed_tests']      = 0
            self.test_suites[self.suite]['skipped_tests']     = []
            self.test_suites[self.suite]['aborted_tests']     = 0
            self.test_suites[self.suite]['total_assertions']  = 0
            self.test_suites[self.suite]['passed_assertions'] = 0
            self.test_suites[self.suite]['warned_assertions'] = 0
            self.test_suites[self.suite]['failed_assertions'] = 0

            self.test_suites[self.suite]['total_cpu_times']   = cuppa.timer.CpuTimes( 0, 0, 0, 0 )

            self.test_suites[self.suite]['tests'] = []

            self.notify.enter_suite(self.suite)
            return True
        return False


    def leaving_test_suite( self, line ):
        matches = re.match(
            r'(?:(?P<file>[a-zA-Z0-9.@_/\\\s\-]+)[(](?P<line>[0-9]+)[)]: )?'
            r'Leaving test (suite|module) "(?P<suite>[a-zA-Z0-9(){}:&_<>/\-, ]+)"'
            r'(?:; testing time: (?P<testing_time>[a-zA-Z0-9.s ,+=()%/]+))?'
            r'(\. Test suite (?P<status>passed|failed)\.'
            r'(?: (?P<results>.*))?)?',
            line.strip() )

        if matches and matches.group('suite') != self.master_test_suite:
            suite = self.test_suites[matches.group('suite')]

            if matches.group('status'):
                suite['status'] = matches.group('status')

            if matches.group('results'):
                self.store_suite_results(suite, matches.group('results'))
            else:
                self.collate_suite_results(suite)

            self.notify.exit_suite(suite)
            return True
        else:
            return False


    def skipped_test_case( self, line ):
        matches = re.match(
            r'Test "(?P<test>[a-zA-Z0-9(){}\[\]:;&_<>\-, =]+)" is skipped',
            line.strip() )

        if matches:
            name = matches.group('test')
            self.test_suites[self.suite]['skipped_tests'].append( name )
            return True

        return False

    def entered_test_case( self, line ):
        matches = re.match(
            r'(?:(?P<file>[a-zA-Z0-9.@_/\\\s\-]+)[(](?P<line>[0-9]+)[)]: )?'
            r'Entering test case "(?P<test>[a-zA-Z0-9(){}\[\]:;&_<>\-, =]+)"',
            line.strip() )

        if matches:
            name = matches.group('test')

            self.test_suites[self.suite]['tests'].append( {} )
            test_case = self.test_suites[self.suite]['tests'][-1]

            test_case['suite']      = self.suite
            test_case['fixture']    = self.suite
            test_case['key']        =  '[' + self.suite + '] ' + name
            test_case['name']       = name
            test_case['stdout']     = []
            test_case['total']      = 0
            test_case['assertions'] = 0
            test_case['passed']     = 0
            test_case['warned']     = 0
            test_case['failed']     = 0
            test_case['skipped']    = False
            test_case['aborted']    = 0
            test_case['line']       = matches.group('line')
            test_case['file']       = matches.group('file')
            test_case['_state_']    = 'handle_asserts'
            self.notify.enter_test_case( test_case )
            return True
        return False

    def leaving_test_case( self, line ):
        test_case = self.test_suites[self.suite]['tests'][-1]

        matches = re.match(
            r'(?:(?P<file>[a-zA-Z0-9.@_/\\\s\-]+)[(](?P<line>[0-9]+)[)]: )?'
            r'Leaving test case "(?:[a-zA-Z0-9(){}\[\]:;&_<>\-, =]+)"'
            r'(?:; testing time: (?P<testing_time>[a-zA-Z0-9.s ,+=()%/]+))?'
            r'(\. Test case (?P<status>passed|failed|skipped|aborted)\.'
            r'(?: (?P<results>.*))?)?',
            line.strip() )

        if matches:

            test_case['timer'].stop()
            test_case['cpu_times'] = test_case['timer'].elapsed()

            if matches.group('status'):
                test_case['status'] = matches.group('status')
            else:
                test_case['status'] = 'passed'

            if matches.group('results'):
                self.store_test_results(test_case, matches.group('results'))
            else:
                self.collate_test_case_results( test_case )

            self.test_case_names.append( test_case['key'] )
            self.notify.exit_test_case(test_case)
            return True
        else:
            test_case['stdout'].append( line )
            self.notify.message(line)
            return False


    def handle_assertion( self, line ):
        test_case = self.test_suites[self.suite]['tests'][-1]

        is_assertion = False
        write_line = True

        # [a-zA-Z0-9(){}:%.*&_<>/\-+=\'!," \[\]]
        matches = re.match( r'[^:]*[:]\s(?P<level>info|warning|error|fatal)[ :].*', line.strip() )

        if matches:
            is_assertion = True
            write_line = False
            status = 'failed'
            level = matches.group('level')
            if level == "error" or level == "fatal":
                status = 'failed'
            elif level == "warning":
                status = 'warned'
            elif level == "info":
                status = 'passed'

            test_case['assertions'] = test_case['assertions'] + 1
            test_case[status] = test_case[status] + 1
            test_case['_state_'] = 'handle_asserts'

            if level == 'warning':
                write_line = True
                self.notify.display_assertion( line, "warning" )
            if status == 'failed':
                write_line = True
                test_case['_state_'] = 'handle_failed'
                self.notify.display_assertion( line, "error" )

        elif test_case['_state_'] == 'handle_failed':
            has_context_matches = re.match( r'Failure occurred in (?:a|the) following context:', line.strip() )
            if has_context_matches:
                self.notify.display_assertion( "Failure occurred in the following context:", "error" )
                test_case['_state_'] = 'handle_context'
            else:
                test_case['_state_'] == 'handle_asserts'

        elif test_case['_state_'] == 'handle_context':
            context_matches = re.match( r'\s\s\s\s.*', line.rstrip() )
            if context_matches:
                self.notify.display_assertion( line, "error" )
            else:
                test_case['_state_'] == 'handle_asserts'

        return is_assertion, write_line


    def __call__( self, line ):

        line = self.preprocess( line )

        if not self.state == State.test_case:
            self.log.write( line + '\n' )

        if self.state == State.waiting:
            if self.entered_test_suite( line ):
                self.state = State.test_suite
            elif self.leaving_test_suite( line ):
                self.state = State.waiting

        elif self.state == State.test_suite:
            if self.entered_test_case( line ):
                self.state = State.test_case
            elif self.skipped_test_case( line ):
                self.state = State.test_suite
            elif self.entered_test_suite( line ):
                self.state = State.test_suite
            elif self.leaving_test_suite( line ):
                self.state = State.waiting

        elif self.state == State.test_case:
            is_assertion, write_line = self.handle_assertion( line )
            #if write_line:
            if not is_assertion:
                if self.leaving_test_case( line ):
                    self.state = State.test_suite


    def __exit__( self, type, value, traceback ):
        if self.log:
            self.log.close()


    def tests( self ):
        tests = []
        for suite in six.itervalues(self.test_suites):
            for test_case in suite['tests']:
                tests.append( test_case )
        return tests


    def collate_test_case_results( self, test ):
        test['status'] = ( test['failed'] or test['aborted'] ) and 'failed' or 'passed'
        test['total'] = test['assertions']

        test['cpu_time']  = test['cpu_times'].process
        test['wall_time'] = test['cpu_times'].wall
        test['user_time'] = test['cpu_times'].user
        test['sys_time']  = test['cpu_times'].system

        test['cpu_duration']  = cuppa.timer.as_duration_string( test['cpu_time'] )
        test['wall_duration'] = cuppa.timer.as_duration_string( test['wall_time'] )
        test['user_duration'] = cuppa.timer.as_duration_string( test['user_time'] )
        test['sys_duration']  = cuppa.timer.as_duration_string( test['sys_time'] )

        test['wall_cpu_percent'] = cuppa.timer.as_wall_cpu_percent_string( test['cpu_times'] )

        test_suite = self.test_suites[test['suite']]

        test_suite['passed_tests']  = test_suite['passed_tests'] + ( test['passed'] and 1 or 0 )
        test_suite['failed_tests']  = test_suite['failed_tests'] + ( test['failed'] and 1 or 0 )
        test_suite['aborted_tests'] = test_suite['aborted_tests'] + ( test['aborted'] and 1 or 0 )

        test_suite['total_assertions']  = test_suite['total_assertions'] + test['total']
        test_suite['passed_assertions'] = test_suite['passed_assertions'] + test['passed'] + test['skipped']
        test_suite['warned_assertions'] = test_suite['warned_assertions'] + test['warned']
        test_suite['failed_assertions'] = test_suite['failed_assertions'] + test['failed'] + test['aborted']

        test_suite['total_cpu_times'] += test['cpu_times']


    def store_test_results(self, test, results):
        matches = []

        for result in results.split('.'):
            matched = re.match(
                r'(?P<count>[0-9]+) assertions? out of (?P<total>[0-9]+) (?P<status>passed|failed)',
                result.strip()
            )
            if matched:
                matches.append(matched)

        for match in matches:
            count  = match.group('count')
            total  = match.group('total')
            status = match.group('status')

            test['total'] = total

            if status == 'passed':
                test['passed'] = count
            elif status == 'failed':
                test['failed'] = count

        ## For backward compatibility - remove later
        test['assertions'] = test['total']


    def collate_suite_results( self, suite ):
        suite['status'] = suite['failed_assertions'] and 'failed' or 'passed'

        suite['cpu_time']  = suite['total_cpu_times'].process
        suite['wall_time'] = suite['total_cpu_times'].wall
        suite['user_time'] = suite['total_cpu_times'].user
        suite['sys_time']  = suite['total_cpu_times'].system

        suite['cpu_duration']  = cuppa.timer.as_duration_string( suite['cpu_time'] )
        suite['wall_duration'] = cuppa.timer.as_duration_string( suite['wall_time'] )
        suite['user_duration'] = cuppa.timer.as_duration_string( suite['user_time'] )
        suite['sys_duration']  = cuppa.timer.as_duration_string( suite['sys_time'] )

        suite['wall_cpu_percent'] = cuppa.timer.as_wall_cpu_percent_string( suite['total_cpu_times'] )


    def store_suite_results(self, suite, results):
        matches = []

        for result in results.split('.'):
            matched = re.match(
                r'(?P<count>[0-9]+) (?P<type>assertions?|test cases?|failures?) '
                 '((?P<expected>expected)|(out of (?P<total>[0-9]+) '
                 '(?P<status>passed|failed|skipped|aborted)))',
                result.strip()
            )
            if matched:
                matches.append(matched)

        for match in matches:
            count = match.group('count')
            type  = match.group('type')
            expected_failures = match.group('expected')
            total  = match.group('total')
            status = match.group('status')

            if not expected_failures:
                if type.startswith('test case'):
                    suite['total_tests'] = total
                elif type.startswith('assertion'):
                    suite['total_assertions'] = total
            else:
                suite['expected_failures'] = count

            if status == 'passed':
                if type.startswith('test case'):
                    suite['passed_tests'] = count
                elif type.startswith('assertion'):
                    suite['passed_assertions'] = count
            elif status == 'failed':
                if type.startswith('test case'):
                    suite['failed_tests'] = count
                elif type.startswith('assertion'):
                    suite['failed_assertions'] = count
            elif status == 'skipped':
                suite['skipped_tests'] = count
            elif status == 'aborted':
                suite['aborted_tests'] = count



class ProcessStderr:

    def __init__( self, log, notify, preprocess ):
        self.preprocess = preprocess
        self.log = open( log, "w" )


    def __call__( self, line ):
        line = self.preprocess( line )
        self.log.write( line + '\n' )


    def __exit__( self, type, value, traceback ):
        if self.log:
            self.log.close()


def stdout_file_name_from( program_file ):
    return program_file + '.stdout.log'


def stderr_file_name_from( program_file ):
    return program_file + '.stderr.log'


def report_file_name_from( program_file ):
    return program_file + '.report.json'


def success_file_name_from( program_file ):
    return program_file + '.success'



class RunBoostTestEmitter:

    def __init__( self, final_dir, **ignored_kwargs ):
        self._final_dir = final_dir


    def __call__( self, target, source, env ):

        program_file = os.path.join( self._final_dir, os.path.split( str( source[0] ) )[1] )

        target = []
        target.append( stdout_file_name_from( program_file ) )
        target.append( stderr_file_name_from( program_file ) )
        target.append( report_file_name_from( program_file ) )
        target.append( success_file_name_from( program_file ) )

        return target, source



class RunBoostTest:

    @classmethod
    def default_preprocess( cls, line ):
        return line

    def __init__( self, expected, final_dir,working_dir=None, **ignored_kwargs ):
        self._expected = expected
        self._final_dir = final_dir
        self._working_dir = working_dir


    def __call__( self, target, source, env ):

        executable   = str( source[0].abspath )
        working_dir  = self._working_dir and self._working_dir or os.path.split( executable )[0]
        program_path = source[0].path
        notifier     = Notify(env, env['show_test_output'])

        if cuppa.build_platform.name() == "Windows":
            executable = '"' + executable + '"'

        boost_version = None
        preprocess = self.default_preprocess
        argument_prefix = ""

        if 'boost' in env['dependencies']:
            boost_version = env['dependencies']['boost']( env ).numeric_version()
            if env['dependencies']['boost']( env ).patched_test():
                argument_prefix="boost.test."
            elif env['dependencies']['boost_package']( env ).patched_test():
                argument_prefix="boost.test."

        test_command = executable + " --{0}log_format=hrf --{0}log_level=all --{0}report_level=no".format( argument_prefix )

        if boost_version:
            if boost_version >= 1.69:
                test_command = executable + " --{0}log_format=HRF --{0}log_level=all --{0}report_level=no --{0}color_output=no".format( argument_prefix )
            elif boost_version >= 1.67:
                preprocess = cuppa.utility.preprocess.AnsiEscape.strip
                test_command = executable + " --{0}log_format=HRF --{0}log_level=all --{0}report_level=no --{0}color_output=no".format( argument_prefix )
            elif boost_version >= 1.60:
                test_command = executable + " --{0}log_format=HRF --{0}log_level=all --{0}report_level=no".format( argument_prefix )

        try:
            return_code, tests = self.__run_test( program_path,
                                                  test_command,
                                                  working_dir,
                                                  notifier,
                                                  preprocess,
                                                  env )

            cuppa.test_report.cuppa_json.write_report( report_file_name_from( program_path ), tests )

            if return_code < 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                logger.error( "Test was terminated by signal: {}".format( as_error(str(return_code) ) ) )
            elif return_code > 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                logger.error( "Test returned with error code: {}".format( as_error(str(return_code) ) ) )
            elif notifier.master_suite['status'] != 'passed':
                logger.error( "Not all test suites passed" )
                raise BuildError( node=source[0], errstr="Not all test suites passed" )

            if return_code:
                self._remove_success_file( success_file_name_from( program_path ) )
                if return_code < 0:
                    raise BuildError( node=source[0], errstr="Test was terminated by signal: {}".format( str(-return_code) ) )
                else:
                    raise BuildError( node=source[0], errstr="Test returned with error code: {}".format( str(return_code) ) )
            else:
                self._write_success_file( success_file_name_from( program_path ) )

            return None

        except OSError as e:
            logger.error( "Execution of [{}] failed with error: {}".format( as_notice(test_command), as_notice(str(e)) ) )
            raise BuildError( e )


    def __run_test( self, program_path, test_command, working_dir, notifier, preprocess, env ):
        process_stdout = ProcessStdout( stdout_file_name_from( program_path ), notifier, preprocess )
        process_stderr = ProcessStderr( stderr_file_name_from( program_path ), notifier, preprocess )

        return_code = IncrementalSubProcess.Popen2( process_stdout,
                                                    process_stderr,
                                                    shlex.split( test_command ),
                                                    cwd=working_dir,
                                                    scons_env=env )

        return return_code, process_stdout.tests()


    def __write_file_to_stderr( self, file_name ):
        with open( file_name, "r" ) as error_file:
            for line in error_file:
                sys.stderr.write( line + '\n' )


    def _write_success_file( self, file_name ):
        with open( file_name, "w" ) as success_file:
            success_file.write( "success" )


    def _remove_success_file( self, file_name ):
        try:
            os.remove( file_name )
        except:
            pass

