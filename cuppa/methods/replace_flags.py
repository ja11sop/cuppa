
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ReplaceFlags method
#-------------------------------------------------------------------------------

class ReplaceFlagsMethod:

    def __init__( self ):
        pass


    def __call__( self, env, flags ):
        env.RemoveFlags( flags )
        env.MergeFlags( flags )
        return None


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "ReplaceFlags" )
