
#          Copyright Jamie Allsop 2011-2016
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildProfileMethod
#-------------------------------------------------------------------------------
import cuppa.utility

class BuildProfileMethod:

    def __call__( self, env, build_profile ):
        for profile in build_profile:
            if cuppa.utility.is_string( profile ):
                name = profile
                if name in env['profiles']:
                    profile = env['profiles'][name]
            else:
                name = str( profile )

            env.AppendUnique( BUILD_PROFILE = name )
            profile( env, env['toolchain'], env['variant'].name() )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "BuildProfile", cls() )


    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        env = sconscript_exports['env']
        if env['default_profiles']:
            env['_pre_sconscript_phase_'] = True
            env.BuildProfile( env['default_profiles'] )
            env['_pre_sconscript_phase_'] = False

