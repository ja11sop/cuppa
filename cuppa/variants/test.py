
#          Copyright Jamie Allsop 2011-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Test and Force Test
#-------------------------------------------------------------------------------


class Test:

    @classmethod
    def name( cls ):
        return cls.__name__.lower()


    @classmethod
    def add_options( cls, add_option ):
        add_option(
                '--test', dest=cls.name(), action='store_true',
                help='Execute any build outputs created using the BuildTest() method' )


    @classmethod
    def add_to_env( cls, env, add_variant, add_action ):
        add_action( cls.name(), cls() )



class ForceTest:

    @classmethod
    def name( cls ):
        return "force_test"


    @classmethod
    def add_options( cls, add_option ):
        add_option(
                '--force-test', dest=cls.name(), action='store_true',
                help='Execute any build outputs created using the Ttest() or BuildTest() method even if they do not need to be run' )


    @classmethod
    def add_to_env( cls, env, add_variant, add_action ):
        add_action( cls.name(), cls() )


