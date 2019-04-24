
#          Copyright Jamie Allsop 2011-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ConfigJam
#-------------------------------------------------------------------------------
import os
import shutil


from cuppa.log import logger

# Boost Imports
from cuppa.dependencies.boost.library_naming import toolset_name_from_toolchain



class WriteToolsetConfigJam(object):

    def _update_project_config_jam( self, project_config_path, current_toolset, toolset_config_line ):

        config_added = False
        changed      = False

        temp_path = os.path.splitext( project_config_path )[0] + ".new_jam"

        if not os.path.exists( project_config_path ):
            with open( project_config_path, 'w' ) as project_config_jam:
                project_config_jam.write( "# File created by cuppa:boost\n" )

        with open( project_config_path ) as project_config_jam:
            with open( temp_path, 'w' ) as temp_file:
                for line in project_config_jam.readlines():
                    if line.startswith( current_toolset ):
                        if line != toolset_config_line:
                            temp_file.write( toolset_config_line )
                            changed = True
                        config_added = True
                    else:
                        temp_file.write( line )
                if not config_added:
                    temp_file.write( toolset_config_line )
                    changed = True
        if changed:
            os.remove( project_config_path )
            shutil.move( temp_path, project_config_path )
        else:
            os.remove( temp_path )


    def __call__( self, target, source, env ):
        path = str(target[0])
        if not os.path.exists( path ):
            toolchain = env['toolchain']
            current_toolset = "using {} : {} :".format( toolset_name_from_toolchain( toolchain ), toolchain.cxx_version() )
            toolset_config_line = "{} {} ;\n".format( current_toolset, toolchain.binary() )

            with open( path, 'w' ) as toolchain_config:
                logger.info( "adding toolset config [{}] to dummy toolset config [{}]".format( str(toolset_config_line.strip()), path ) )
                toolchain_config.write( toolset_config_line )

            self._update_project_config_jam(
                os.path.join( os.path.split( path )[0], "project-config.jam" ),
                current_toolset,
                toolset_config_line
            )

        return None


