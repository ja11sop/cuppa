#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ImportModules method — load packaged BMI module-map into the env registry
#-------------------------------------------------------------------------------

from cuppa.cpp.cxx_modules import load_packaged_modules


class ImportModulesMethod:

    def __call__( self, env, modules_dir, **kwargs ):
        return load_packaged_modules( env, modules_dir )

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'ImportModules', cls() )
