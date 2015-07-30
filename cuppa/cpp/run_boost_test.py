
#          Copyright Jamie Allsop 2015-2015
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

import cuppa.timer
import cuppa.test_report.cuppa_json
import cuppa.build_platform
from cuppa.output_processor import IncrementalSubProcess


class Notify(object):


    def __init__( self, scons_env, show_test_output ):
        self._show_test_output = show_test_output
        self._toolchain = scons_env['toolchain']
        self._colouriser = scons_env['colouriser']
        self.master_suite = {}
        self.master_suite['status'] = 'passed'


    def enter_suite(self, suite):
        sys.stdout.write(
            self._colouriser.emphasise( "\nStarting Test Suite [%s]\n" % suite )
        )


    def exit_suite(self, suite):
        sys.stdout.write(
            self._colouriser.emphasise( "\nTest Suite Finished [%s] " % suite['name'] )
        )

        label   = suite['status'].upper()
        meaning = suite['status']

        sys.stdout.write(
            self._colouriser.highlight( meaning, " = {} = ".format( suite['status'].upper() ) )
        )

        sys.stdout.write('\n')

        sys.stdout.write(
            self._colouriser.emphasise( "\nSummary\n" )
        )

        for test in suite['tests']:
            sys.stdout.write(
                self._colouriser.emphasise( "\nTest case [{}]".format( test['name'] ) ) + '\n'
            )
            self._write_test_case( test )

        sys.stdout.write('\n')

        sys.stdout.write(
            self._colouriser.highlight( meaning, " = %s = " % label )
        )

        cuppa.timer.write_time( suite['total_cpu_times'], self._colouriser )

        passed_tests      = suite['passed_tests']
        failed_tests      = suite['failed_tests']
        expected_failures = suite['expected_failures']
        skipped_tests     = suite['skipped_tests']
        aborted_tests     = suite['aborted_tests']
        total_assertions  = suite['total_assertions']
        passed_assertions = suite['passed_assertions']
        failed_assertions = suite['failed_assertions']

        if total_assertions > 0:
            if suite['status'] == 'passed':
                sys.stdout.write(
                    self._colouriser.highlight(
                        meaning,
                        " ( %s of %s Assertions Passed )" % (passed_assertions, total_assertions)
                    )
                )
            else:
                sys.stdout.write(
                    self._colouriser.highlight(
                        meaning,
                        " ( %s of %s Assertions Failed )" % (failed_assertions, total_assertions)
                    )
                )
        else:
            sys.stdout.write(
                self._colouriser.colour(
                    'notice',
                    " ( No Assertions Checked )"
                )
            )

        if suite['status'] == 'passed' and passed_tests > 0:
            sys.stdout.write(
                self._colouriser.highlight(
                    meaning,
                    " ( %s %s Passed ) "
                    % (passed_tests, passed_tests > 1 and 'Test Cases' or 'Test Case')
                )
            )
        elif suite['status'] != 'passed':
            self.master_suite['status'] = 'failed'

        if failed_tests > 0:
            sys.stdout.write(
                self._colouriser.highlight(
                    meaning,
                    " ( %s %s Failed ) "
                    % (failed_tests, failed_tests > 1 and 'Test Cases' or 'Test Case')
                )
            )

        if expected_failures > 0:
            sys.stdout.write(
                self._colouriser.highlight(
                    meaning,
                    " ( %s %s Expected ) "
                    % (expected_failures, expected_failures > 1 and 'Failures' or 'Failure')
                )
            )

        if len( skipped_tests ):
            number = len( skipped_tests )
            sys.stdout.write(
                self._colouriser.highlight(
                    meaning,
                    " ( %s %s Skipped ) "
                    % (number, number > 1 and 'Test Cases' or 'Test Case')
                )
            )

        if aborted_tests > 0:
            sys.stdout.write(
                self._colouriser.highlight(
                    meaning,
                    " ( %s %s Aborted ) "
                    % (aborted_tests, aborted_tests > 1 and 'Test Cases Were' or 'Test Case Was')
                )
            )

        sys.stdout.write('\n\n')


    def _write_test_case( self, test_case ):
        label   = test_case['status']
        meaning = test_case['status']

        sys.stdout.write(
            self._colouriser.highlight( meaning, " = %s = " % label )
        )

        cuppa.timer.write_time( test_case['cpu_times'], self._colouriser )

        assertions = test_case['total']
        passed     = test_case['passed']
        failed     = test_case['failed']

        if test_case['status'] == 'passed' and passed > 0:
            sys.stdout.write(
                self._colouriser.colour(
                    meaning,
                    " ( %s of %s Assertions Passed )" % ( passed, assertions )
                )
            )

        if failed > 0:
            sys.stdout.write(
                self._colouriser.colour(
                    meaning,
                    " ( %s of %s Assertions Failed )" % ( failed, assertions )
                )
            )

        if test_case['total'] == 0:
            sys.stdout.write(
                self._colouriser.colour( 'notice'," ( No Assertions )" )
            )

        sys.stdout.write('\n')


    def enter_test_case(self, test_case):
        sys.stdout.write(
            self._colouriser.emphasise( "\nRunning Test Case [%s] ...\n" % test_case['key'] )
        )
        test_case['timer'] = cuppa.timer.Timer()


    def exit_test_case( self, test ):
        self._write_test_case( test )


    def failed_assertion(self, line ):

        def as_error( text ):
            return self._colouriser.as_error( text )

        def emphasise( text ):
            return self._colouriser.emphasise( text )

        def start_error():
            return self._colouriser.start_colour( "error" )

        def reset():
            return self._colouriser.reset()

        matches = re.match(
            r'(?P<file>[a-zA-Z0-9._/\s\-]+)[(](?P<line>[0-9]+)[)]: '
             '(?P<message>[a-zA-Z0-9(){}:&_<>/\-=!," \[\]]+)',
            line )

        if matches:
            path = matches.group( 'file' )
            line = matches.group( 'line' )
            message = matches.group( 'message')

            error = self._toolchain.error_format()
            sys.stdout.write( error.format(
                    start_error() + emphasise( path ) + start_error(),
                    emphasise( line ) + start_error(),
                    message + reset()
                ) + "\n"
            )
        else:
            sys.stdout.write(
                self._colouriser.colour( "error", line ) + "\n"
            )


    def message(self, line):
        if self._show_test_output:
            sys.stdout.write(
                line + "\n"
            )


