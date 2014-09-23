
#          Copyright Jamie Allsop 2013-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CompileMethod
#-------------------------------------------------------------------------------

class CompileMethod:

    def __call__( self, env, source ):
        objects = env.Object( source,
                              CPPPATH = env['SYSINCPATH'] + env['INCPATH'] )
        return objects

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "Compile" )
