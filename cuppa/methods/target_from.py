
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   TargetFrom
#-------------------------------------------------------------------------------
import os


class TargetFromMethod:

    def __call__( self, env, source, final_dir=None ):
        target = os.path.splitext( os.path.relpath( source.path, env['build_dir'] ) )[0]
        return target

    @classmethod
    def add_to_env( cls, env ):
        env.AddMethod( cls(), "TargetFrom" )
