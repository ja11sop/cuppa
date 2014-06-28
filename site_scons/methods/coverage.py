
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CoverageMethod
#-------------------------------------------------------------------------------

class CoverageMethod:

    def __init__( self, toolchain ):
        self.__toolchain = toolchain


    def __call__( self, env, source, final_dir ):
        coverage_builder = self.__toolchain.coverage_builder()
        coverage_emitter = self.__toolchain.coverage_emitter( final_dir )

        env.AppendUnique( BUILDERS = {
            'Coverage' : env.Builder( action=coverage_builder, emitter=coverage_emitter )
        } )

        env.Coverage( [], source )

    @classmethod
    def add_to_env( cls, args ):
        args['env'].AddMethod( cls( args['env']['toolchain'] ), "Coverage" )
