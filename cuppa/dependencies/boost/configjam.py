#          Copyright Jamie Allsop 2011-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ConfigJam
#-------------------------------------------------------------------------------
import os


from cuppa.log import logger

# Boost Imports
from cuppa.dependencies.boost.library_naming import toolset_name_from_toolchain


_CUPPA_PROJECT_CONFIG_MARKER = "# File created by cuppa:boost"


def _neutralise_cuppa_project_config_jam( boost_local ):
    """Remove a cuppa-authored project-config.jam left by older Cuppa versions.

    b2 still auto-loads project-config.jam when present. Toolsets now come from
    --user-config=<toolchain>._jam; a torn leftover from the old shared RMW
    path must not stay in the tree.
    """
    project_config_path = os.path.join( boost_local, "project-config.jam" )
    if not os.path.isfile( project_config_path ):
        return
    try:
        with open( project_config_path ) as project_config_jam:
            first_line = project_config_jam.readline()
    except OSError:
        return
    if not first_line.startswith( _CUPPA_PROJECT_CONFIG_MARKER ):
        return
    try:
        os.remove( project_config_path )
        logger.info(
            "removed leftover cuppa project-config.jam [{}] (toolsets use --user-config)".format(
                project_config_path
            )
        )
    except OSError as error:
        logger.warn(
            "could not remove leftover project-config.jam [{}]: {}".format(
                project_config_path,
                error,
            )
        )


class WriteToolsetConfigJam(object):

    def __call__( self, target, source, env ):
        path = str(target[0])
        boost_local = os.path.split( path )[0]
        _neutralise_cuppa_project_config_jam( boost_local )

        if not os.path.exists( path ):
            toolchain = env['toolchain']
            current_toolset = "using {} : {} :".format( toolset_name_from_toolchain( toolchain ), toolchain.cxx_version() )
            toolset_config_line = "{} {} ;\n".format( current_toolset, toolchain.binary() )

            with open( path, 'w' ) as toolchain_config:
                logger.info( "adding toolset config [{}] to user-config [{}]".format( str(toolset_config_line.strip()), path ) )
                toolchain_config.write( toolset_config_line )

        return None
