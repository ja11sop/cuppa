#          Copyright Jamie Allsop 2024-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Helpers for running command with env.Command
#-------------------------------------------------------------------------------

import os
import shlex
import sys

from cuppa.output_processor import IncrementalSubProcess
from cuppa.log import logger
from cuppa.colourise import as_info, as_notice, as_error
from cuppa.utility.command_failure import select_failure_detail_lines


def _resolve_executable( args_list, working_dir ):
    """
    Resolve a relative argv[0] against ``working_dir`` when that file exists.

    Bare names like ``tool`` / ``tool.exe`` are not on PATH; POSIX also requires
    ``./tool`` for cwd binaries. Prefer an absolute path under ``working_dir``
    so callers can pass a basename when ``cwd`` is set.
    """
    if not working_dir or not args_list:
        return args_list
    exe = args_list[0]
    if os.path.isabs( exe ):
        return args_list
    candidate = os.path.normpath( os.path.join( working_dir, exe ) )
    if os.path.isfile( candidate ):
        return [ candidate ] + list( args_list[1:] )
    if not exe.lower().endswith( '.exe' ):
        candidate_exe = candidate + '.exe'
        if os.path.isfile( candidate_exe ):
            return [ candidate_exe ] + list( args_list[1:] )
    return args_list


class run:

    def __init__(
            self,
            command,
            working_dir=None,
            completion_file=None,
            terse_summary=None,
            terse_action=None,
    ):

        from SCons.Node import Node

        self._command = command
        self._working_dir = isinstance( working_dir, Node ) and working_dir.abspath or working_dir
        self._completion_file = completion_file
        self._terse_summary = terse_summary
        self._terse_action = terse_action


    def __call__( self, target, source, env ):

        from SCons.Script import Touch
        import cuppa.progress as progress

        captured_lines = []
        terse = bool( env.get( 'terse_output' ) )
        # Launch bookend + muted children only when the caller opts in (CMake,
        # b2, …). A plain ``run("cp …")`` stays on the ordinary Python-action
        # path so staging copies are not announced as delegated builds.
        delegated = terse and (
                self._terse_summary is not None or self._terse_action is not None
        )
        if delegated:
            action = self._terse_action or progress.spell_terse_action(
                    self._command, target, env,
            )
            summary = self._terse_summary if self._terse_summary is not None else self._command
            progress.write_terse_launch(
                    action, summary, env, command=self._command, target=target,
            )

        def process_stdout( line ):
            captured_lines.append( line )
            if delegated:
                progress.write_terse_muted_child( line, env )
            else:
                sys.stdout.write( line + '\n' )

        def process_stderr( line ):
            captured_lines.append( line )
            if delegated:
                progress.write_terse_muted_child( line, env )
            else:
                sys.stderr.write( line + '\n' )

        def log_failure_detail():
            detail = select_failure_detail_lines( captured_lines )
            if not detail:
                return
            logger.error(
                    "Failure detail ({} line(s); real errors often scroll away "
                    "under parallel warning floods):".format( len( detail ) )
            )
            for line in detail:
                logger.error( "  {}".format( as_error( line ) ) )

        try:
            logger.info( "Executing [{}] in directory [{}]...".format(
                    as_info( self._command ),
                    as_notice( self._working_dir )
            ) )
            args_list = _resolve_executable(
                    shlex.split( self._command ),
                    self._working_dir
            )
            return_code = IncrementalSubProcess.Popen2(
                    process_stdout,
                    process_stderr,
                    args_list,
                    cwd=self._working_dir,
                    scons_env=env,
                    # Popen2 reprints argv unless suppressed; under terse the
                    # launch bookend or the counted status line owns that role.
                    suppress_output=terse,
            )
            if return_code < 0:
                logger.error( "Execution of [{}] terminated by signal: {}".format( as_notice( self._command ), as_error( str(-return_code) ) ) )
                log_failure_detail()
                return return_code
            elif return_code > 0:
                logger.error( "Execution of [{}] returned with error code: {}".format( as_notice( self._command ), as_error( str(return_code) ) ) )
                log_failure_detail()
                return return_code
            if self._completion_file:
                env.Execute( Touch( self._completion_file ) )
            return 0

        except OSError as error:
            logger.error( "Execution of [{}] failed with error: {}".format( as_notice( self._command ), as_error( str(error) ) ) )
            return 1
