
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildTestMethod
#-------------------------------------------------------------------------------

from SCons.Script import Flatten


class BuildTestMethod:

    def __init__( self, default_test_runner=None ):
        self._default_runner = default_test_runner


    def __call__( self, env, target, source, final_dir=None, data=None, append_variant=None, runner=None, expected='passed', **kwargs ):

        nodes = []
        program = env.Build( target, source, final_dir=final_dir, append_variant=append_variant, **kwargs )
        nodes.append( program )
        if env['variant_actions'].has_key('test') or env['variant_actions'].has_key('cov'):
            if not runner:
                runner = self._default_runner

            test = env.Test( program, final_dir=final_dir, data=data, runner=runner, expected=expected )

            nodes.append( test )
            if 'cov' in env['variant_actions']:
                coverage = env.Coverage( program, source, final_dir=final_dir )
                nodes.append( coverage )

        return Flatten( nodes )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "BuildTest", cls( cuppa_env['default_runner'] ) )

        test_runners = set()
        for toolchain in cuppa_env['active_toolchains']:
            for test_runner in toolchain.test_runners():
                test_runners.add( test_runner )

        for test_runner in test_runners:
            cuppa_env.add_method( "Build{}Test".format( test_runner.title() ), cls( test_runner ) )
