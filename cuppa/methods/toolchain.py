#          Copyright Jamie Allsop 2011-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ToolchainMethod / HasToolchainMethod
#-------------------------------------------------------------------------------

from cuppa.log import logger


_TOOLCHAIN_NAME_DEPRECATED = (
        'env.Toolchain(name) is deprecated; use env.Toolchain() for the active '
        'toolchain or env.HasToolchain(name) (removed in cuppa 2.0)'
)


def lookup_toolchain( toolchains, name ):
    """Return a registered toolchain by registry key or ``name()``, else ``None``."""
    if not name:
        return None
    key = str( name )
    if key in toolchains:
        return toolchains[ key ]
    # Also accept toolchain.name() (build/ABI identity), which for Clang may
    # differ from the registry key when --clang-stdlib tags the name
    # (e.g. registry "clang" vs name() "clang-libc++").
    for registered in toolchains.values():
        if hasattr( registered, 'name' ) and registered.name() == key:
            return registered
    return None


class ToolchainMethod:

    def __init__( self, toolchains ):
        self.__toolchains = toolchains

    def __call__( self, env, toolchain=None ):
        # Configure-time handle / lookup only — no build nodes, so NotifyProgress
        # is intentionally unused.
        if toolchain is None:
            return env['toolchain']
        logger.warn( _TOOLCHAIN_NAME_DEPRECATED )
        return lookup_toolchain( self.__toolchains, toolchain )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Toolchain", cls( cuppa_env['toolchains'] ) )


class HasToolchainMethod:

    def __init__( self, toolchains ):
        self.__toolchains = toolchains

    def __call__( self, env, name ):
        # Registry inspection only — no build nodes.
        return lookup_toolchain( self.__toolchains, name ) is not None

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "HasToolchain", cls( cuppa_env['toolchains'] ) )
