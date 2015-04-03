
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   UseMethod
#-------------------------------------------------------------------------------

class UseMethod:

    def __init__( self, dependencies ):
        self.__dependencies = dependencies

    def __call__( self, env, dependency ):
        if dependency in self.__dependencies:
            return self.__dependencies[ dependency ]
        return None

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls( env['dependencies'] ), "Using" )
