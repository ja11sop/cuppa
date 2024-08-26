
#          Copyright Jamie Allsop 2011-2024
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


    def __call__(
            self,
            env, target, source,
            final_dir=None,
            data=None,
            depends_on=None,
            append_variant=None,
            runner=None,
            expected='passed',
            command=None,
            expected_exit_code=None,
            cov_include_patterns=None,
            cov_exclude_dependencies=False,
            cov_exclude_patterns=None,
            working_dir=None,
            **kwargs
    ):

        nodes = []
        program = env.Build( target, source, final_dir=final_dir, append_variant=append_variant, depends_on=depends_on, **kwargs )
        nodes.append( program )

        actions = env['variant_actions']

        if 'test' in actions.keys() or 'force_test' in actions.keys():
            if not runner:
                runner = self._default_runner

            test = env.Test(
                program,
                final_dir=final_dir,
                data=data,
                runner=runner,
                expected=expected,
                command=command,
                expected_exit_code=expected_exit_code,
                working_dir=working_dir
            )

            nodes.append( test )
            if 'cov' in actions:
                coverage = env.Coverage( program, source, final_dir=final_dir, exclude_dependencies=cov_exclude_dependencies, exclude_patterns=cov_exclude_patterns )
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
