
#          Copyright Jamie Allsop 2019-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunMethod
#-------------------------------------------------------------------------------

import cuppa.progress
from cuppa.method_helpers.run_process import runner

from SCons.Script import Flatten


class RunMethod(object):

    def __init__( self ):
        pass


    def __call__( self, env, source=None, target=None, final_dir=None, data=None, depends_on=None, command=None, format_args=None, expected_exit_code=None, working_dir=None ):

        actions = env['variant_actions']

        if actions.has_key('run') or actions.has_key('test') or actions.has_key('force_run') or actions.has_key('force_test'):

            if final_dir == None:
                final_dir = env['abs_final_dir']

            action, emitter = runner(
                final_dir,
                command=command,
                format_args=format_args,
                expected_exit_code=expected_exit_code,
                target=target,
                working_dir=working_dir
            )

            env['BUILDERS']['RunBuilder'] = env.Builder( action=action, emitter=emitter )

            sources = source

            # data should be deprecated in favour of depends_on
            if data:
                sources = Flatten( source and [ source, data ] or [data] )
            if depends_on:
                sources = Flatten( source and [ source, depends_on ] or [depends_on] )

            run_process = env.RunBuilder( [], sources )
            if env['variant_actions'].has_key('force_run') or env['variant_actions'].has_key('force_test'):
                run_process = env.AlwaysBuild( run_process )

            cuppa.progress.NotifyProgress.add( env, run_process )

            return run_process

        return []



    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Run", cls() )

