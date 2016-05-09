
#          Copyright Jamie Allsop 2016
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CopyFilesAsMethod
#-------------------------------------------------------------------------------

import os.path

from SCons.Script import Flatten

import cuppa.progress


class CopyFilesAsMethod:

    def __call__( self, env, target, source ):

        destinations = []
        for destination in Flatten([target]):
            if not os.path.isabs( destination ):
                destination = os.path.join( env['abs_final_dir'], destination )
            destinations.append( destination )

        installed_files = env.InstallAs( destinations, source )
        cuppa.progress.NotifyProgress.add( env, installed_files )
        return installed_files

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CopyFilesAs", cls() )

