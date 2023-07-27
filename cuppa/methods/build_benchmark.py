
#          Copyright Jamie Allsop, Jonny Weir 2023
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildBenchmarkMethod
#-------------------------------------------------------------------------------

from SCons.Script import Flatten


class BuildBenchmarkMethod:

    def __init__( self, default_benchmark_runner=None ):
        self._default_runner = default_benchmark_runner


    def __call__(
            self,
            env, target, source,
            final_dir=None,
            data=None,
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
        program = env.Build( target, source, final_dir=final_dir, append_variant=append_variant, **kwargs )
        nodes.append( program )

        actions = env['variant_actions']

        if 'benchmark' in actions.keys() or 'force_benchmark' in actions.keys():
            if not runner:
                runner = self._default_runner

            benchmark = env.Benchmark(
                program,
                final_dir=final_dir,
                data=data,
                runner=runner,
                expected=expected,
                command=command,
                expected_exit_code=expected_exit_code,
                working_dir=working_dir
            )

            nodes.append( benchmark )
            if 'cov' in actions:
                coverage = env.Coverage( program, source, final_dir=final_dir, exclude_dependencies=cov_exclude_dependencies, exclude_patterns=cov_exclude_patterns )
                nodes.append( coverage )

        return Flatten( nodes )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "BuildBenchmark", cls( cuppa_env['default_runner'] ) )

        benchmark_runners = set()
        for toolchain in cuppa_env['active_toolchains']:
            for benchmark_runner in toolchain.benchmark_runners():
                benchmark_runners.add( benchmark_runner )

        for benchmark_runner in benchmark_runners:
            cuppa_env.add_method( "Build{}Benchmark".format( benchmark_runner.title() ), cls( benchmark_runner ) )
