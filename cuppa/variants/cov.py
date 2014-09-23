
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Cov
#-------------------------------------------------------------------------------

# Scons
import SCons.Script

class Cov:

    @classmethod
    def name( cls ):
        return cls.__name__.lower()


    @classmethod
    def add_options( cls, add_option ):
        add_option(
                '--cov', dest=cls.name(), action='store_true',
                help='Build an instrumented binary' )


    @classmethod
    def add_to_env( cls, env, add_variant, add_action ):
        add_variant( cls.name(), cls() )
        add_action( cls.name(), cls() )


    @classmethod
    def create( cls, env, toolchain ):
        env.Append( CXXFLAGS    = toolchain['coverage_cxx_flags'] )
        env.Append( CFLAGS      = toolchain['coverage_c_flags'] )
        env.AppendUnique( LINKFLAGS   = toolchain['coverage_link_cxx_flags'] )
        env.AppendUnique( DYNAMICLIBS = toolchain['coverage_libs'] )
        return env
