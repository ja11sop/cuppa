
#          Copyright Jamie Allsop 2011-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dbg
#-------------------------------------------------------------------------------

# Scons
import SCons.Script

class Dbg:

    @classmethod
    def name( cls ):
        return cls.__name__.lower()


    @classmethod
    def add_options( cls ):
        SCons.Script.AddOption(
                '--dbg', dest=cls.name(), action='store_true',
                help='Build a debug binary' )


    @classmethod
    def add_to_env( cls, args ):
        args['env']['variants'][cls.name()] = cls()


    @classmethod
    def create( cls, env, toolchain ):
        env.AppendUnique( CXXFLAGS  = toolchain['debug_cxx_flags'] )
        env.AppendUnique( CFLAGS    = toolchain['debug_c_flags'] )
        return env

