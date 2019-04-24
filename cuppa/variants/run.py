
#          Copyright Jamie Allsop 2019-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Run and Force Run
#-------------------------------------------------------------------------------


class Run:

    @classmethod
    def name( cls ):
        return cls.__name__.lower()


    @classmethod
    def add_options( cls, add_option ):
        add_option(
                '--run', dest=cls.name(), action='store_true',
                help='Execute the specified command' )


    @classmethod
    def add_to_env( cls, env, add_variant, add_action ):
        add_action( cls.name(), cls() )



class ForceRun:

    @classmethod
    def name( cls ):
        return "force_run"


    @classmethod
    def add_options( cls, add_option ):
        add_option(
                '--force-run', dest=cls.name(), action='store_true',
                help='Execute any build outputs created using the Run() method even if they do not need to be run' )


    @classmethod
    def add_to_env( cls, env, add_variant, add_action ):
        add_action( cls.name(), cls() )
