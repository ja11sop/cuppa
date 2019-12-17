
#          Copyright Jamie Allsop 2011-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   TestMethod
#-------------------------------------------------------------------------------

import cuppa.progress

from SCons.Script import Flatten


class TestMethod(object):

    def __init__( self, default_test_runner=None ):
        self._default_runner = default_test_runner


    def __call__( self, env, source, target=None, final_dir=None, data=None, runner=None, expected='passed', command=None, expected_exit_code=None, working_dir=None ):

        actions = env['variant_actions']

        if 'test' in actions.keys() or 'force_test' in actions.keys():
            if not runner:
                runner = self._default_runner

            if final_dir == None:
                final_dir = env['abs_final_dir']

            test_builder, test_emitter = env['toolchain'].test_runner(
                runner,
                final_dir,
                expected,
                command=command,
                expected_exit_code=expected_exit_code,
                target=target,
                working_dir=working_dir
            )

            env['BUILDERS']['TestBuilder'] = env.Builder( action=test_builder, emitter=test_emitter )

            sources = source
            if data:
                sources = Flatten( [ source, data ] )

            test = env.TestBuilder( [], sources )
            if 'force_test' in env['variant_actions'].keys():
                test = env.AlwaysBuild( test )

            cuppa.progress.NotifyProgress.add( env, test )

            return test

        return []



    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Test", cls( cuppa_env['default_runner'] ) )

        test_runners = set()
        for toolchain in cuppa_env['active_toolchains']:
            for test_runner in toolchain.test_runners():
                test_runners.add( test_runner )

        for test_runner in test_runners:
            cuppa_env.add_method( "{}Test".format( test_runner.title() ), cls( test_runner ) )


