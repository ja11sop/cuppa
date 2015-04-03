
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildTestMethod
#-------------------------------------------------------------------------------


class BuildTestMethod:

    def __init__( self, default_test_runner=None ):
        self._default_runner = default_test_runner


    def __call__( self, env, target, source, final_dir=None, data=None, append_variant=None, runner=None, expected='success', **kwargs ):

        program = env.Build( target, source, final_dir=final_dir, append_variant=append_variant, **kwargs )
        if env['variant_actions'].has_key('test') or env['variant_actions'].has_key('cov'):
            if not runner:
                runner = self._default_runner

            env.Test( program, final_dir=final_dir, data=data, runner=runner, expected=expected )
            if 'cov' in env['variant_actions']:
                env.Coverage( program, source, final_dir=final_dir )

        return program


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls( env['default_runner'] ), "BuildTest" )

        test_runners = set()
        for toolchain in env['active_toolchains']:
            for test_runner in toolchain.test_runners():
                test_runners.add( test_runner )

        for test_runner in test_runners:
            env.AddMethod( cls( test_runner ), "Build{}Test".format( test_runner.title() ) )
