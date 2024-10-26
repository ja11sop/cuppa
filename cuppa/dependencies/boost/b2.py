
#          Copyright Jamie Allsop 2011-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   B2
#-------------------------------------------------------------------------------
import os
import shutil
import re
import platform
import shlex

# Cuppa Imports
import cuppa.build_platform

from cuppa.output_processor   import IncrementalSubProcess, ToolchainProcessor
from cuppa.colourise          import as_emphasised, as_notice, as_info
from cuppa.log                import logger

# Boost Imports
from cuppa.dependencies.boost.library_naming import directory_from_abi_flag, toolset_from_toolchain


def b2_exe_name( boost_version ):
    exe_name = 'b2'
    if boost_version < 1.47:
        exe_name = 'bjam'
    if platform.system() == "Windows":
        exe_name += ".exe"
    return exe_name


def b2_exe( boost_version, boost_location ):
    exe_name = b2_exe_name( boost_version )
    return os.path.join( boost_location, exe_name )


def b2_as_command( boost_version, boost_location ):
    if platform.system() != "Windows":
        return "./" + b2_exe_name( boost_version )
    return b2_exe( boost_version, boost_location )


def b2_command( env, boost_version, location, toolchain, libraries, variant, target_arch, linktype, stage_dir, verbose_build, verbose_config, job_count, parallel, defines ):

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

    if defines:
        for define in defines:
            build_flags += ' define="{}"'.format( define )

    if linktype == 'shared':
        build_flags += ' define="BOOST_ALL_DYN_LINK"'

    build_dir = "bin." + directory_from_abi_flag( abi_flag )

    b2 = b2_as_command( boost_version, location )

    toolset = toolset_from_toolchain( toolchain )

    command_line = "{b2}{verbose} -j {jobs}{with_libraries} toolset={toolset} variant={variant} {address_model} {architecture} {windows_api} {build_flags} link={linktype} --build-dir=.{path_sep}{build_dir} stage --stagedir=.{path_sep}{stage_dir} --ignore-site-config".format(
            b2              = b2,
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



class ProcessB2Build(object):

    def __init__( self, version ):
        self.b2_exe_path = b2_exe_name( version )
        self.search_output_for_path = version < 1.71

    def _search_for_path( self, line ):
        match = re.search( r'\[COMPILE\] ([\S]+)', line )
        if match:
            self.b2_exe_path = match.expand( r'\1' )
        return line

    def __call__( self, line ):
        if self.search_output_for_path:
            self._search_for_path( line )
        return line

    def exe_path( self ):
        return self.b2_exe_path



class BuildB2(object):

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

        b2_build_script = './build.sh'
        if platform.system() == "Windows":
            b2_build_script = os.path.join( build_script_path, 'build.bat' )

        logger.debug( "Execute [{}] from [{}]".format(
                b2_build_script,
                str(build_script_path)
        ) )

        process_b2_build = ProcessB2Build( self._version )

        try:
            IncrementalSubProcess.Popen(
                process_b2_build,
                [ b2_build_script ],
                cwd=build_script_path
            )

            b2_exe_path = process_b2_build.exe_path()

            if not b2_exe_path:
                logger.critical( "Could not determine b2 exe path" )
                return 1

            b2_binary_path = os.path.join( build_script_path, b2_exe_path )

            if not os.path.exists( b2_binary_path ):
                logger.critical( "Could find b2 exe on path [{}]".format( b2_binary_path ) )
                return 1

            logger.debug( "Copying b2 exe from [{}] to [{}]".format( as_info( b2_binary_path ), as_notice( target[0].path ) ) )
            shutil.copy( b2_binary_path, target[0].path )

        except OSError as error:
            logger.critical( "Error building b2 [{}]".format( str( error.args ) ) )
            return 1

        return None



class B2OutputProcessor(object):

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
