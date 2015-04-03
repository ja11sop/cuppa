
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CreateVersionMethod
#-------------------------------------------------------------------------------

class CreateVersionMethod:

    def __init__( self ):
        pass


    def __call__( self, env, target, source, namespaces, version, location ):
        create_version_file_builder = env['toolchain'].version_file_builder( env, namespaces, version, location )
        create_version_file_emitter = env['toolchain'].version_file_emitter( env, namespaces, version, location )

        env.AppendUnique( BUILDERS = {
            'CreateVersionFile' : env.Builder( action=create_version_file_builder, emitter=create_version_file_emitter )
        } )

        return env.CreateVersionFile( target, source )

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "CreateVersion" )