class State:
    waiting, test_suite, test_case = range(3)


class ProcessStdout:

    def __init__( self, log, branch_root, notify ):
        self.log = open( log, "w" )
        self.branch_root = branch_root
        self.notify = notify
        self.state = State.waiting
        self.test_case_names = []
        self.test_cases = {}
        self.test_suites = {}
        self.master_test_suite = 'Master Test Suite'


    def entered_test_suite( self, line ):
        matches = re.match(
            r'(?:(?P<file>[a-zA-Z0-9._/\s\-]+)?[(](?P<line>[0-9]+)[)]: )?'
             'Entering test suite "(?P<suite>[a-zA-Z0-9(){}:&_<>/\-, ]+)"',
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
            self.test_suites[self.suite]['failed_assertions'] = 0

            self.test_suites[self.suite]['total_cpu_times']   = cuppa.timer.CpuTimes( 0, 0, 0, 0 )

            self.test_suites[self.suite]['tests'] = []

            self.notify.enter_suite(self.suite)
            return True
        return False


    def leaving_test_suite( self, line ):
        matches = re.match(
            r'Leaving test suite "(?P<suite>[a-zA-Z0-9(){}:&_<>/\-, ]+)"'
             '(\. Test suite (?P<status>passed|failed)\.'
             '(?: (?P<results>.*))?)?',
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
            test_case['failed']     = 0
            test_case['skipped']    = False
            test_case['aborted']    = 0
            self.notify.enter_test_case( test_case )
            return True
        return False

    def leaving_test_case( self, line ):
        test_case = self.test_suites[self.suite]['tests'][-1]

        matches = re.match(
            r'Leaving test case "(?:[a-zA-Z0-9(){}\[\]:;&_<>\-, =]+)"'
             '(?:; testing time: (?P<testing_time>[a-zA-Z0-9.s ,+=()%/]+))?'
             '(\. Test case (?P<status>passed|failed|skipped|aborted)\.'
             '(?: (?P<results>.*))?)?',
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

        matches = re.match(
                r'.*\s(?P<status>passed|failed)(\s[\[][^\[\]]+[\]])?$',
                line.strip() )

        if matches:
            is_assertion = True
            write_line = False
            status = matches.group('status')
            test_case['assertions'] = test_case['assertions'] + 1
            test_case[status] = test_case[status] + 1
            if status == 'failed':
                write_line = True
                self.notify.failed_assertion(line)



        return is_assertion, write_line


    def __call__( self, line ):

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
            if write_line:
                self.log.write( line + '\n' )
            if not is_assertion:
                if self.leaving_test_case( line ):
                    self.state = State.test_suite


    def __exit__( self, type, value, traceback ):
        if self.log:
            self.log.close()


    def tests( self ):
        tests = []
        for suite in self.test_suites.itervalues():
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

    def __init__( self, log, notify ):
        self.log = open( log, "w" )


    def __call__( self, line ):
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

    def __init__( self, final_dir ):
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

    def __init__( self, expected ):
        self._expected = expected


    def __call__( self, target, source, env ):

        executable   = str( source[0].abspath )
        working_dir  = os.path.split( executable )[0]
        program_path = source[0].path
        notifier     = Notify(env, env['show_test_output'])

        if cuppa.build_platform.name() == "Windows":
            executable = '"' + executable + '"'

        test_command = executable + " --log_format=hrf --log_level=all --report_level=no"
        print "cuppa: RunBoostTest: [" + test_command + "]"

        try:
            return_code, tests = self.__run_test( program_path,
                                                  test_command,
                                                  working_dir,
                                                  env['branch_root'],
                                                  notifier )

            cuppa.test_report.cuppa_json.write_report( report_file_name_from( program_path ), tests )

            if return_code < 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                print >> sys.stderr, "cuppa: RunBoostTest: Test was terminated by signal: ", -return_code
            elif return_code > 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                print >> sys.stderr, "cuppa: RunBoostTest: Test returned with error code: ", return_code
            elif notifier.master_suite['status'] != 'passed':
                print >> sys.stderr, "cuppa: RunBoostTest: Not all test suites passed. "

            if return_code:
                self._remove_success_file( success_file_name_from( program_path ) )
            else:
                self._write_success_file( success_file_name_from( program_path ) )

            return None

        except OSError as e:
            print >> sys.stderr, "Execution of [", test_command, "] failed with error: ", str(e)
            return 1


    def __run_test( self, program_path, test_command, working_dir, branch_root, notifier ):
        process_stdout = ProcessStdout( stdout_file_name_from( program_path ), branch_root, notifier )
        process_stderr = ProcessStderr( stderr_file_name_from( program_path ), notifier )

        return_code = IncrementalSubProcess.Popen2( process_stdout,
                                                    process_stderr,
                                                    shlex.split( test_command ),
                                                    cwd=working_dir )

        return return_code, process_stdout.tests()


    def __write_file_to_stderr( self, file_name ):
        with open( file_name, "r" ) as error_file:
            for line in error_file:
                print >> sys.stderr, line


    def _write_success_file( self, file_name ):
        with open( file_name, "w" ) as success_file:
            success_file.write( "success" )


    def _remove_success_file( self, file_name ):
        try:
            os.remove( file_name )
        except:
            pass

