
#          Copyright Jamie Allsop, Jonny Weir 2023
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BenchmarkMethod
#-------------------------------------------------------------------------------

import cuppa.progress

from SCons.Script import Flatten


class BenchmarkMethod(object):

    def __init__( self, default_benchmark_runner=None ):
        self._default_runner = default_benchmark_runner


    def __call__( self, env, source, target=None, final_dir=None, data=None, runner=None, expected='passed', command=None, expected_exit_code=None, working_dir=None ):

        actions = env['variant_actions']

        if 'benchmark' in actions.keys() or 'force_benchmark' in actions.keys():
            if not runner:
                runner = self._default_runner

            if final_dir == None:
                final_dir = env['abs_final_dir']

            benchmark_builder, benchmark_emitter = env['toolchain'].benchmark_runner(
                runner,
                final_dir,
                expected,
                command=command,
                expected_exit_code=expected_exit_code,
                target=target,
                working_dir=working_dir
            )

            env['BUILDERS']['BenchmarkBuilder'] = env.Builder( action=benchmark_builder, emitter=benchmark_emitter )

            sources = source
            if data:
                sources = Flatten( [ source, data ] )

            benchmark = env.BenchmarkBuilder( [], sources )
            if 'force_benchmark' in env['variant_actions'].keys():
                benchmark = env.AlwaysBuild( benchmark )

            cuppa.progress.NotifyProgress.add( env, benchmark )

            return benchmark

        return []



    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Benchmark", cls( cuppa_env['default_runner'] ) )

        benchmark_runners = set()
        for toolchain in cuppa_env['active_toolchains']:
            for benchmark_runner in toolchain.benchmark_runners():
                benchmark_runners.add( benchmark_runner )

        for benchmark_runner in benchmark_runners:
            cuppa_env.add_method( "{}Benchmark".format( benchmark_runner.title() ), cls( benchmark_runner ) )


