
#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   QuadFloat
#-------------------------------------------------------------------------------


class quad_float():

    def __call__( self, env, toolchain, variant ):
        env.AppendUnique( DYNAMICLIBS = [ 'quadmath'] );
