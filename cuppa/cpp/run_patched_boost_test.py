
#          Copyright Jamie Allsop 2011-2015
#          Copyright Declan Traynor 2012
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunPatchedBoostTest
#-------------------------------------------------------------------------------
from cuppa.output_processor import IncrementalSubProcess

import os
import sys
import shlex
import re
import cgi


class Notify:


    def __init__( self, scons_env ):
        self.colouriser = scons_env['colouriser']
        self.master_suite = {}
        self.master_suite['status'] = 'success'


    def enter_suite(self, suite):
        sys.stdout.write(
            self.colouriser.emphasise( "\nStarting Test Suite [%s]\n" % suite )
        )


    def exit_suite(self, suite):
        sys.stdout.write(
            self.colouriser.emphasise( "\nTest Suite Finished [%s]\n" % suite['name'] )
        )

        label   = suite['status'].upper()
        meaning = suite['status']

        store_durations( suite )

        sys.stdout.write(
            self.colouriser.highlight( meaning, " = %s = " % label )
        )

        self.__write_time( suite )

        total_tests       = int(suite['total_tests'])
        passed_tests      = int(suite['passed_tests'])
        failed_tests      = int(suite['failed_tests'])
        expected_failures = int(suite['expected_failures'])
        skipped_tests     = int(suite['skipped_tests'])
        aborted_tests     = int(suite['aborted_tests'])
        total_assertions  = int(suite['total_assertions'])
        passed_assertions = int(suite['passed_assertions'])
        failed_assertions = int(suite['failed_assertions'])

        if total_assertions > 0:
            if suite['status'] == 'passed':
                sys.stdout.write(
                    self.colouriser.highlight(
                        meaning,
                        " ( %s of %s Assertions Passed )" % (passed_assertions, total_assertions)
                    )
                )
            else:
                sys.stdout.write(
                    self.colouriser.highlight(
                        meaning,
                        " ( %s of %s Assertions Failed )" % (failed_assertions, total_assertions)
                    )
                )
        else:
            sys.stdout.write(
                self.colouriser.colour(
                    'notice',
                    " ( No Assertions Checked )"
                )
            )

        if suite['status'] == 'passed' and passed_tests > 0:
            sys.stdout.write(
                self.colouriser.highlight(
                    meaning,
                    " ( %s %s Passed ) "
                    % (passed_tests, passed_tests > 1 and 'Test Cases' or 'Test Case')
                )
            )
        else:
            self.master_suite['status'] = 'failed'

        if failed_tests > 0:
            sys.stdout.write(
                self.colouriser.highlight(
                    meaning,
                    " ( %s %s Failed ) "
                    % (failed_tests, failed_tests > 1 and 'Test Cases' or 'Test Case')
                )
            )

        if expected_failures > 0:
            sys.stdout.write(
                self.colouriser.highlight(
                    meaning,
                    " ( %s %s Expected ) "
                    % (expected_failures, expected_failures > 1 and 'Failures' or 'Failure')
                )
            )

        if skipped_tests > 0:
            sys.stdout.write(
                self.colouriser.highlight(
                    meaning,
                    " ( %s %s Skipped ) "
                    % (skipped_tests, skipped_tests > 1 and 'Test Cases' or 'Test Case')
                )
            )

        if aborted_tests > 0:
            sys.stdout.write(
                self.colouriser.highlight(
                    meaning,
                    " ( %s %s Aborted ) "
                    % (aborted_tests, aborted_tests > 1 and 'Test Cases Were' or 'Test Case Was')
                )
            )

        sys.stdout.write('\n\n')


    def enter_test(self, test):
        pass
        sys.stdout.write(
            self.colouriser.emphasise( "\nRunning Test Case [%s] ...\n" % test )
        )


    def exit_test( self, test ):
        label         = test['status']
        meaning       = test['status']

        sys.stdout.write(
            self.colouriser.highlight( meaning, " = %s = " % label )
        )

        self.__write_time( test )

        assertions = int(test['total'])
        passed     = int(test['passed'])
        failed     = int(test['failed'])

        if test['status'] == 'passed' and passed > 0:
            sys.stdout.write(
                self.colouriser.colour(
                    meaning,
                    " ( %s of %s Assertions Passed )" % ( passed, assertions )
                )
            )

        if failed > 0:
            sys.stdout.write(
                self.colouriser.colour(
                    meaning,
                    " ( %s of %s Assertions Failed )" % ( failed, assertions )
                )
            )

        if test['total'] == 0:
            sys.stdout.write(
                self.colouriser.colour( 'notice'," ( No Assertions )" )
            )

        sys.stdout.write('\n')


    def __write_time( self, results ):
        sys.stdout.write( " Time:" )

        if 'wall_duration' in results:
            sys.stdout.write(
                " Wall [ %s ]" % self.colouriser.emphasise_time_by_digit( results['wall_duration'] )
            )

        sys.stdout.write(
            " CPU [ %s ]" % self.colouriser.emphasise_time_by_digit( results['cpu_duration'] )
        )

        if 'wall_cpu_percent' in results:
            wall_cpu_percent = results['wall_cpu_percent'].upper()
            format = "%6s%%"
            if wall_cpu_percent == "N/A":
                format = "%5s  "
            wall_cpu_percent = format % wall_cpu_percent
            sys.stdout.write(
                " CPU/Wall [ %s ]" % self.colouriser.colour( 'time', wall_cpu_percent )
            )

    def message(self, line):
        sys.stdout.write(
            line + "\n"
        )


