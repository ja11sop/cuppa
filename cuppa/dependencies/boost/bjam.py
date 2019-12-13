
#          Copyright Jamie Allsop 2011-2019
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
import shlex

# Cuppa Imports
import cuppa.build_platform

from cuppa.output_processor   import IncrementalSubProcess, ToolchainProcessor
from cuppa.colourise          import as_emphasised
from cuppa.log                import logger

# Boost Imports
from cuppa.dependencies.boost.library_naming import directory_from_abi_flag, toolset_from_toolchain



def bjam_command( env, location, toolchain, libraries, variant, target_arch, linktype, stage_dir, verbose_build, verbose_config, job_count, parallel ):

    verbose = ""
    if verbose_build:
        verbose += " -d+2"
    if verbose_config:
        verbose += " --debug-configuration"

    jobs = "1"
    if job_count >= 2 and parallel:
        if len(libraries)>4:
            jobs = str( job_count - 1 )
        else:
            jobs = str( job_count/4 + 1 )

    with_libraries = ""
    for library in libraries:
        with_libraries += " --with-" + library

    build_flags = ""
    abi_flag = toolchain.abi_flag(env)
    if abi_flag:
        build_flags = 'cxxflags="' + abi_flag + '"'

    address_model = ""
    architecture = ""
    windows_api = ""
    if toolchain.family() == "cl":
        if target_arch == "amd64":
            address_model = "address-model=64"
        elif target_arch == "arm":
            address_model = "architecture=arm"
        if toolchain.target_store() != "desktop":
            windows_api = "windows-api=" + toolchain.target_store()

    build_flags += ' define="BOOST_DATE_TIME_POSIX_TIME_STD_CONFIG"'

    if linktype == 'shared':
        build_flags += ' define="BOOST_ALL_DYN_LINK"'

    build_dir = "bin." + directory_from_abi_flag( abi_flag )

    bjam = './bjam'
    if platform.system() == "Windows":
        # Use full path on Windows
        bjam = os.path.join( location, 'bjam.exe' )

    toolset = toolset_from_toolchain( toolchain )

    command_line = "{bjam}{verbose} -j {jobs}{with_libraries} toolset={toolset} variant={variant} {address_model} {architecture} {windows_api} {build_flags} link={linktype} --build-dir=.{path_sep}{build_dir} stage --stagedir=.{path_sep}{stage_dir} --ignore-site-config".format(
            bjam            = bjam,
            verbose         = verbose,
            jobs            = jobs,
            with_libraries  = with_libraries,
            toolset         = toolset,
            variant         = variant,
            address_model   = address_model,
            architecture    = architecture,
            windows_api     = windows_api,
            build_flags     = build_flags,
            linktype        = linktype,
            build_dir       = build_dir,
            stage_dir       = stage_dir,
            path_sep        = os.path.sep
    )

    if platform.system() == "Windows":
        command_line = command_line.replace( "\\", "\\\\" )
    command_line = command_line.replace( '"', '\\"' )

    return shlex.split( command_line )



def bjam_exe( boost ):
    exe_name = 'bjam'
    if platform.system() == "Windows":
        exe_name += ".exe"
    return os.path.join( boost.local(), exe_name )



class ProcessBjamBuild(object):

    def __init__( self, version ):
        self.bjam_exe_path = 'bjam'
        if platform.system() == "Windows":
            self.bjam_exe_path += '.exe'

        self.search_output_for_path = version < 1.71

    def _search_for_path( self, line ):
        match = re.search( r'\[COMPILE\] ([\S]+)', line )
        if match:
            self.bjam_exe_path = match.expand( r'\1' )
        return line

    def __call__( self, line ):
        if self.search_output_for_path:
            self._search_for_path( line )
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

        process_bjam_build = ProcessBjamBuild( self._version )

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

    @classmethod
    def _toolset_name_from_toolchain( cls, toolchain ):
        toolset_name = toolchain.toolset_name()
        if cuppa.build_platform.name() == "Darwin":
            if toolset_name == "gcc":
                toolset_name = "darwin"
            elif toolset_name == "clang":
                toolset_name = "clang-darwin"
        elif cuppa.build_platform.name() == "Linux":
            if toolset_name == "clang":
                toolset_name = "clang-linux"
        return toolset_name


    def __init__( self, env, verbose_build, verbose_config, toolchain ):

        toolset_name = self._toolset_name_from_toolchain( toolchain )
        self._toolset_filter = toolset_name + '.'

        self._verbose_build = verbose_build
        self._verbose_config = verbose_config

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
