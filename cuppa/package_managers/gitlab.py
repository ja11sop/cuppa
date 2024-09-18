
#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Gitlab Package Manager
#-------------------------------------------------------------------------------

# Python imports
import platform
import os
import shlex
import subprocess

from SCons.Script import Flatten, Touch

# cuppa imports
from cuppa.log import logger
from cuppa.colourise import as_error, as_info


def remove_prefix( text, prefix ):
    if text.startswith( prefix ):
        return text[len(prefix):]
    return text


def remove_suffix( text, suffix ):
    if text.endswith( suffix ):
        return text[:-len(suffix)]
    return text


def tool_variant( env, variant=None ):
    return "{toolchain}_{variant}_{arch}_{abi}".format(
            toolchain = env['toolchain'].name(),
            variant = variant and variant or env['variant'].name(),
            arch = env['target_arch'],
            abi = env['abi']
    )


def package_file_name( env, package=None, variant=None, target_dir=None ):
    name = "{package}_{system}_{build_name}.tar.gz".format(
            package    = str(package),
            system     = platform.freedesktop_os_release()['ID'],
            build_name = tool_variant( env, variant )
    )
    if target_dir:
        return os.path.join( target_dir, name )
    return name


def package_url( env, registry=None, package=None, version=None, variant=None ):
    return "{registry}/packages/generic/{package}/{version}/{package_file}".format(
            registry = str(registry),
            package = str(package),
            version = str(version),
            package_file = package_file_name( env, package=package, variant=variant )
    )


def get_token( custom_token=None ):
    if custom_token and custom_token in os.environ:
        return "PRIVATE_TOKEN: {}".format( os.environ[custom_token] )
    elif 'GITLAB_REGISTRY_TOKEN' in os.environ:
        return "PRIVATE_TOKEN: {}".format( os.environ['GITLAB_REGISTRY_TOKEN'] )
    elif 'CI_JOB_TOKEN' in os.environ:
        return "CI_JOB_TOKEN: {}".format( os.environ['CI_JOB_TOKEN'] )
    logger.error( "Could not find token for package registry" )
    return str(None)



class GitlabPackagePublisher:

    def __init__(
        self,
        env,
        source_include_dir=None,
        offset_include_dir=None,
        source_lib_dir=None,
        registry=None,
        package=None,
        version=None,
        custom_token=None
    ):
        self._source_include_dir = env.Dir( str(source_include_dir) )
        self._source_lib_dir     = env.Dir( str(source_lib_dir) )
        self._package_folder     = os.path.join( package, str(version) )
        self._target_include_dir = env.Dir( os.path.join( env['final_dir'], self._package_folder, "include" ) )

        if not offset_include_dir is None:
            self._target_include_dir = env.Dir( os.path.join( str(self._target_include_dir), offset_include_dir ) )

        self._target_lib_dir    = env.Dir( os.path.join( env['final_dir'], self._package_folder, "lib" ) )
        self._package_file_name = package_file_name( env, package=package )
        self._package_location  = env.File( os.path.join( env['abs_final_dir'], self._package_file_name ) )

        self._tar_command = 'tar -C {working_dir} -czf {package_file} {source_dir}'.format(
                working_dir = env['abs_final_dir'],
                package_file = str( self._package_location ),
                source_dir = package
        )

        self._curl_command = 'curl --fail-with-body --header "{token}" --upload-file {package_file} "{package_location}"'.format(
                token = get_token( custom_token ),
                package_file = str( self._package_location ),
                package_location = package_url( env, registry=registry, package=package, version=version )
        )

        self._package_file_path    = os.path.join( self._package_folder, self._package_file_name )
        self._package_published_id = env.File( remove_suffix( self._package_file_path.replace( "/", "_" ), ".tar.gz" ).replace( ".", "_" ) + ".published" )
        self._path_file            = os.path.join( env['abs_final_dir'], env['variant'].name() + ".txt" )


    def _package( self, target, source, env ):
        logger.debug( "Creating package [{}]...".format( as_info( str(target[0]) ) ) )
        completion = subprocess.run( shlex.split( self._tar_command ) )
        if completion.returncode != 0:
            logger.error( "Executing [{}] failed with return code [{}]".format(
                    as_error( self._tar_command ),
                    as_error( str(completion.returncode) ) )
            )
            return completion.returncode
        return None


    def _publish( self, target, source, env ):
        logger.info( "Publishing package [{}]...".format( as_info( str(target[0]) ) ) )
        completion = subprocess.run( shlex.split( self._curl_command ) )
        if completion.returncode != 0:
            logger.error( "Executing [{}] failed with return code [{}]".format(
                    as_error( self._curl_command ),
                    as_error( str(completion.returncode) ) )
            )
            return completion.returncode
        return None


    def __call__( self, target, source, env ):

        libraries = env.CopyFiles( self._target_lib_dir, env.Glob( str( self._source_lib_dir ) + "/*" ) )
        includes  = env.CopyFiles( self._target_include_dir, env.Glob( str( self._source_include_dir ) + "/*" ) )

        package = env.Command( self._package_location, [], self._package )

        env.Depends( package, [ self._target_lib_dir, self._target_include_dir ] )

        env.Clean( target, self._target_lib_dir )
        env.Clean( target, self._target_include_dir )

        installed_package = env.Install( '#_artifacts/', package  )

        package_path_file = env.Textfile( self._path_file, [ self._package_file_path, self._package_file_name ] )

        env.Depends( package_path_file, package )

        installed_path_file = env.Install( '#_artifacts/', package_path_file  )

        env.Clean( target, [ installed_package, installed_path_file ] )

        publish = env.get_option( 'publish-package' ) and True or False

        if publish:
            logger.debug( "Publish package [{}] for target [{}]".format( as_info(str(installed_package[0])), as_info(str(target[0])) ) )

            if self._publish( target, source, env ) is None:
                env.Execute( Touch( target[0] ) )

        return None


    def package_published( self ):
        return self._package_published_id


    def package( self ):
        return self._package_location



