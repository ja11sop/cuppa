
#          Copyright Jamie Allsop 2011-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Output Processor
#-------------------------------------------------------------------------------

import subprocess
import sys
import os
import re
import time
import threading
import shlex

import platform
import logging

import cuppa.timer
from cuppa.colourise import as_colour, as_emphasised, as_highlighted, as_notice
from cuppa.log import logger
from cuppa.utility.python2to3 import as_str, errno, Queue


def command_available( command ):
    try:
        with open(os.devnull) as devnull:
            subprocess.Popen( shlex.split( command ), stdout=devnull, stderr=devnull ).communicate()
    except OSError as e:
        if e.errno == errno.ENOENT:
            return False
    return True


class LineConsumer:

    def __init__( self, call_readline, processor=None ):
        self.call_readline = call_readline
        self.processor = processor


    def __call__( self ):
        try:
            for line in iter( self.call_readline, "" ):
                line = as_str( line.rstrip() )
                if line:
                    if self.processor:
                        line = self.processor( line )
                        if line:
                            print( line )
                    else:
                        print( line )
        except UnicodeDecodeError as error:
            print( "WARNING: Ignoring unicode error {}".format( error ) )



class IncrementalSubProcess:

    @classmethod
    def Popen2( cls, stdout_processor, stderr_processor, args_list, **kwargs ):

        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE

        timing_enabled = logger.isEnabledFor( logging.DEBUG )

        suppress_output = False
        if 'suppress_output' in kwargs:
            suppress_output = kwargs['suppress_output']
            del kwargs['suppress_output']

        use_shell = False
        if 'scons_env' in kwargs:
            use_shell = kwargs['scons_env'].get_option( 'use-shell' )
            del kwargs['scons_env']

        try:
            process = None
            stderr_thread = None

            timer = timing_enabled and cuppa.timer.Timer() or None
            if timer:
                logger.debug( "Command [{}] - Running...".format( as_notice(str(timer.timer_id())) ) )

            close_fds = platform.system() == "Windows" and False or True

            if not suppress_output:
                sys.stdout.write( " ".join(args_list) + "\n" )

            process = subprocess.Popen(
                use_shell and " ".join(args_list) or args_list,
                **dict( kwargs, close_fds=close_fds, shell=use_shell, universal_newlines=True )
            )

            stderr_consumer = LineConsumer( process.stderr.readline, stderr_processor )
            stdout_consumer = LineConsumer( process.stdout.readline, stdout_processor )

            stderr_thread = threading.Thread( target=stderr_consumer )
            stderr_thread.start()
            stdout_consumer();
            stderr_thread.join()

            process.wait()

            if timer:
                timer.stop()
                logger.debug( "Command [{}] - Elapsed {}".format( as_notice(str(timer.timer_id())), cuppa.timer.as_string( timer.elapsed() ) ) )

            return process.returncode

        except Exception as e:
            if timer:
                timer.stop()
                logger.debug( "Command [{}] - Elapsed {}".format( as_notice(str(timer.timer_id())), cuppa.timer.as_string( timer.elapsed() ) ) )
            logger.error( "IncrementalSubProcess.Popen2() failed with error [{}]".format( str(e) ) )
            if process:
                logger.info( "Killing existing POpen object" )
                process.kill()
            if stderr_thread:
                logger.info( "Joining any running threads" )
                stderr_thread.join()
            raise e


    @classmethod
    def Popen( cls, processor, args_list, **kwargs ):
        return cls.Popen2( processor, processor, args_list, **kwargs )



class PSpawn(object):

    def __init__( self, pspawn, sh, escape, cmd, args, env, stdout, stderr ):
        self._pspawn = pspawn
        self._sh = sh
        self._escape = escape
        self._cmd = cmd
        self._args = args
        self._env = env
        self._stdout = stdout
        self._stderr = stderr
        self._exception = None

    def __call__( self ):
        try:
            self._returncode = self._pspawn( self._sh, self._escape, self._cmd, self._args, self._env, self._stdout, self._stderr )
        except BaseException:
            self._exception = sys.exc_info()

    def returncode( self ):
        if self._exception != None:
            logger.error("pspawn terminated with exception [{}]".format( str(self._exception) ) )
            raise self._exception
        return self._returncode



class Stream(object):

    def __init__( self, processor, name ):
        self._queue = Queue.Queue()
        self._processor = processor
        self._name = name

    def flush( self ):
        pass

    def write( self, text ):
        logger.trace( "Stream _queue.put [{}]".format( self._name ) )
        self._queue.put( text )

    def read( self, block ):
        try:
            logger.trace( "Stream _queue.get [{}]".format( self._name ) )
            text = self._queue.get( block )
            if text:
                for line in text.splitlines():
                    if self._processor:
                        line = self._processor( line )
                        if line:
                            print( line )
                    else:
                        print( line )
            self._queue.task_done()
        except Queue.Empty:
            logger.trace( "Stream Queue.Empty raised [{}]".format( self._name ) )

    def join( self ):
        if self._queue.empty():
            logger.trace( "Stream _queue.empty() - flush with None [{}]".format( self._name ) )
            self._queue.put( None )
        self._queue.join()



class Reader(object):

    def __init__( self, stream, finished ):
        self._stream = stream
        self._finished = finished

    def __call__( self ):
        while not self._finished.is_set():
            self._stream.read(True)
        self._stream.read(False)



