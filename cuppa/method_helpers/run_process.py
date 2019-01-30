
#          Copyright Jamie Allsop 2019-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunProcess
#-------------------------------------------------------------------------------

import os
import sys
import shlex

from SCons.Errors import BuildError
from SCons.Script import Flatten

import cuppa.timer
import cuppa.progress
from cuppa.output_processor import IncrementalSubProcess
from cuppa.colourise import as_emphasised, as_highlighted, as_colour, as_error, as_notice
from cuppa.log import logger


class Monitor(object):

    def __init__( self, name, scons_env ):
        self._name = name
        self._scons_env = scons_env
        self._timer = None

        sys.stdout.write('\n')
        sys.stdout.write(
            as_emphasised( "Running Process [{}]".format( name ) )
        )
        sys.stdout.write('\n')
        self._cpu_times = cuppa.timer.CpuTimes( 0, 0, 0, 0 )


    def run( self, process ):
        self._timer = cuppa.timer.Timer()


    def stop( self, test, status='success' ):
        meaning = status
        if status == 'success':
            status = 'done'
        sys.stdout.write( as_highlighted( meaning, " = {} = ".format( status ) ) )
        if self._timer:
            self._timer.stop()
            self._cpu_times = self._timer.elapsed()
            cuppa.timer.write_time( self._cpu_times, True )
            sys.stdout.write('\n\n')


    def message( self, line ):
        sys.stdout.write(
            line + "\n"
        )


def stdout_file_name_from( program_file ):
    return program_file + '.stdout.log'


def stderr_file_name_from( program_file ):
    return program_file + '.stderr.log'


def success_file_name_from( program_file ):
    return program_file + '.success'


class RunProcessEmitter(object):

    def __init__( self, final_dir, target=None, **ignored_kwargs ):
        self._final_dir = final_dir
        self._targets = target and Flatten( target ) or None


    def __call__( self, target, source, env ):
        program_file = str(source[0])
        if not program_file.startswith( self._final_dir ):
            program_file = os.path.split( program_file )[1]
        target = []
        target.append( stdout_file_name_from( program_file ) )
        target.append( stderr_file_name_from( program_file ) )
        target.append( success_file_name_from( program_file ) )
        if self._targets:
            for t in self._targets:
                target.append( t )
        return target, source


class ProcessStdout(object):

    def __init__( self, show_output, log ):
        self._show_output = show_output
        self.log = open( log, "w" )


    def __call__( self, line ):
        self.log.write( line + '\n' )
        if self._show_output:
            sys.stdout.write( line + '\n' )


    def __exit__( self, type, value, traceback ):
        if self.log:
            self.log.close()


class ProcessStderr(object):

    def __init__( self, show_output, log ):
        self._show_output = show_output
        self.log = open( log, "w" )


    def __call__( self, line ):
        self.log.write( line + '\n' )
        if self._show_output:
            sys.stderr.write( line + '\n' )


    def __exit__( self, type, value, traceback ):
        if self.log:
            self.log.close()


class RunProcessAction(object):

    def __init__( self, final_dir, command=None, expected_exit_code=None, working_dir=None, **ignored_kwargs ):
        self._final_dir = final_dir
        self._command = command
        self._expected_exit_code = expected_exit_code
        self._working_dir = working_dir


    def __call__( self, target, source, env ):

        executable = str( source[0].abspath )
        working_dir, test = os.path.split( executable )
        if self._working_dir:
            working_dir = self._working_dir
        program_path = source[0].path
        suite = env['build_dir']

        if cuppa.build_platform.name() == "Windows":
            executable = '"' + executable + '"'

        test_command = executable
        if self._command:
            command = self._command
            working_dir = self._working_dir and self._working_dir or self._final_dir
            process = os.path.relpath( executable, working_dir )

        monitor = Monitor( program_path, env )

        monitor.run( process )

        show_output = env['show_process_output']

        try:
            return_code = self._run(
                    show_output,
                    program_path,
                    command,
                    working_dir,
                    env
            )

            if return_code == self._expected_exit_code:
                monitor.stop( process, 'success' )
            elif return_code < 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                logger.error( "Command was terminated by signal: {}".format( as_error(str(return_code) ) ) )
                monitor.stop( process, 'aborted' )
            elif return_code > 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                logger.error( "Command returned with error code: {}".format( as_error(str(return_code) ) ) )
                monitor.stop( process, 'failed' )
            else:
                monitor.stop( process, 'success' )

            if return_code == self._expected_exit_code:
                self._write_success_file( success_file_name_from( program_path ) )
            elif return_code:
                self._remove_success_file( success_file_name_from( program_path ) )
                if return_code < 0:
                    raise BuildError( node=source[0], errstr="Command was terminated by signal: {}".format( str(-return_code) ) )
                else:
                    raise BuildError( node=source[0], errstr="Command returned with error code: {}".format( str(return_code) ) )
            else:
                self._write_success_file( success_file_name_from( program_path ) )

            return None

        except OSError, e:
            logger.error( "Execution of [{}] failed with error: {}".format( as_notice(test_command), as_notice(str(e)) ) )
            raise BuildError( e )


    def _write_success_file( self, file_name ):
        with open( file_name, "w" ) as success_file:
            success_file.write( "success" )


    def _remove_success_file( self, file_name ):
        try:
            os.remove( file_name )
        except:
            pass


    def _run( self, show_output, program_path, command, working_dir, env ):
        process_stdout = ProcessStdout( show_output, stdout_file_name_from( program_path ) )
        process_stderr = ProcessStderr( show_output, stderr_file_name_from( program_path ) )

        return_code = IncrementalSubProcess.Popen2( process_stdout,
                                                    process_stderr,
                                                    shlex.split( command ),
                                                    cwd=working_dir,
                                                    scons_env=env)
        return return_code


    def __write_file_to_stderr( self, file_name ):
        error_file = open( file_name, "r" )
        for line in error_file:
            print >> sys.stderr, line
        error_file.close()


def runner( final_dir, **kwargs ):
    return RunProcessAction( final_dir, **kwargs ), RunProcessEmitter( final_dir, **kwargs )


