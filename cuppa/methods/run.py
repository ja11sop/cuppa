
#          Copyright Jamie Allsop 2019-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RunMethod
#-------------------------------------------------------------------------------

import cuppa.progress
from cuppa.method_helpers.run_process import runner, short_run_summary
from cuppa.utility.depends import with_depends


def _run_terse_action( env ):
    """Action word for ``env.Run`` on the durable terse line.

    ``Run`` is always a process helper (fixtures, docker, generic execute) —
    even under ``--test``. ``Test()`` / ``BuildTest()`` own the ``test`` word
    and ``[pass]`` / test-case children. Under ``--benchmark`` keep
    ``benchmark`` so Run of a benchmark binary stays distinct.
    """
    keys = set( env['variant_actions'].keys() )
    if keys & { 'benchmark', 'force_benchmark' }:
        return 'benchmark'
    return 'run'


def _run_terse_summary( command ):
    """Command / callable name for the terse file cell (not a ``.success`` stamp).

    Skip strings that still contain ``{…}`` format holes — ``command_args`` fill
    those at action time, and ``RunProcessAction`` re-labels then.
    """
    if command is None:
        return None
    if callable( command ):
        return short_run_summary( getattr( command, "__name__", "callable" ) )
    text = str( command )
    if "{" in text and "}" in text:
        return None
    return short_run_summary( text ) or None


class RunMethod(object):

    def __init__( self ):
        self._action_keys = [
            'run',
            'test',
            'benchmark',
            'force_run',
            'force_test',
            'force_benchmark'
        ]
        self._force_action_keys = [
            'force_run',
            'force_test',
            'force_benchmark'
        ]


    def __call__( self, env, source=None, target=None, final_dir=None, data=None, depends_on=None, command=None, command_args=None, expected_exit_code=None, working_dir=None, retry_count=None, inherit_process_env=None ):

        actions = env['variant_actions']

        if any( action_key in self._action_keys for action_key in actions.keys() ):

            if final_dir == None:
                final_dir = env['abs_final_dir']

            action, emitter = runner(
                final_dir,
                command=command,
                command_args=command_args,
                expected_exit_code=expected_exit_code,
                target=target,
                working_dir=working_dir,
                retry_count=retry_count,
                inherit_process_env=inherit_process_env,
            )

            env['BUILDERS']['RunBuilder'] = env.Builder( action=action, emitter=emitter )

            # depends_on preferred; data is a legacy alias. Both merge.
            sources = with_depends( source, depends_on, data )

            run_process = env.RunBuilder( [], sources )
            cuppa.progress.label_terse_action(
                    run_process,
                    _run_terse_action( env ),
                    summary=_run_terse_summary( command ),
            )
            if any( force_action in self._force_action_keys for force_action in env['variant_actions'].keys() ):
                run_process = env.AlwaysBuild( run_process )

            cuppa.progress.NotifyProgress.add( env, run_process )

            return run_process

        return []



    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Run", cls() )

