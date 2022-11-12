
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildWithMethod
#-------------------------------------------------------------------------------

from SCons.Script import Flatten
from cuppa.utility.types import is_string

class BuildWithException(Exception):

    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class BuildWithMethod:

    def __call__( self, env, dependencies ):

        # Ensure we have a list of dependencies
        dependencies = Flatten( dependencies )

        env_dependencies = []

        # We might have string names of dependencies or actual factories
        # so refer to this as an id
        for named_dependency in dependencies:

            name = None
            if is_string( named_dependency ):
                name = named_dependency
            else:
                name = named_dependency.name()

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
                env_dependencies.append( dependency )
            else:
                raise BuildWithException(
                    "The sconscript [{}] requires the dependency [{}] but it cannot be created."
                        .format( env['sconscript_file'], name )
                )
        return len(env_dependencies) == 1 and env_dependencies[0] or env_dependencies


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