class GitlabPackageInstaller:

    def __init__(
            self,
            env,
            target_dir=None,
            registry=None,
            package=None,
            version=None,
            variant=None,
            library_prefix=None,
            custom_token=None
        ):

        self._env = env
        if not target_dir:
            self._target_dir = env['download_root']
        else:
            self._target_dir = str(target_dir)

        package_file = package_file_name( env, package=package, variant=variant )
        # package_variant_dir = remove_prefix( package_file, package + "_" ).split(".")[0]
        self._download_target = os.path.join( self._target_dir, package_file )
        download_dir = os.path.split( self._download_target )[0]
        self._extraction_dir = os.path.join( download_dir, tool_variant( env ) )
        self._package_dir = os.path.join( self._extraction_dir, package, version )
        self._include_dir = os.path.join( self._package_dir, 'include' )
        self._lib_dir = os.path.join( self._package_dir, 'lib' )

        self._library_prefix = library_prefix

        if not os.path.exists( self._extraction_dir ):
            os.makedirs( self._extraction_dir )

        self._wget_command = 'wget --header="{token}" -P {target_dir} -nv {package_location}'.format(
                token = get_token( custom_token ),
                target_dir = self._target_dir,
                package_location = package_url( env, registry=registry, package=package, version=version, variant=variant )
        )
        self._tar_command = 'tar -C {working_dir} -xzf {package}'.format(
                working_dir=self._extraction_dir,
                package=self._download_target
        )


    def __call__( self, target, source, env ):

        if not os.path.exists( self._download_target ):
            logger.debug( "Executing [{}]".format( as_info(self._wget_command) ) )
            completion = subprocess.run( shlex.split( self._wget_command ) )
            if completion.returncode != 0:
                logger.error( "Executing [{}] failed with return code [{}]".format(
                        as_error( self._wget_command ),
                        as_error( str(completion.returncode) ) )
                )
                return completion.returncode

        if not os.path.exists( str(target[0]) ):
            logger.debug( "Executing [{}]".format( as_info(self._tar_command) ) )
            completion = subprocess.run( shlex.split(  self._tar_command ) )
            if completion.returncode != 0:
                logger.error( "Executing [{}] failed with return code [{}]".format(
                        as_error( self._tar_command ),
                        as_error( str(completion.returncode) ) )
                )
                return completion.returncode

        return None


    def download_target( self ):
        return self._download_target


    def extraction_dir( self ):
        return self._extraction_dir


    def package_dir( self ):
        return self._package_dir


    def include_dir( self ):
        return self._include_dir


    def lib_dir( self ):
        return self._lib_dir


    def static_libs( self, libs ):
        libs = Flatten( libs )
        env = self._env
        staticlibs = []
        prefix = self._library_prefix and self._library_prefix or ""
        for lib in libs:
            library_path = os.path.join( self._lib_dir, env['LIBPREFIX'] + prefix + lib + env['LIBSUFFIX'] )
            staticlibs.append( env.File( library_path ) )
        return staticlibs
