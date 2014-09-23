
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ScmMethod
#-------------------------------------------------------------------------------

class ScmMethod:

    def __init__( self, scm_systems ):
        self.__scm_systems = scm_systems

    def __call__( self, env, scm ):
        if scm and scm in self.__scm_systems:
            return self.__scm_systems[ scm ]

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls( env['scms'] ), "Scm" )
