
#          Copyright Jamie Allsop 2011-2015
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
import colorama



def command_available( command ):
    try:
        with open(os.devnull) as devnull:
            subprocess.Popen( shlex.split( command ), stdout=devnull, stderr=devnull ).communicate()
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            return False
    return True



class AutoFlushFile:

    def __init__( self, f ):
        self.f = f

    def flush( self ):
        self.f.flush()

    def write( self, x ):
        self.f.write(x)
        self.f.flush()



class LineConsumer:

    def __init__( self, call_readline, processor=None ):
        self.call_readline = call_readline
        self.processor     = processor


    def __call__( self ):
        for line in iter( self.call_readline, "" ):
            line = line.rstrip()
            if line:
                if self.processor:
                    line = self.processor( line )
                    if line:
                        print line
                else:
                    print line


class IncrementalSubProcess:

    @classmethod
    def Popen2( cls, stdout_processor, stderr_processor, args_list, **kwargs ):

        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE

        sys.stdout = AutoFlushFile( colorama.initialise.wrapped_stdout )
        sys.stderr = AutoFlushFile( colorama.initialise.wrapped_stderr )

        process = subprocess.Popen(
            args_list,
            **kwargs
        )

        stderr_consumer = LineConsumer( process.stderr.readline, stderr_processor )
        stdout_consumer = LineConsumer( process.stdout.readline, stdout_processor )

        stderr_thread = threading.Thread( target=stderr_consumer )
        stderr_thread.start()
        stdout_consumer();
        stderr_thread.join()

        process.wait()
        return process.returncode


    @classmethod
    def Popen( cls, processor, args_list, **kwargs ):
        return cls.Popen2( processor, processor, args_list, **kwargs )


class Processor:

    def __init__( self, scons_env ):
        self.scons_env = scons_env


    @classmethod
    def install( cls, env ):
        output_processor = cls( env )
        env['SPAWN'] = output_processor.spawn


    def spawn( self, sh, escape, cmd, args, env ):

        processor = SpawnedProcessor( self.scons_env )

        returncode = IncrementalSubProcess.Popen(
            processor,
            [ arg.strip('"') for arg in args ],
            env=env
        )

        summary = processor.summary( returncode )

        if summary:
            print summary

        return returncode



class SpawnedProcessor(object):

    def __init__( self, scons_env ):
        self._processor = ToolchainProcessor(
                scons_env['colouriser'],
                scons_env['toolchain'],
                scons_env['minimal_output'],
                scons_env['ignore_duplicates'] )

    def __call__( self, line ):
        return self._processor( line )

    def summary( self, returncode ):
        return self._processor.summary( returncode )



class ToolchainProcessor:

    def __init__( self, colouriser, toolchain, minimal_output, ignore_duplicates ):
        self.toolchain              = toolchain
        self.colouriser             = colouriser
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

                element = self.colouriser.colour( meaning, element )

                if match in highlights:
                    element = self.colouriser.emphasise( element )

                message += element

            message = self.filtered_line( message + "\n", meaning )

            if meaning == 'error':
                if message:
                    message = self.colouriser.highlight( meaning, " = Error " + str(error_id) + " = ") +  "\n" + message
                else:
                    self.errors -= 1

            elif meaning == 'warning':
                if message:
                    message = self.colouriser.highlight( meaning, " = Warning " + str(warning_id) + " = ") + "\n" + message
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
            Summary += self.colouriser.highlight( 'summary', " === Process Terminated with status " + str(returncode)  + " (Elapsed " + str(elapsed_time) + "s)" + " === ") + "\n"
        if self.errors:
            Summary += self.colouriser.highlight( 'error',   " === Errors "   + str(self.errors)   + " === ")
        if self.warnings:
            Summary += self.colouriser.highlight( 'warning', " === Warnings " + str(self.warnings) + " === ")
        return Summary
