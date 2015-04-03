
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildWithMethod
#-------------------------------------------------------------------------------

class BuildWithException(Exception):

    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class BuildWithMethod:

    def __init__( self, env ):
        self.__build_with = env['BUILD_WITH']


    def __call__( self, env, build_with ):
        if isinstance( build_with, basestring ):
            build_with = [ build_with ]
        for name in build_with:
            if name in env['dependencies']:
                dependency = env['dependencies'][name]
                if not dependency:
                    raise BuildWithException(
                        "The sconscript [{}] requires the dependency [{}] but it has not been initialised."
                            .format( env['sconscript_file'], name )
                    )
                env.AppendUnique( BUILD_WITH = name )
                dependency( env, env['toolchain'], env['variant'].name() )


    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls( env ), "BuildWith" )


    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        env = sconscript_exports['env']
        if env['default_dependencies']:
            env.BuildWith( env['default_dependencies'] )

