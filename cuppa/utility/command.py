
#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Helpers for running command with env.Command
#-------------------------------------------------------------------------------

import shlex
import sys

from cuppa.output_processor import IncrementalSubProcess
from cuppa.log import logger
from cuppa.colourise import as_info, as_notice, as_error


class run:

    def __init__( self, command, working_dir=None, completion_file=None ):

        from SCons.Node import Node

        self._command = command
        self._working_dir = isinstance( working_dir, Node ) and working_dir.abspath or working_dir
        self._completion_file = completion_file


    def __call__( self, target, source, env ):

        from SCons.Script import Touch

        def process_stdout( line ):
            sys.stdout.write( line + '\n' )

        def process_stderr( line ):
            sys.stderr.write( line + '\n' )

        try:
            logger.info( "Executing [{}] in directory [{}]...".format(
                    as_info( self._command ),
                    as_notice( self._working_dir )
            ) )
            return_code = IncrementalSubProcess.Popen2(
                    process_stdout,
                    process_stderr,
                    shlex.split( self._command ),
                    cwd=self._working_dir
            )
            if return_code < 0:
                logger.error( "Execution of [{}] terminated by signal: {}".format( as_notice( self._command ), as_error( str(-return_code) ) ) )
            elif return_code > 0:
                logger.error( "Execution of [{}] returned with error code: {}".format( as_notice( self._command ), as_error( str(return_code) ) ) )
            else:
                if self._completion_file:
                    env.Execute( Touch( self._completion_file ) )

        except OSError as error:
            logger.error( "Execution of [{}] failed with error: {}".format( as_notice( self._command ), as_error( str(error) ) ) )
