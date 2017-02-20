
#          Copyright Jamie Allsop 2011-2017
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

    def __call__( self, env, build_with ):
        if isinstance( build_with, basestring ):
            build_with = [ build_with ]
        for name in build_with:
            if not name in env['dependencies']:
                raise BuildWithException(
                    "The sconscript [{}] requires the dependency [{}] but it is not available."
                        .format( env['sconscript_file'], name )
                )

            dependency_factory = env['dependencies'][name]
            env.AppendUnique( BUILD_WITH = name )
            dependency = dependency_factory( env )
            if dependency:
                dependency( env, env['toolchain'], env['variant'].name() )
            else:
                raise BuildWithException(
                    "The sconscript [{}] requires the dependency [{}] but it cannot be created."
                        .format( env['sconscript_file'], name )
                )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "BuildWith", cls() )


    @classmethod
    def init_env_for_variant( cls, sconscript_exports ):
        env = sconscript_exports['env']
        if env['default_dependencies']:
            env['_pre_sconscript_phase_'] = True
            env.BuildWith( env['default_dependencies'] )
            env['_pre_sconscript_phase_'] = False

