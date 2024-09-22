
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
from cuppa.colourise import as_error, as_info, as_warning, as_notice


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


def get_header_token( custom_token=None ):
    if custom_token and custom_token in os.environ:
        return "PRIVATE-TOKEN: {}".format( os.environ[custom_token] )
    elif 'GITLAB_REGISTRY_TOKEN' in os.environ:
        return "PRIVATE-TOKEN: {}".format( os.environ['GITLAB_REGISTRY_TOKEN'] )
    elif 'CI_JOB_TOKEN' in os.environ:
        return "JOB-TOKEN: {}".format( os.environ['CI_JOB_TOKEN'] )
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
                token = get_header_token( custom_token ),
                package_file = str( self._package_location ),
                package_location = package_url( env, registry=registry, package=package, version=version )
        )

        self._package_file_path    = os.path.join( self._package_folder, self._package_file_name )

        publish = env.get_option( 'publish-package' ) and True or False

        if publish:
            self._package_published_id = env.File( remove_suffix( self._package_file_path.replace( "/", "_" ), ".tar.gz" ).replace( ".", "_" ) + ".published" )
        else:
            self._package_published_id = env.File( remove_suffix( self._package_file_path.replace( "/", "_" ), ".tar.gz" ).replace( ".", "_" ) + ".created" )

        self._path_file = os.path.join( env['abs_final_dir'], env['variant'].name() + ".txt" )


    def _package( self, target, source, env ):

        print( "_package TARGET = [{}]".format( str([ str(t) for t in target ]) ) )
        print( "_package SOURCE = [{}]".format( str([ str(s) for s in source ]) ) )

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
            pkg_config_dir=None,
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

        self._pkg_config_dir = None
        if pkg_config_dir:
            if os.path.isabs(pkg_config_dir):
                self._pkg_config_dir = pkg_config_dir
            else:
                self._pkg_config_dir = os.path.join( self._package_dir, pkg_config_dir )

        self._library_prefix = library_prefix

        if not os.path.exists( self._extraction_dir ):
            os.makedirs( self._extraction_dir )

        self._wget_command = 'wget --header="{token}" -P {target_dir} -nv {package_location}'.format(
                token = get_header_token( custom_token ),
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


    def build_with( self, env, libs=[], depends_on=[] ):

        includes = env.AppendUnique( SYSINCPATH = self.include_dir() )
        env.Depends( includes, depends_on )

        libs = Flatten( libs )

        if self._pkg_config_dir:
            library_prefix = self._library_prefix and self._library_prefix or ""

            libraries = []
            for lib in libs:
                prefix = lib.startswith( library_prefix ) and "" or library_prefix
                libraries.append( prefix + lib )

            command = 'pkg-config --with-path={pkg_config_dir} {libraries} --libs --cflags'.format(
                    pkg_config_dir=self._pkg_config_dir,
                    libraries=" ".join( libraries )
            )

            print( "PKG-CONFIG COMMAND = [{}]".format( command ) )

            env.ParseConfig( command )
        else:
            env.AppendUnique( STATICLIBS = self.static_libs( env, libs ) )


    def static_libs( self, env, libs ):
        libs = Flatten( libs )
        env = self._env
        staticlibs = []
        library_prefix = self._library_prefix and self._library_prefix or ""
        for lib in libs:
            prefix = lib.startswith( library_prefix ) and "" or library_prefix
            library_path = os.path.join( self._lib_dir, env['LIBPREFIX'] + prefix + lib + env['LIBSUFFIX'] )
            staticlibs.append( env.File( library_path ) )
        return staticlibs


class GitlabPackageDependencyException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class GitlabPackageDependency:

    _options = {
        "registry"       : { "help": "package registry to build against", },
        "package"        : { "help": "package to build against from the specified registry", },
        "version"        : { "help": "package version to build against", },
        "variant"        : { "help": "package variant to build against", },
        "library-prefix" : { "help": "package library prefix that can be used (or omitted) when referencing libs from the package", },
        "pkg-config-dir" : { "help": "package pkg-config folder to use to find pc files", },
        "develop"        : { "help": "local package to build against when in develop mode", },
        "custom-token"   : { "help": "custom token that should be used to authenticate with the registry", }
    }


    class add_option_factory:

        def __init__( self, manager, name, add_option ):
            self._id = "-".join( [ name, manager ] )
            self._add_option = add_option

        def option_id( self, option ):
            return "-".join( [ self._id, option ] )

        def __call__( self, option, help_string ):
            self._add_option(
                    '--' + self.option_id( option ),
                    dest   = self.option_id( option ),
                    type   = 'string',
                    nargs  = 1,
                    action = 'store',
                    help   = " ".join( [ self._id, help_string ] )
            )


    @classmethod
    def add_options( cls, manager, name, add_option ):
        AddOption = cls.add_option_factory( manager, name, add_option )
        for option, attributes in cls._options.items():
            AddOption( option, attributes['help'] )
            attributes['id'] = AddOption.option_id( option )


    @classmethod
    def _member( cls, option ):
        return "_" + option.replace( "-", "_" )


    @classmethod
    def _arg( cls, option ):
        return option.replace( "-", "_" )


    @classmethod
    def _id( cls, package, version, variant ):
        return "/".join( [ package, version, variant ] )


    @classmethod
    def package_id( cls, package, env ):

        for option, attributes in cls._options.items():
            if 'id' in attributes:
                logger.trace( "Getting option for [{}]".format( as_notice(attributes['id']) ) )
                env_option = env.get_option( attributes['id'] )
                if env_option:
                    logger.trace( "Setting option for [{}] to [{}}]".format(
                            as_notice(attributes['id']),
                            as_info(str(env_option))
                    ) )
                    setattr( package, cls._member(option), env_option )

        use_develop = env.get_option( "develop" )

        identity = (
            package._registry,
            package._package,
            package._version,
            package._variant,
            use_develop
        )

        short_id = cls._id( package._package, package._version, package._variant )

        logger.debug( "Identity for package [{}] is [{}]".format( as_info(short_id), as_notice(str(identity)) ) )

        args = {}

        for option in cls._options:
            args[cls._arg(option)] = getattr( package, cls._member(option), None )

        return { "id": identity, "args": args }


    def is_option_set( self, option ):
        return option in self._cuppa_env and self._cuppa_env[option] or False


    def __init__(
            self,
            cuppa_env,
            registry=None,
            package=None,
            version=None,
            variant=None,
            library_prefix=None,
            pkg_config_dir=None,
            custom_token=None,
            develop=None
        ):

        self._cuppa_env = cuppa_env
        self._env = None
        self._offline = self.is_option_set( "offline" )
        self._clean = self.is_option_set( "clean" )
        self._dump = self.is_option_set( "dump" )

        self._package_id = "/".join( [ package, version, variant ] )

        cache_dir = cuppa_env['cache_root']
        package_file = package_file_name( cuppa_env, package=package, variant=variant )
        self._download_target = os.path.join( cache_dir, package_file )
        download_dir = os.path.split( self._download_target )[0]

        extraction_root = cuppa_env['download_root']
        self._extraction_dir = os.path.join( extraction_root, tool_variant( cuppa_env ) )
        self._package_dir = os.path.join( self._extraction_dir, package, version )
        self._include_dir = os.path.join( self._package_dir, 'include' )
        self._lib_dir = os.path.join( self._package_dir, 'lib' )

        self._pkg_config_dir = None
        if pkg_config_dir:
            if os.path.isabs(pkg_config_dir):
                self._pkg_config_dir = pkg_config_dir
            else:
                self._pkg_config_dir = os.path.join( self._package_dir, pkg_config_dir )
            self._pkg_config_dir = os.path.abspath( self._pkg_config_dir )

        self._library_prefix = library_prefix

        if self._dump:
            return

        if self._clean:
            return

        if not os.path.exists( self._extraction_dir ):
            os.makedirs( self._extraction_dir )

        self._wget_command = 'wget --header="{token}" -P {cache_dir} -nv {package_location}'.format(
                token = get_header_token( custom_token ),
                cache_dir = cache_dir,
                package_location = package_url( cuppa_env, registry=registry, package=package, version=version, variant=variant )
        )

        # The package file doesn't exist so lets attempt to download it
        if not self._offline:
            if not os.path.exists( self._download_target ):
                logger.debug( "Downloading package [{}] by executing [{}]".format( as_info(package_file), as_info(self._wget_command) ) )
                completion = subprocess.run( shlex.split( self._wget_command ) )
                if completion.returncode != 0:
                    logger.error( "Executing [{}] failed with return code [{}]".format(
                            as_error( self._wget_command ),
                            as_error( str(completion.returncode) ) )
                    )
                    raise GitlabPackageDependencyException(
                        "Executing [{}] failed with return code [{}]".format( self._wget_command, str(completion.returncode) )
                    )
        elif self._offline and not os.path.exists(self._download_target):
            logger.error(
                "Running in {offline} mode and [{download_target}] does not exist so package cannot be retrieved at this time.".format(
                    offline = as_info_label("OFFLINE"),
                    download_target = as_error(self._download_target)
            ) )
            raise GitlabPackageDependencyException(
                "Running in {offline} mode and [{download_target}] does not exist so package cannot be retrieved at this time.".format(
                    offline = "OFFLINE",
                    download_target = self._download_target
            ) )


        self._tar_command = 'tar -C {working_dir} -xzf {package}'.format(
                working_dir=self._extraction_dir,
                package=self._download_target
        )

        # If there is no inculde_dir then we didn't successfully extract this before
        if not os.path.exists( self._include_dir ):
            if os.path.exists( self._download_target ):
                logger.debug( "Extracting package [{}] by executing [{}]".format( as_info(self._download_target), as_info(self._tar_command) ) )
                completion = subprocess.run( shlex.split(  self._tar_command ) )
                if completion.returncode != 0:
                    logger.error( "Executing [{}] failed with return code [{}]".format(
                            as_error( self._tar_command ),
                            as_error( str(completion.returncode) )
                    ) )
                    return GitlabPackageDependencyException(
                        "Executing [{}] failed with return code [{}]".format( self._tar_command, str(completion.returncode) )
                    )
            else:
                logger.error( "Cannot extract [{}] for package [{}] as the file does not exist".format(
                            as_error( self._download_target ),
                            as_error( self._package_id )
                ) )


    # Observers
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


    # Package Interface

    def initialise_build_variant( self, env, toolchain, variant ):
        logger.debug( "Initialise build variant for [{}:{}] for package [{}] by adding SYSINCPATH of [{}]".format(
                as_notice( str(toolchain.name()) ),
                as_notice( str(variant) ),
                as_info( self._package_id ),
                as_info( self._include_dir )
        ) )
        self._env = env
        env.AppendUnique( SYSINCPATH = self._include_dir )


    def use_libs( self, libs, depends_on=[] ):
        env = self._env
        libs = Flatten( [ libs ] )

        includes = env.AppendUnique( SYSINCPATH = self.include_dir() )
        if depends_on:
            env.Depends( includes, depends_on )

        if self._pkg_config_dir:
            library_prefix = self._library_prefix and self._library_prefix or ""

            libraries = []
            for lib in libs:
                prefix = lib.startswith( library_prefix ) and "" or library_prefix
                libraries.append( prefix + lib )

            command = 'pkg-config --with-path={pkg_config_dir} --libs --cflags {libraries}'.format(
                    pkg_config_dir=self._pkg_config_dir,
                    libraries=" ".join( libraries )
            )

            logger.debug( "Using pkg-config command [{}] to determine appropriate compile and linker flags for package [{}]".format(
                    as_info( command ),
                    as_notice( self._package_id )
            ) )
            env.ParseConfig( command )
        else:
            env.AppendUnique( STATICLIBS = self.static_libs( libs ) )


    def static_libs( self, libs ):
        libs = Flatten( [ libs ] )
        env = self._env
        staticlibs = []
        library_prefix = self._library_prefix and self._library_prefix or ""
        for lib in libs:
            prefix = lib.startswith( library_prefix ) and "" or library_prefix
            library_path = os.path.join( self._lib_dir, env['LIBPREFIX'] + prefix + lib + env['LIBSUFFIX'] )
            staticlibs.append( env.File( library_path ) )
        return staticlibs
