
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   StdCpp method
#-------------------------------------------------------------------------------

from cuppa.colourise import as_error


class StdCppMethod:

    stdcpp_choices = ( "c++98", "c++03", "c++0x", "c++11", "c++1y", "c++14" )

    @classmethod
    def add_options( cls, add_option ):

        add_option( '--stdcpp', dest='stdcpp', choices=cls.stdcpp_choices, nargs=1, action='store',
            help="Use this option to override the default language compliance of your cpp compiler which by dafault is the highest compliance available. Value may be one of {}".format( str(cls.stdcpp_choices) ) )

    @classmethod
    def get_options( cls, env ):
        env['stdcpp'] = env.get_option( 'stdcpp' )


    def __init__( self ):
        pass


    def __call__( self, env, standard ):
        if standard not in self.stdcpp_choices:
            print as_error( env, "cuppa: stdcpp: error: [{}] not in allowed list {}".format( standard, self.stdcpp_choices ) )
            return None
        env[ 'stdcpp' ] = standard
        toolchain = env['toolchain']
        flag = toolchain.stdcpp_flag_for( standard )
        env.ReplaceFlags( [ flag ] )
        return None


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "StdCpp" )