def stdout_from_program( program_file ):
    return program_file + '.stdout.log'


def stderr_from_program( program_file ):
    return program_file + '.stderr.log'


def report_from_program( program_file ):
    return program_file + '.report.xml'


def store_durations( results ):
    if 'cpu_time' in results:
        results['cpu_duration']  = duration_from_elapsed(results['cpu_time'])
    if 'wall_time' in results:
        results['wall_duration'] = duration_from_elapsed(results['wall_time'])
    if 'user_time' in results:
        results['user_duration'] = duration_from_elapsed(results['user_time'])
    if 'sys_time' in results:
        results['sys_duration']  = duration_from_elapsed(results['sys_time'])


class RunPatchedBoostTestEmitter:

    def __init__( self, final_dir ):
        self.__final_dir = final_dir


    def __call__( self, target, source, env ):

#        print "RunBoostTestEmitter source[0] = " + str(source)

        program_file = os.path.join( self.__final_dir, os.path.split( source[0].path )[1] )

#        print "RunBoostTestEmitter program_file = " + program_file

        target = []
        target.append( stdout_from_program( program_file ) )
        target.append( stderr_from_program( program_file ) )
        target.append( report_from_program( program_file ) )

#        import SCons
#        print "Targets = " + str([isinstance(t, SCons.Node.FS.File) and t.path or t for t in target])
#        print "Source = " + str(source[0].path)
        return target, source


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

            self.test_suites[self.suite]['cpu_time']          = 0
            self.test_suites[self.suite]['wall_time']         = 0
            self.test_suites[self.suite]['user_time']         = 0
            self.test_suites[self.suite]['sys_time']          = 0
            self.test_suites[self.suite]['total_tests']       = 0
            self.test_suites[self.suite]['expected_failures'] = 0
            self.test_suites[self.suite]['passed_tests']      = 0
            self.test_suites[self.suite]['failed_tests']      = 0
            self.test_suites[self.suite]['skipped_tests']     = 0
            self.test_suites[self.suite]['aborted_tests']     = 0
            self.test_suites[self.suite]['total_assertions']  = 0
            self.test_suites[self.suite]['passed_assertions'] = 0
            self.test_suites[self.suite]['failed_assertions'] = 0

            self.notify.enter_suite(self.suite)
            return True
        return False

    def leaving_test_suite( self, line ):
        matches = re.match(
            r'Leaving test suite "(?P<suite>[a-zA-Z0-9(){}:&_<>/\-, ]+)"'
             '\. Test suite (?P<status>passed|failed)\.'
             '(?: (?P<results>.*))?',
            line.strip() )

        if matches and matches.group('suite') != self.master_test_suite:
            suite = self.test_suites[matches.group('suite')]

            if matches.group('status'):
                suite['status'] = matches.group('status')

            if matches.group('results'):
                self.store_suite_results(suite, matches.group('results'))

            self.notify.exit_suite(suite)
            return True
        else:
            return False

    def entered_test_case( self, line ):
        matches = re.match(
            r'(?:(?P<file>[a-zA-Z0-9._/\s\-]+)[(](?P<line>[0-9]+)[)]: )?'
             'Entering test case "(?P<test>[a-zA-Z0-9(){}\[\]:;&_<>\-, =]+)"',
            line.strip() )

        if matches:
            name = matches.group('test')
            self.test = '[' + self.suite + '] ' + name
            self.test_cases[ self.test ] = {}
            self.test_cases[ self.test ]['suite']      = self.suite
            self.test_cases[ self.test ]['fixture']    = self.suite
            self.test_cases[ self.test ]['key']        = self.test
            self.test_cases[ self.test ]['name']       = name
            self.test_cases[ self.test ]['stdout']     = []
            self.test_cases[ self.test ]['file']       = matches.group('file')
            self.test_cases[ self.test ]['line']       = matches.group('line')
            self.test_cases[ self.test ]['cpu_time']   = 0
            self.test_cases[ self.test ]['branch_dir'] = os.path.relpath( matches.group('file'), self.branch_root )
            self.test_cases[ self.test ]['total']      = 0
            self.test_cases[ self.test ]['assertions'] = 0
            self.test_cases[ self.test ]['passed']     = 0
            self.test_cases[ self.test ]['failed']     = 0
            self.notify.enter_test(self.test)
            return True
        return False

    def leaving_test_case( self, line ):
        test = self.test_cases[self.test]

        matches = re.match(
            r'Leaving test case "(?:[a-zA-Z0-9(){}\[\]:;&_<>\-, =]+)"'
             '(?:; testing time: (?P<testing_time>[a-zA-Z0-9.s ,+=()%/]+))?'
             '\. Test case (?P<status>passed|failed|skipped|aborted)\.'
             '(?: (?P<results>.*))?',
            line.strip() )

        if matches:

            self.__capture_times( matches.group('testing_time'), test )

            if matches.group('status'):
                test['status'] = matches.group('status')

            if matches.group('results'):
                self.store_test_results(test, matches.group('results'))

            self.test_case_names.append( test['key'] )
            self.notify.exit_test(test)
            return True
        else:
            test['stdout'].append( line )
            self.notify.message(line)
            return False


    def __capture_times( self, time, results ):
        if time:
            time = time.strip()

            test_time = re.match( '(?:(P<test_time>[0-9]+)(?P<units>ms|mks))', time )

            if test_time:
                multiplier = test_time.group('units') == 'ms' and 1000000 or 1000
                subseconds = int(test_time.group('test_time'))
                total_nanosecs = subseconds * multiplier
                results['cpu_time'] = total_nanosecs

            cpu_times = re.match(
                r'(?P<wall_time>[0-9.]+)s wall, '
                 '(?P<user_time>[0-9.]+)s user [+] '
                 '(?P<sys_time>[0-9.]+)s system [=] '
                 '(?P<cpu_time>[0-9.]+)s CPU [(](?P<wall_cpu_percent>[nN/aA0-9.]+)%?[)]',
                time )

            if cpu_times:
                results['wall_time'] = nanosecs_from_time( cpu_times.group('wall_time') )
                results['user_time'] = nanosecs_from_time( cpu_times.group('user_time') )
                results['sys_time']  = nanosecs_from_time( cpu_times.group('sys_time') )
                results['cpu_time']  = nanosecs_from_time( cpu_times.group('cpu_time') )

                self.test_suites[results['suite']]['wall_time'] += results['wall_time']
                self.test_suites[results['suite']]['user_time'] += results['user_time']
                self.test_suites[results['suite']]['sys_time']  += results['sys_time']

                results['wall_cpu_percent'] = cpu_times.group('wall_cpu_percent')

            self.test_suites[results['suite']]['cpu_time'] += results['cpu_time']

            store_durations( results )
        else:
            results['cpu_duration']  = duration_from_elapsed(0)

        ## For backward compatibility - remove later
        results['elapsed'] = results['cpu_time']


    def __call__( self, line ):

        self.log.write( line + '\n' )

        if self.state == State.waiting:
            if self.entered_test_suite( line ):
                self.state = State.test_suite
            elif self.leaving_test_suite( line ):
                self.state = State.waiting

        elif self.state == State.test_suite:
            if self.entered_test_case( line ):
                self.state = State.test_case
            elif self.entered_test_suite( line ):
                self.state = State.test_suite
            elif self.leaving_test_suite( line ):
                self.state = State.waiting

        elif self.state == State.test_case:
            if self.leaving_test_case( line ):
                self.state = State.test_suite

    def __exit__( self, type, value, traceback ):
        if self.log:
            self.log.close()

    def tests( self ):
        for name in self.test_case_names:
            yield name, self.test_cases[ name ]


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


