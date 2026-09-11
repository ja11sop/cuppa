#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   VariantMethod — active variant handle
#-------------------------------------------------------------------------------

class VariantMethod:

    def __call__( self, env ):
        # Configure-time handle only — no build nodes, so NotifyProgress is
        # intentionally unused.
        return env['variant']

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Variant", cls() )
