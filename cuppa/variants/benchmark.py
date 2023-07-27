
#          Copyright Jamie Allsop, Jonny Weir 2023
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Benchmark and Force Benchmark
#-------------------------------------------------------------------------------


class Benchmark:

    @classmethod
    def name( cls ):
        return cls.__name__.lower()


    @classmethod
    def add_options( cls, add_option ):
        add_option(
                '--benchmark', dest=cls.name(), action='store_true',
                help='Execute any build outputs created using the BuildBenchmark() method' )


    @classmethod
    def add_to_env( cls, env, add_variant, add_action ):
        add_action( cls.name(), cls() )



class ForceBenchmark:

    @classmethod
    def name( cls ):
        return "force_benchmark"


    @classmethod
    def add_options( cls, add_option ):
        add_option(
                '--force-benchmark', dest=cls.name(), action='store_true',
                help='Execute any build outputs created using the Benchmark() or BuildBenchmark() method even if they do not need to be run' )


    @classmethod
    def add_to_env( cls, env, add_variant, add_action ):
        add_action( cls.name(), cls() )


