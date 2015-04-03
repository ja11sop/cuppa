
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ToolchainMethod
#-------------------------------------------------------------------------------

class ToolchainMethod:

    def __init__( self, toolchains ):
        self.__toolchains = toolchains

    def __call__( self, env, toolchain ):
        if toolchain and toolchain in self.__toolchains:
            return self.__toolchains[ toolchain ]

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls( env['toolchains'] ), "Toolchain" )
