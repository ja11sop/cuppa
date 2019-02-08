
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
import re

from SCons.Errors import BuildError
from SCons.Script import Flatten

import cuppa.timer
import cuppa.progress
from cuppa.output_processor import IncrementalSubProcess
from cuppa.colourise import as_emphasised, as_highlighted, as_colour, as_error, as_notice
from cuppa.log import logger
from cuppa.path import unique_short_filename


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


    def stop( self, status='success' ):
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

    def __init__( self, final_dir, command=None, format_args=None, expected_exit_code=None, working_dir=None, **ignored_kwargs ):
        self._final_dir = final_dir
        self._command = command
        self._format_args = format_args
        self._expected_exit_code = expected_exit_code
        self._working_dir = working_dir


    def __call__( self, target, source, env ):

        command = None
        working_dir = None
        program_path = None

        if self._command and callable(self._command):
            program_path = os.path.splitext(os.path.splitext(str(target[0]))[0])[0]
            monitor = Monitor( program_path, env )
            monitor.start()

            result = self._command( target, source, env )

            if result or result == None:
                self._write_success_file( success_file_name_from( program_path ) )
                monitor.stop( 'success' )
            else:
                self._remove_success_file( success_file_name_from( program_path ) )
                monitor.stop( 'failed' )
        else:

            if self._command:
                command = self._command
                if self._format_args:
                    format_args = {}
                    for key, value in self._format_args.iteritems():
                        format_args[key] = callable(value) and value() or value
                    command = command.format( **format_args )
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

                test_command = executable
                if self._command:
                    command = self._command
                    working_dir = self._working_dir and self._working_dir or self._final_dir

            monitor = Monitor( program_path, env )

            monitor.start()

            suppress_output = env['suppress_process_output']

            try:
                return_code = self._run(
                        suppress_output,
                        program_path,
                        command,
                        working_dir,
                        env
                )

                if return_code == self._expected_exit_code:
                    monitor.stop( 'success' )
                elif return_code < 0:
                    self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                    logger.error( "Command was terminated by signal: {}".format( as_error(str(return_code) ) ) )
                    monitor.stop( 'aborted' )
                elif return_code > 0:
                    self.__write_file_to_stderr( stderr_file_name_from( program_path ) )
                    logger.error( "Command returned with error code: {}".format( as_error(str(return_code) ) ) )
                    monitor.stop( 'failed' )
                else:
                    monitor.stop( 'success' )

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
            print >> sys.stderr, line
        error_file.close()


def runner( final_dir, **kwargs ):
    return RunProcessAction( final_dir, **kwargs ), RunProcessEmitter( final_dir, **kwargs )


