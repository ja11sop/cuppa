#          Copyright Jamie Allsop 2022-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunAndRedirectToFileMethod
#-------------------------------------------------------------------------------

# Python imports
import os.path
import shlex
import subprocess

# cuppa imports
import cuppa.progress
from cuppa.log import logger
from cuppa.colourise import as_notice


class RunAndRedirectToFileAction(object):

    def __init__( self, command_args=None ):
        self._command_args = command_args and command_args or ""

    def __call__( self, target, source, env ):

        for s, t in zip( source, target ):
            program  = str(s)
            output_file = str(t)

            command = "{} {}".format( program, self._command_args )

            logger.debug( "Running command [{}] and redirecting output to [{}]".format( as_notice(command), as_notice(output_file) ) )

            with open( output_file, "wb" ) as output:
                subprocess.call( shlex.split( command ), stdout=output )
        return None


class RunAndRedirectToFileEmitter(object):

    def __init__( self, output_dir, extension=None ):
        self._output_dir = output_dir
        self._extension = extension and extension or ".out"

    def __call__( self, target, source, env ):
        last_source = len(source)
        s_idx = len(target)
        while s_idx < last_source:
            path = os.path.join( self._output_dir, os.path.split( str(source[s_idx]) )[1] )
            t = os.path.splitext(path)[0] + self._extension
            target.append(t)
            s_idx = s_idx+1
        return target, source


class RunAndRedirectToFileMethod(object):

    def __call__( self, env, target, source, final_dir=None, command_args=None, extension=None ):
        if final_dir == None:
            final_dir = env['abs_final_dir']

        env.AppendUnique( BUILDERS = {
            'RunAndRedirectToFile' : env.Builder(
                action  = RunAndRedirectToFileAction( command_args=command_args ),
                emitter = RunAndRedirectToFileEmitter( final_dir, extension=extension ) )
        } )

        output = env.RunAndRedirectToFile( target, source )
        cuppa.progress.NotifyProgress.add( env, output )
        return output


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "RunAndRedirectToFile", cls() )

