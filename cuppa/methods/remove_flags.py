
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   RemoveFlags method
#-------------------------------------------------------------------------------

class RemoveFlagsMethod:

    def __init__( self ):
        pass


    def _remove_flags( self, remove, flags ):
        return [f for f in flags if not f.split('=')[0] in remove]


    def __call__( self, env, flags ):
        remove = set( f.split('=')[0] for f in flags )
        env.Replace( CCFLAGS   = self._remove_flags( remove, env['CCFLAGS'] ) )
        env.Replace( CXXFLAGS  = self._remove_flags( remove, env['CXXFLAGS'] ) )
        env.Replace( CFLAGS    = self._remove_flags( remove, env['CFLAGS'] ) )
        env.Replace( LINKFLAGS = self._remove_flags( remove, env['LINKFLAGS'] ) )
        return None


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "RemoveFlags", cls() )
