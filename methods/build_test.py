
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildTestMethod
#-------------------------------------------------------------------------------


class BuildTestMethod:

    def __init__( self, default_test_runner=None ):
        self._default_test_runner = default_test_runner


    def __call__( self, env, target, source, final_dir=None, data=None, append_variant=None, test_runner=None, expected='success' ):
        program = env.Build( target, source, final_dir=final_dir, append_variant=append_variant )
        if env['variant_actions'].has_key('test') or env['variant_actions'].has_key('cov'):
            if not test_runner:
                test_runner = self._default_test_runner

            env.Test( program, final_dir=final_dir, data=data, test_runner=test_runner, expected=expected )
            if 'cov' in env['variant_actions']:
                env.Coverage( program, source, final_dir=final_dir )

        return program


    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls( args['env']['default_test_runner'] ), "BuildTest" )

        test_runners = set()
        for toolchain in args['env']['active_toolchains']:
            for test_runner in toolchain.test_runners():
                test_runners.add( test_runner )

        for test_runner in test_runners:
            args['env'].AddMethod( cls( test_runner ), "Build{}Test".format( test_runner.title() ) )
