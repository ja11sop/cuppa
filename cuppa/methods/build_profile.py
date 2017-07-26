
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildProfileMethod
#-------------------------------------------------------------------------------


from SCons.Script import Flatten
from cuppa.utility.types import is_string


class BuildProfileException(Exception):

    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class BuildProfileMethod:

    def __call__( self, env, profiles ):
        # Ensure we have a list of profiles
        profiles = Flatten( profiles )

        # We might have string names of profiles or actual factories
        # so refer to this as an id
        for named_profile in profiles:

            name = None
            if is_string( named_profile ):
                name = named_profile
            else:
                name = named_profile.name()

            if not name in env['profiles']:
                raise BuildProfileException(
                    "The sconscript [{}] requires the profile [{}] but it is not available."
                        .format( env['sconscript_file'], name )
                )

            profile_factory = env['profiles'][name]
            env.AppendUnique( BUILD_PROFILE = name )
            profile = profile_factory( env )
            if profile:
                profile( env, env['toolchain'], env['variant'].name() )
            else:
                raise BuildProfileException(
                    "The sconscript [{}] requires the profile [{}] but it cannot be created."
                        .format( env['sconscript_file'], name )
                )


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

