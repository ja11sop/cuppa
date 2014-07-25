
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   TestMethod
#-------------------------------------------------------------------------------

import sconscript_progress
from SCons.Script import Flatten

class TestMethod(object):

    def __init__( self, toolchain, default_test_runner=None ):
        self._toolchain = toolchain
        self._default_test_runner = default_test_runner


    def __call__( self, env, source, final_dir=None, data=None, test_runner=None, expected='success' ):
        if final_dir == None:
            final_dir = env['final_dir']
        if not test_runner:
            test_runner = self._default_test_runner
        test_builder, test_emitter = self._toolchain.test_runner( test_runner, final_dir, expected )

        env['BUILDERS']['TestBuilder'] = env.Builder( action=test_builder, emitter=test_emitter )

        sources = source
        if data:
            sources = Flatten( [ source, data ] )

        test = env.TestBuilder( [], sources )
        sconscript_progress.SconscriptProgress.add( env, test )

        return test



    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls( args['env']['toolchain'], args['env']['default_test_runner'] ), "Test" )
        for test_runner in args['env']['toolchain'].test_runners():
            args['env'].AddMethod( cls( args['env']['toolchain'], test_runner ), "{}Test".format( test_runner.title() ) )