class RunPatchedBoostTest:

    def __init__( self, expected ):
        self._expected = expected


    def __call__( self, target, source, env ):

        executable   = str( source[0].abspath )
        working_dir  = os.path.split( executable )[0]
        program_path = source[0].path
        notifier     = Notify(env)

        test_command = executable + " --boost.test.log_format=hrf --boost.test.log_level=test_suite --boost.test.report_level=no"

        print "RunBoostTest: [" + test_command + "]"

        try:
            return_code, tests = self.__run_test( program_path,
                                                  test_command,
                                                  working_dir,
                                                  env['branch_root'],
                                                  notifier )

            self.generate_bitten_test_report( report_from_program( program_path ), tests )

            if return_code < 0:
                self.__write_file_to_stderr( stderr_from_program( program_path ) )
                print >> sys.stderr, "Test was terminated by signal: ", -return_code
            elif return_code > 0:
                self.__write_file_to_stderr( stderr_from_program( program_path ) )
                print >> sys.stderr, "Test returned with error code: ", return_code
            elif notifier.master_suite['status'] != 'success':
                print >> sys.stderr, "Not all test suites passed. "
                return_code = 1
            else:
                return None

            return return_code

        except OSError, e:
            print >> sys.stderr, "Execution of [", test_command, "] failed with error: ", e
            return 1


    def __run_test( self, program_path, test_command, working_dir,branch_root, notifier ):
        process_stdout = ProcessStdout( stdout_from_program( program_path ), branch_root, notifier )
        process_stderr = ProcessStderr( stderr_from_program( program_path ), notifier )

        return_code = IncrementalSubProcess.Popen2( process_stdout,
                                                    process_stderr,
                                                    shlex.split( test_command ),
                                                    cwd=working_dir )

        return return_code, process_stdout.tests()


    def __write_file_to_stderr( self, file_name ):
        error_file = open( file_name, "r" )
        for line in error_file:
            print >> sys.stderr, line
        error_file.close()


    def generate_bitten_test_report( self, report_path, test_cases ):
        report = open( report_path, "w" )
        report.write( '<report category="test">\n' )

        for name, test in test_cases:

            report.write( '    <test>\n' )

            for key, value in test.iteritems():
                report.write( '        <%s>' % key )
                if key == 'stdout':
                    value = ( '<span class="line">' + cgi.escape(line) + '<br /></span>' for line in value )
                    value = '<![CDATA[' + "\n".join( value ) + ']]>'
                else:
                    value = cgi.escape( str( value ) )
                report.write( value )
                report.write( '</%s>\n' % key )

            report.write( '    </test>\n' )

        report.write( '</report>\n' )
        report.close()


def nanosecs_from_time( time_in_seconds ):
    seconds, subseconds = time_in_seconds.split('.')
    nanoseconds = subseconds
    decimal_places = len(subseconds)
    if decimal_places < 9:
        nanoseconds = int(subseconds) * 10**(9-decimal_places)
    return int(seconds) * 1000000000 + int(nanoseconds)


def duration_from_elapsed( total_nanosecs ):
    secs, remainder      = divmod( total_nanosecs, 1000000000 )
    millisecs, remainder = divmod( remainder, 1000000 )
    microsecs, nanosecs  = divmod( remainder, 1000 )
    hours, remainder     = divmod( secs, 3600 )
    minutes, secs        = divmod( remainder, 60 )

    duration = "%02d:%02d:%02d.%03d,%03d,%03d" % ( hours, minutes, secs, millisecs, microsecs, nanosecs )
    return duration
