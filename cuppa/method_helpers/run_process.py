
#          Copyright Jamie Allsop 2019-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunProcess
#-------------------------------------------------------------------------------

import os
import sys
import shlex
import re

from SCons.Errors import BuildError
from SCons.Script import Flatten

import cuppa.timer
import cuppa.progress
from cuppa.output_processor import IncrementalSubProcess
from cuppa.colourise import as_emphasised, as_highlighted, as_error, as_notice, is_error
from cuppa.log import logger
from cuppa.path import unique_short_filename
from cuppa.utility.dict_tools import args_from_dict


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


    def start( self ):
        self._timer = cuppa.timer.Timer()


    def stop( self, status='success', treat_error_as_warning=False ):
        meaning = status
        if treat_error_as_warning and is_error( status ):
            meaning = 'warning'
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

    invocation = {}

    def __init__( self, final_dir, target=None, command=None, **ignored_kwargs ):
        self._final_dir = final_dir
        self._targets = target and Flatten( target ) or None
        self._command = command


    @classmethod
    def next_invocation_id( cls, env ):
        variant_key = env['tool_variant_dir_offset']
        if not variant_key in cls.invocation:
            cls.invocation[variant_key] = 0
        next_id = cls.invocation[variant_key] + 1
        cls.invocation[variant_key] = next_id
        return next_id


    def _name_from_command( self, env ):
        invocation_id = self.next_invocation_id( env )
        name = re.sub(r'[^\w\s-]', '', self._command).strip().lower()
        return re.sub(r'[-\s]+', '-', name) + "_" + str(invocation_id)


    def _base_name( self, source, env ):
        if callable(self._command):
            name = self._command.__name__ + "_" + str(self.next_invocation_id( env ))
            return os.path.join( self._final_dir, name )
        elif self._command:
            path = os.path.join( self._final_dir, self._name_from_command( env ) )
            path, name = os.path.split( path )
            name = unique_short_filename( name )
            logger.trace( "Command = [{}], Unique Name = [{}]".format( as_notice(self._command), as_notice(name) ) )
            return os.path.join( path, name )
        else:
            program_file = str(source[0])
            if not program_file.startswith( self._final_dir ):
                program_file = os.path.split( program_file )[1]
            return program_file


    def __call__( self, target, source, env ):
        base_name = self._base_name( source, env )
        target = []
        if not callable(self._command):
            target.append( stdout_file_name_from( base_name ) )
            target.append( stderr_file_name_from( base_name ) )
        target.append( success_file_name_from( base_name ) )
        if self._targets:
            for t in self._targets:
                target.append( t )

        logger.trace( "targets = {}".format( str([ str(t) for t in target ]) ) )
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

    def __init__( self, final_dir, command=None, command_args=None, expected_exit_code=None, working_dir=None, retry_count=None, **ignored_kwargs ):
        self._final_dir = final_dir
        self._command = command
        self._command_args = command_args
        self._expected_exit_code = expected_exit_code
        self._working_dir = working_dir
        self._retry_count = retry_count and retry_count or 0


    def _run_command( self, source, suppress_output, program_path, command, working_dir, env, retry ):

        log_failure = retry and logger.warn or logger.error
        success = False

        monitor = Monitor( program_path, env )
        monitor.start()

        try:
            return_code = self._run(
                    suppress_output,
                    program_path,
                    command,
                    working_dir,
                    env
            )

            if return_code == self._expected_exit_code:
                monitor.stop( status='success' )
                success = True
            elif return_code < 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                log_failure( "Command was terminated by signal: {}".format( as_error(str(return_code) ) ) )
                monitor.stop( status='aborted', treat_error_as_warning=retry )
            elif return_code > 0:
                self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                log_failure( "Command returned with error code: {}".format( as_error(str(return_code) ) ) )
                monitor.stop( status='failed', treat_error_as_warning=retry )
            else:
                monitor.stop( status='success' )
                success = True

            if return_code == self._expected_exit_code:
                self._write_success_file( success_file_name_from( program_path ) )
            elif return_code:
                self._remove_success_file( success_file_name_from( program_path ) )
                if not retry:
                    if return_code < 0:
                        raise BuildError( node=source and source[0] or None, errstr="Command was terminated by signal: {}".format( str(-return_code) ) )
                    else:
                        raise BuildError( node=source and source[0] or None, errstr="Command returned with error code: {}".format( str(return_code) ) )
            else:
                self._write_success_file( success_file_name_from( program_path ) )

            return success

        except OSError as e:
            log_failure( "Execution of [{}] failed with error: {}".format( as_notice(command), as_notice(str(e)) ) )
            monitor.stop( status='failed', treat_error_as_warning=retry )
            if not retry:
                raise BuildError( e )


    def __call__( self, target, source, env ):

        command = None
        working_dir = None
        program_path = None

        if self._command and callable(self._command):
            program_path = os.path.splitext(os.path.splitext(str(target[0]))[0])[0]
            monitor = Monitor( program_path, env )
            monitor.start()

            command_args = args_from_dict( self._command_args )

            result = self._command( target, source, env, **command_args )

            if result==0 or result==None:
                self._write_success_file( success_file_name_from( program_path ) )
                monitor.stop( 'success' )
            else:
                self._remove_success_file( success_file_name_from( program_path ) )
                monitor.stop( 'failed' )
        else:

            if self._command:
                command = self._command
                if self._command_args:
                    command_args = args_from_dict( self._command_args )
                    command = command.format( **command_args )
                working_dir = self._working_dir and self._working_dir or self._final_dir
                program_path = os.path.splitext(os.path.splitext(str(target[0]))[0])[0]
            else:
                executable = str( source[0].abspath )
                working_dir, test = os.path.split( executable )
                if self._working_dir:
                    working_dir = self._working_dir
                program_path = source[0].path

                if cuppa.build_platform.name() == "Windows":
                    executable = '"' + executable + '"'

                command = executable
                if self._command:
                    command = self._command
                    working_dir = self._working_dir and self._working_dir or self._final_dir

            suppress_output = env['suppress_process_output']
            retry_count = self._retry_count

            while retry_count >= 0:

                retry = ( retry_count > 0 )

                success = self._run_command( source, suppress_output, program_path, command, working_dir, env, retry )

                if not success and retry:
                    logger.info( "Retrying [{}]...".format( as_notice(command) ) )
                else:
                    break

                retry_count = retry_count-1

        return None



    def _write_success_file( self, file_name ):
        with open( file_name, "w" ) as success_file:
            success_file.write( "success" )


    def _remove_success_file( self, file_name ):
        try:
            os.remove( file_name )
        except:
            pass


    def _run( self, suppress_output, program_path, command, working_dir, env ):
        process_stdout = ProcessStdout( not suppress_output, stdout_file_name_from( program_path ) )
        process_stderr = ProcessStderr( not suppress_output, stderr_file_name_from( program_path ) )

        return_code = IncrementalSubProcess.Popen2( process_stdout,
                                                    process_stderr,
                                                    shlex.split( command ),
                                                    cwd=working_dir,
                                                    scons_env=env)
        return return_code


    def __write_file_to_stderr( self, file_name ):
        error_file = open( file_name, "r" )
        for line in error_file:
            sys.stderr.write( line + '\n' )
        error_file.close()


def runner( final_dir, **kwargs ):
    return RunProcessAction( final_dir, **kwargs ), RunProcessEmitter( final_dir, **kwargs )


