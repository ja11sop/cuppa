
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Bjam
#-------------------------------------------------------------------------------
import os
import shutil
import re
import platform

from cuppa.output_processor import IncrementalSubProcess, ToolchainProcessor
from cuppa.colourise        import as_info, as_emphasised
from cuppa.log              import logger



class ProcessBjamBuild(object):

    def __call__( self, line ):
        match = re.search( r'\[COMPILE\] ([\S]+)', line )
        if match:
            self.bjam_exe_path = match.expand( r'\1' )
        return line

    def exe_path( self ):
        return self.bjam_exe_path



class BuildBjam(object):

    def __init__( self, boost ):
        self._location = boost.local()
        self._version  = boost.numeric_version()

    def __call__( self, target, source, env ):

        build_script_path = os.path.join( self._location, 'tools', 'build' )

        if self._version < 1.47:
            build_script_path = os.path.join( build_script_path, 'src', 'v2', 'engine' )

        elif self._version > 1.55:
            build_script_path = os.path.join( build_script_path, 'src', 'engine' )

        else:
            build_script_path = os.path.join( build_script_path, 'v2', 'engine' )

        bjam_build_script = './build.sh'
        if platform.system() == "Windows":
            bjam_build_script = os.path.join( build_script_path, 'build.bat' )

        logger.debug( "Execute [{}] from [{}]".format(
                bjam_build_script,
                str(build_script_path)
        ) )

        process_bjam_build = ProcessBjamBuild()

        try:
            IncrementalSubProcess.Popen(
                process_bjam_build,
                [ bjam_build_script ],
                cwd=build_script_path
            )

            bjam_exe_path = process_bjam_build.exe_path()

            if not bjam_exe_path:
                logger.critical( "Could not determine bjam exe path" )
                return 1

            bjam_binary_path = os.path.join( build_script_path, bjam_exe_path )

            shutil.copy( bjam_binary_path, target[0].path )

        except OSError as error:
            logger.critical( "Error building bjam [{}]".format( str( error.args ) ) )
            return 1

        return None



class BjamOutputProcessor(object):

    def __init__( self, env, verbose_build, verbose_config, toolset_name ):
        self._verbose_build = verbose_build
        self._verbose_config = verbose_config
        self._toolset_filter = toolset_name + '.'

        self._minimal_output = not self._verbose_build
        ignore_duplicates = not self._verbose_build
        self._toolchain_processor = ToolchainProcessor( env['toolchain'], self._minimal_output, ignore_duplicates )


    def __call__( self, line ):
        if line.startswith( self._toolset_filter ):
            return line
        elif not self._verbose_config:
            if(     line.startswith( "Performing configuration" )
                or  line.startswith( "Component configuration" )
                or  line.startswith( "    - " ) ):
                return None
        return self._toolchain_processor( line )


    def summary( self, returncode ):
        summary = self._toolchain_processor.summary( returncode )
        if returncode and not self._verbose_build:
            summary += "\nTry running with {} for more details".format( as_emphasised( '--boost-verbose-build' ) )
        return summary
