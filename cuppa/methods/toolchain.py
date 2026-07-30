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
        # Lookup helper only (returns toolchain metadata/object).
        # No build nodes are emitted, so NotifyProgress is intentionally unused.
        if not toolchain:
            return None
        key = str( toolchain )
        if key in self.__toolchains:
            return self.__toolchains[ key ]
        # Also accept toolchain.name() (build/ABI identity), which for Clang may
        # differ from the registry key when --clang-stdlib tags the name
        # (e.g. registry "clang" vs name() "clang-libc++").
        for registered in self.__toolchains.values():
            if hasattr( registered, 'name' ) and registered.name() == key:
                return registered
        return None

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Toolchain", cls( cuppa_env['toolchains'] ) )
