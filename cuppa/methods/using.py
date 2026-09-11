#          Copyright Jamie Allsop 2011-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   UseMethod (deprecated) / HasDependencyMethod
#-------------------------------------------------------------------------------

from cuppa.log import logger


_USING_DEPRECATED = (
        'env.Using() is deprecated; use env.HasDependency() (removed in cuppa 2.0)'
)


class UseMethod:

    def __init__( self, dependencies ):
        self.__dependencies = dependencies

    def __call__( self, env, dependency ):
        # Deprecated factory peek — prefer HasDependency for existence checks.
        # No build nodes are emitted, so NotifyProgress is intentionally unused.
        logger.warn( _USING_DEPRECATED )
        if dependency in self.__dependencies:
            return self.__dependencies[ dependency ]
        return None

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Using", cls( cuppa_env['dependencies'] ) )


class HasDependencyMethod:

    def __init__( self, dependencies ):
        self.__dependencies = dependencies

    def __call__( self, env, name ):
        # Registry key membership only — not “BuildWith would succeed”.
        # No build nodes are emitted, so NotifyProgress is intentionally unused.
        return name in self.__dependencies

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "HasDependency", cls( cuppa_env['dependencies'] ) )