class Processor:

    def __init__( self, scons_env ):
        self.scons_env = scons_env


    @classmethod
    def install( cls, env ):
        global _pspawn
        _pspawn = env['PSPAWN']
        output_processor = cls( env )
        if platform.system() == "Windows":
            env['SPAWN'] = output_processor.windows_spawn
        else:
            env['SPAWN'] = output_processor.posix_spawn


    def posix_spawn( self, sh, escape, cmd, args, env ):

        processor = SpawnedProcessor( self.scons_env )

        returncode = IncrementalSubProcess.Popen(
            processor,
            [ arg.strip('"') for arg in args ],
            env=env,
            suppress_output=True,
        )

        summary = processor.summary( returncode )

        if summary:
            print( summary )

        return returncode


    def windows_spawn( self, sh, escape, cmd, args, env ):

        processor = SpawnedProcessor( self.scons_env )

        stdout = Stream( processor, "stdout" )
        stderr = Stream( processor, "stderr" )

        pspawn = PSpawn( _pspawn, sh, escape, cmd, args, env, stdout, stderr )

        pspawn_thread = threading.Thread( target=pspawn )

        finished = threading.Event()
        pspawn_thread.start()

        stdout_thread = threading.Thread( target = Reader( stdout, finished ) )
        stdout_thread.start()

        stderr_thread = threading.Thread( target = Reader( stderr, finished ) )
        stderr_thread.start()

        pspawn_thread.join()
        logger.trace( "Processor - PSPAWN joined" )
        finished.set()

        stdout.join()
        logger.trace( "Processor - STDOUT stream joined" )
        stdout_thread.join()
        logger.trace( "Processor - STDOUT thread joined" )

        stderr.join()
        logger.trace( "Processor - STDERR stream joined" )
        stderr_thread.join()
        logger.trace( "Processor - STDERR thread joined" )

        returncode = pspawn.returncode()

        summary = processor.summary( returncode )

        if summary:
            print( summary )

        return returncode



class SpawnedProcessor(object):

    def __init__( self, scons_env ):
        self._processor = ToolchainProcessor(
                scons_env['toolchain'],
                scons_env['minimal_output'],
                scons_env['ignore_duplicates'] )

    def __call__( self, line ):
        return self._processor( line )

    def summary( self, returncode ):
        return self._processor.summary( returncode )



class ToolchainProcessor:

    def __init__( self, toolchain, minimal_output, ignore_duplicates ):
        self.toolchain              = toolchain
        self.minimal_output         = minimal_output
        self.ignore_duplicates      = ignore_duplicates
        self.errors                 = 0
        self.warnings               = 0
        self.start_time             = time.time()
        self.error_messages         = {}
        self.warning_messages       = {}
        self.ignore_current_message = False


    def filtered_duplicate( self, line, existing_messages ):
        if self.ignore_duplicates and line in existing_messages:
            existing_messages[line] +=1
            self.ignore_current_message = True
            return None
        else:
            self.ignore_current_message = False
            existing_messages[line] = 1
            return line


    def filtered_line( self, line=None, meaning=None ):
        if meaning == "error":
            return self.filtered_duplicate( line, self.error_messages )

        if meaning == "warning":
            return self.filtered_duplicate( line, self.warning_messages )

        if self.minimal_output or self.ignore_current_message:
            return None
        else:
            return line


    def __call__( self, line ):

        ( matches, interpretor, error_id, warning_id ) = self.interpret( line )

        if matches:
            highlights  = interpretor['highlight']
            display     = interpretor['display']
            meaning     = interpretor['meaning']
            file        = interpretor['file']
            message     = ''

            for match in display:

                element = matches.group( match )

                if match == file and ( meaning == 'error' or meaning == 'warning' ):
                    element = self.normalise_path( element )

                element = as_colour( meaning, element )

                if match in highlights:
                    element = as_emphasised( element )

                message += element

            message = self.filtered_line( message + "\n", meaning )

            if meaning == 'error':
                if message:
                    message = as_highlighted( meaning, " = Error " + str(error_id) + " = ") +  "\n" + message
                else:
                    self.errors -= 1

            elif meaning == 'warning':
                if message:
                    message = as_highlighted( meaning, " = Warning " + str(warning_id) + " = ") + "\n" + message
                else:
                    self.warnings -= 1

            return message
        return self.filtered_line( line )


    def normalise_path( self, file_path ):

        normalised_path = file_path
        if os.path.exists( file_path ):
            normalised_path = os.path.relpath( os.path.realpath( file_path ) )
#            if normalised_path[0] != '.' and normalised_path[0] != os.path.sep:
#                normalised_path = '.' + os.path.sep + normalised_path
#        return os.path.abspath( normalised_path )
        return normalised_path


    def interpret( self, line ):
        Interpretors = self.toolchain.output_interpretors()

        for interpretor in Interpretors:
            Regex = interpretor['regex']
            Matches = re.match( Regex, line )

            if Matches:
                error_id = 0
                warning_id = 0

                if interpretor['meaning'] == 'error':
                    self.errors += 1
                    error_id = self.errors

                elif interpretor['meaning'] == 'warning':
                    self.warnings += 1
                    warning_id = self.warnings

                return ( Matches, interpretor, error_id, warning_id, )

        return ( None, None, None, None, )


    def summary( self, returncode ):

        elapsed_time = time.time() - self.start_time
        Summary = ''
        if returncode:
            Summary += as_highlighted( 'summary', " === Process Terminated with status " + str(returncode)  + " (Elapsed " + str(elapsed_time) + "s)" + " === ") + "\n"
        if self.errors:
            Summary += as_highlighted( 'error',   " === Errors "   + str(self.errors)   + " === ")
        if self.warnings:
            Summary += as_highlighted( 'warning', " === Warnings " + str(self.warnings) + " === ")
        return Summary
