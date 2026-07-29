#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   HeaderUnit method — declare a header for BMI compilation
#-------------------------------------------------------------------------------

from cuppa.cpp.cxx_modules import build_header_unit


class HeaderUnitMethod:

    def __call__( self, env, header, **kwargs ):
        # Delegates to cxx_modules.build_header_unit(), which creates the BMI
        # command and wires NotifyProgress for the returned node.
        return build_header_unit( env, header, **kwargs )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'HeaderUnit', cls() )
