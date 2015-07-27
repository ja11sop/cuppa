
#          Copyright Jamie Allsop 2011-2015
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


    def __call__( self, env, source, final_dir=None, data=None, runner=None, expected='passed' ):
        if final_dir == None:
            final_dir = env['abs_final_dir']
        if not runner:
            runner = self._default_runner
        test_builder, test_emitter = env['toolchain'].test_runner( runner, final_dir, expected )

        env['BUILDERS']['TestBuilder'] = env.Builder( action=test_builder, emitter=test_emitter )

        sources = source
        if data:
            sources = Flatten( [ source, data ] )

        test = env.TestBuilder( [], sources )

        cuppa.progress.NotifyProgress.add( env, test )

        return test



    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls( env['default_runner'] ), "Test" )

        test_runners = set()
        for toolchain in env['active_toolchains']:
            for test_runner in toolchain.test_runners():
                test_runners.add( test_runner )

        for test_runner in test_runners:
            env.AddMethod( cls( test_runner ), "{}Test".format( test_runner.title() ) )


