
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildProfileMethod
#-------------------------------------------------------------------------------
import six

class BuildProfileMethod:

    def __init__( self, env ):
        self.__build_profile = env['BUILD_PROFILE']


    def __call__( self, env, build_profile ):
        for profile in build_profile:

            if isinstance( profile, six.string_types ):
                name = profile
                if name in env['profiles']:
                    profile = env['profiles'][name]
            else:
                name = str( profile )

            env.AppendUnique( BUILD_PROFILE = name )
            profile( env, env['toolchain'], env['variant'].name() )


    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls( args['env'] ), "BuildProfile" )


    @classmethod
    def init_env_for_variant( cls, args ):
        if args['env']['default_profiles']:
            args['env'].BuildProfile( args['env']['default_profiles'] )

