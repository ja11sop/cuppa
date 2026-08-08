
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
import shutil
import subprocess
import zipfile

# cuppa imports
import cuppa.core.storage_options

from cuppa.log import logger, register_secret
from cuppa.colourise import as_error, as_info, as_notice, as_info_label


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
            toolchain = env['toolchain'].package_name(),
            variant = variant and variant or env['variant'].name(),
            arch = env['target_arch'],
            abi = env['abi']
    )


def os_release_id():
    """Linux ``/etc/os-release`` ID (``debian``, ``ubuntu``, …), else a platform fallback.

    Archive names embed this so packages stay OS-scoped. Windows and macOS have no
    freedesktop os-release; fall back to a stable label rather than raising.
    """
    try:
        return platform.freedesktop_os_release()['ID']
    except ( AttributeError, KeyError, OSError, TypeError, ValueError ):
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        if system == 'darwin':
            return 'macos'
        return system or 'unknown'


def package_archive_extension():
    """Preferred package archive suffix: ``.zip`` on Windows, ``.tar.gz`` elsewhere."""
    if platform.system() == 'Windows':
        return '.zip'
    return '.tar.gz'


def package_archive_extensions():
    """Preferred then alternate archive suffixes for resolve fallback."""
    preferred = package_archive_extension()
    alternate = '.tar.gz' if preferred == '.zip' else '.zip'
    return preferred, alternate


def package_file_stem( env, package=None, variant=None ):
    """Basename without archive extension: ``{package}_{os}_{tool_variant}``."""
    return "{package}_{system}_{build_name}".format(
            package    = str(package),
            system     = os_release_id(),
            build_name = tool_variant( env, variant )
    )


def package_file_name( env, package=None, variant=None, target_dir=None ):
    name = package_file_stem( env, package=package, variant=variant ) + package_archive_extension()
    if target_dir:
        return os.path.join( target_dir, name )
    return name


def resolve_existing_package_archive( directory, stem ):
    """Return an existing archive path under ``directory`` for ``stem``, preferring the platform extension.

    Looks for ``stem`` + preferred extension, then the alternate (``.zip`` / ``.tar.gz``), so a
    Windows build can still use a previously published ``*.tar.gz``.
    """
    if not directory or not stem:
        return None
    for extension in package_archive_extensions():
        candidate = os.path.join( directory, stem + extension )
        if os.path.isfile( candidate ):
            return candidate
    return None


def strip_package_archive_extension( name ):
    """Remove a trailing ``.tar.gz`` or ``.zip`` from an archive basename."""
    text = str( name )
    for extension in ( '.tar.gz', '.zip' ):
        if text.endswith( extension ):
            return text[:-len( extension )]
    return text


def create_package_archive( archive_path, working_dir, source_dir ):
    """Create ``archive_path`` from ``working_dir/source_dir`` (zip on Windows, tar.gz elsewhere)."""
    if archive_path.endswith( '.zip' ):
        root = os.path.join( working_dir, source_dir )
        with zipfile.ZipFile( archive_path, 'w', zipfile.ZIP_DEFLATED ) as archive:
            for dirpath, _dirnames, filenames in os.walk( root ):
                for filename in filenames:
                    full = os.path.join( dirpath, filename )
                    arcname = os.path.relpath( full, working_dir )
                    archive.write( full, arcname )
        return 0
    command = 'tar -C {working_dir} -czf {package_file} {source_dir}'.format(
            working_dir = working_dir,
            package_file = archive_path,
            source_dir = source_dir,
    )
    completion = subprocess.run( shlex.split( command ) )
    return completion.returncode


def extract_package_archive( archive_path, extraction_dir ):
    """Extract a GitLab package archive into ``extraction_dir`` (preserves ``package/version/…``)."""
    if archive_path.endswith( '.zip' ):
        with zipfile.ZipFile( archive_path ) as archive:
            archive.extractall( extraction_dir )
        return 0
    from cuppa.utility.download import DownloadError, extract_tar_archive
    try:
        extract_tar_archive( archive_path, extraction_dir )
        return 0
    except DownloadError as error:
        logger.error( "Failed to extract package archive [{}]: {}".format(
                archive_path, error.parameter
        ) )
        return 1


def package_url( env, registry=None, package=None, version=None, variant=None ):
    return "{registry}/packages/generic/{package}/{version}/{package_file}".format(
            registry = str(registry),
            package = str(package),
            version = str(version),
            package_file = package_file_name( env, package=package, variant=variant )
    )


def get_header_token( custom_token=None ):
    """Return a ``Name: value`` header string for curl/wget-style tools."""
    if custom_token and custom_token in os.environ:
        return "PRIVATE-TOKEN: {}".format( os.environ[custom_token] )
    elif 'GITLAB_REGISTRY_TOKEN' in os.environ:
        return "PRIVATE-TOKEN: {}".format( os.environ['GITLAB_REGISTRY_TOKEN'] )
    elif 'CI_JOB_TOKEN' in os.environ:
        return "JOB-TOKEN: {}".format( os.environ['CI_JOB_TOKEN'] )
    logger.error( "Could not find token for package registry" )
    return str(None)


def registry_auth_headers( custom_token=None ):
    """Return a header mapping for ``download_file``, with the token registered for masking."""
    raw = get_header_token( custom_token )
    if not raw or raw == 'None' or ': ' not in raw:
        return {}
    name, value = raw.split( ': ', 1 )
    if value:
        register_secret( value )
    return { name: value }


def download_registry_package( url, dest_path, custom_token=None, label=None ):
    """Fetch a GitLab generic package archive via ``download_file`` (progress + auth headers).

    Raises ``DownloadError`` on failure (callers map that to their own exception types).
    """
    from cuppa.utility.download import download_file
    return download_file(
            url,
            dest_path,
            label=label or os.path.basename( dest_path ) or url,
            headers=registry_auth_headers( custom_token ),
    )


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
        variant=None,
        custom_token=None
    ):
        from SCons.Script import Flatten

        self._source_include_dir = env.Dir( str(source_include_dir) )
        self._source_lib_dir     = env.Dir( str(source_lib_dir) )
        self._package_folder     = os.path.join( package, str(version) )
        self._package_base_dir   = env.Dir( os.path.join( env['final_dir'], self._package_folder ) )
        self._target_include_dir = env.Dir( os.path.join( str(self._package_base_dir), "include" ) )

        if not offset_include_dir is None:
            self._target_include_dir = env.Dir( os.path.join( str(self._target_include_dir), offset_include_dir ) )

        self._target_lib_dir    = env.Dir( os.path.join( env['final_dir'], self._package_folder, "lib" ) )
        self._package_variant   = tool_variant( env, variant=variant )
        self._package_file_name = package_file_name( env, package=package, variant=variant )
        self._package_location  = env.File( os.path.join( env['abs_final_dir'], self._package_file_name ) )
        self._package_source_dir = package

        self._clean_targets = Flatten( [
                self._target_lib_dir,
                self._package_base_dir
        ] )

        self._curl_command = 'curl --fail-with-body --header "{token}" --upload-file {package_file} "{package_location}"'.format(
                token = get_header_token( custom_token ),
                package_file = str( self._package_location ),
                package_location = package_url( env, registry=registry, package=package, version=version )
        )

        self._package_file_path = os.path.join( self._package_folder, self._package_file_name )

        self._package_published_id = env.File(
                strip_package_archive_extension(
                        self._package_file_path.replace( "/", "_" )
                ).replace( ".", "_" ) + ".published"
        )


    def build_package( self, target, source, env ):

        if not os.path.exists( str(self._target_include_dir) ):
            logger.info( "For package [{}], include dir [{}] does not exist so copying include files from [{}]...".format(
                    as_info( self._package_file_name ),
                    as_info( str(self._target_include_dir) ),
                    as_notice( str(self._source_include_dir) )
            ) )
            shutil.copytree( str( self._source_include_dir ), str(self._target_include_dir) )

        if not os.path.exists( str(self._target_lib_dir) ):
            logger.info( "For package [{}], lib dir [{}] does not exist so copying lib files from [{}]...".format(
                    as_info( self._package_file_name ),
                    as_info( str(self._target_lib_dir) ),
                    as_notice( str(self._source_lib_dir) )
            ) )
            shutil.copytree(
                str( self._source_lib_dir ),
                str( self._target_lib_dir ),
                ignore=shutil.ignore_patterns( 'modules' ),
            )

        source_modules = os.path.join( str( self._source_lib_dir ), 'modules' )
        target_modules = os.path.join( str( self._package_base_dir ), 'modules' )
        if os.path.isdir( source_modules ) and not os.path.exists( target_modules ):
            logger.info( "For package [{}], copying modules from [{}]...".format(
                    as_info( self._package_file_name ),
                    as_notice( source_modules ),
            ) )
            shutil.copytree( source_modules, target_modules )

        logger.info( "Creating package [{}]...".format( as_info( str(target[0]) ) ) )
        returncode = create_package_archive(
                str( self._package_location ),
                env['abs_final_dir'],
                self._package_source_dir,
        )
        if returncode != 0:
            logger.error( "Creating package archive [{}] failed with return code [{}]".format(
                    as_error( str( self._package_location ) ),
                    as_error( str( returncode ) ) )
            )
            return returncode

        logger.info( "Package [{}] created".format( as_info( str(target[0]) ) ) )

        return None


    def publish_package( self, target, source, env ):

        from SCons.Script import Touch

        logger.info( "Publishing package [{}]...".format( as_info( str(source[0]) ) ) )
        logger.info( "Using commnd [{}]".format( as_notice( self._curl_command ) ) )

        completion = subprocess.run( shlex.split( self._curl_command ) )
        if completion.returncode != 0:
            logger.error( "Executing [{}] failed with return code [{}]".format(
                    as_error( self._curl_command ),
                    as_error( str(completion.returncode) ) )
            )
            return completion.returncode

        env.Execute( Touch( target[0] ) )
        logger.info( "Package [{}] published".format( as_info( str(source[0]) ) ) )

        return None


    def package_variant( self ):
        return self._package_variant


    def sources( self ):
        return [ self._source_include_dir ]


    def package_published( self ):
        return self._package_published_id


    def package( self ):
        return self._package_location


    def clean_targets( self ):
        return self._clean_targets



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
            self._target_dir = env['dependencies_root']
            if not os.path.isabs( self._target_dir ):
                self._target_dir = os.path.abspath( os.path.join( env['sconstruct_dir'], self._target_dir ) )
        else:
            self._target_dir = str(target_dir)

        package_file = package_file_name( env, package=package, variant=variant )
        stem = package_file_stem( env, package=package, variant=variant )
        # package_variant_dir = remove_prefix( package_file, package + "_" ).split(".")[0]
        preferred_target = os.path.join( self._target_dir, package_file )
        existing = resolve_existing_package_archive( self._target_dir, stem )
        self._download_target = existing or preferred_target
        download_dir = os.path.split( self._download_target )[0]
        self._extraction_dir = os.path.join( download_dir, tool_variant( env, variant=variant ) )
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

        self._package_url = package_url(
                env, registry=registry, package=package, version=version, variant=variant
        )
        self._custom_token = custom_token
        self._package_file = package_file


    def __call__( self, target, source, env ):

        if not os.path.exists( self._download_target ):
            from cuppa.utility.download import DownloadError
            logger.info( "Downloading package archive [{}] from registry...".format(
                    as_info( self._package_file )
            ) )
            try:
                download_registry_package(
                        self._package_url,
                        self._download_target,
                        custom_token=self._custom_token,
                        label=self._package_file,
                )
            except DownloadError as error:
                logger.error( "Failed to download [{}]: {}".format(
                        as_error( self._package_file ),
                        as_error( str( error.parameter ) ),
                ) )
                return 1

        if not os.path.exists( str(target[0]) ):
            logger.info( "Extracting [{}] into [{}]".format(
                    as_info( self._download_target ),
                    as_info( self._extraction_dir ),
            ) )
            returncode = extract_package_archive( self._download_target, self._extraction_dir )
            if returncode != 0:
                logger.error( "Extracting [{}] failed with return code [{}]".format(
                        as_error( self._download_target ),
                        as_error( str( returncode ) ) )
                )
                return returncode

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

        from SCons.Script import Flatten

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

        from SCons.Script import Flatten

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
                    logger.trace( "Setting option for [{}] to [{}]".format(
                            as_notice(attributes['id']),
                            as_info(str(env_option))
                    ) )
                    setattr( package, cls._member(option), env_option )

        if not package._variant:
            package._variant = "rel"

        package.default_version( package._version, env )

        use_develop = env.get_option( "develop" )

        # Extraction dirs are per tool_variant; without this key a multi-toolchain run
        # reuses the first package instance and only resolves one tree.
        try:
            build_id = tool_variant( env, variant=package._variant )
        except ( KeyError, AttributeError, TypeError ):
            build_id = None

        identity = (
            package._registry,
            package._package,
            package._version,
            package._variant,
            use_develop,
            build_id,
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

        use_develop = self.is_option_set( "develop" )
        self._develop = develop

        self._registry = registry
        self._package = package
        self._version = version
        self.version()

        self._variant = variant

        if not self._variant:
            self._variant = "rel"

        self._library_prefix = library_prefix
        if not self._library_prefix:
            self._library_prefix = ""

        self._package_id = "/".join( [ package, self.version(), variant ] )

        cuppa.core.storage_options.report_roots( cuppa_env )

        cache_dir = os.path.join( cuppa_env['downloads_root'], 'packages', package, version )
        package_file = package_file_name( cuppa_env, package=package, variant=variant )
        stem = package_file_stem( cuppa_env, package=package, variant=variant )
        preferred_target = os.path.join( cache_dir, package_file )
        existing = resolve_existing_package_archive( cache_dir, stem )
        self._download_target = existing or preferred_target

        extraction_root = cuppa_env['dependencies_root']
        if not os.path.isabs( extraction_root ):
            extraction_root = os.path.abspath( os.path.join( cuppa_env['sconstruct_dir'], extraction_root ) )

        self._tool_variant = tool_variant( cuppa_env, variant=self._variant )
        self._extraction_dir = os.path.join( extraction_root, self._tool_variant )

        self._package_dir = os.path.join( self._extraction_dir, package, self.version() )
        self._using_develop = bool( self._develop and use_develop )

        if self._using_develop:
            self._develop = os.path.expanduser( self._develop )
            self._package_dir = self._develop

        self._include_dir = os.path.join( self._package_dir, 'include' )
        self._lib_dir = os.path.join( self._package_dir, 'lib' )

        self._pkg_config_dir = None
        if pkg_config_dir:
            if os.path.isabs(pkg_config_dir):
                self._pkg_config_dir = pkg_config_dir
            else:
                self._pkg_config_dir = os.path.join( self._package_dir, pkg_config_dir )
            self._pkg_config_dir = os.path.abspath( self._pkg_config_dir )

        # dump / clean / storage resolve-only: paths are known; do not download or extract.
        # --offline still extracts from a cached archive when one is present.
        if self._dump or self._clean or self._cuppa_env.get( 'storage_resolve_only' ):
            return

        if self._develop and use_develop:
            logger.info( "--develop specified so using package [{}] from [{}]".format(
                    as_info( self._package_id ),
                    as_notice( self._package_dir )
            ) )
            return

        if not os.path.exists( self._extraction_dir ):
            os.makedirs( self._extraction_dir )

        # Prefer an already-cached alternate extension (e.g. legacy Windows .tar.gz).
        existing = resolve_existing_package_archive( cache_dir, stem )
        if existing:
            self._download_target = existing
            package_file = os.path.basename( existing )

        package_location = package_url(
                cuppa_env,
                registry=registry,
                package=package,
                version=self.version(),
                variant=variant,
        )

        # The package file doesn't exist so lets attempt to download it
        if not self._offline:
            if not os.path.exists( self._download_target ):
                # Download the preferred platform name into cache_dir.
                self._download_target = preferred_target
                package_file = os.path.basename( preferred_target )
                if not os.path.isdir( cache_dir ):
                    os.makedirs( cache_dir )
                from cuppa.utility.download import DownloadError
                logger.info( "Downloading package [{}] from [{}] as archive [{}]...".format(
                        as_info( self._package_id ),
                        as_notice( registry ),
                        as_info( package_file )
                ) )
                try:
                    download_registry_package(
                            package_location,
                            self._download_target,
                            custom_token=custom_token,
                            label=package_file,
                    )
                except DownloadError as error:
                    logger.error( "Downloading package archive [{}] failed: {}".format(
                            as_error( package_file ),
                            as_error( str( error.parameter ) ),
                    ) )
                    raise GitlabPackageDependencyException(
                        "Failed to download [{}]: {}".format( package_file, error.parameter )
                    )
                logger.info( "Package archive [{}] downloaded successfully for package [{}] from [{}]".format(
                        as_info( package_file ),
                        as_info( self._package_id ),
                        as_notice( registry )
                ) )
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

        # If there is no include_dir then we didn't successfully extract this before
        if not os.path.exists( self._include_dir ):
            if os.path.exists( self._download_target ):
                logger.debug( "Extracting package [{}] to [{}]".format(
                        as_info( self._download_target ),
                        as_info( self._extraction_dir ),
                ) )
                logger.info( "Extracting package archive [{}] to [{}]...".format(
                        as_info( package_file ),
                        as_info( self._extraction_dir )
                ) )
                returncode = extract_package_archive( self._download_target, self._extraction_dir )
                if returncode != 0:
                    logger.error( "Extracting [{}] failed with return code [{}]".format(
                            as_error( self._download_target ),
                            as_error( str( returncode ) )
                    ) )
                    raise GitlabPackageDependencyException(
                        "Extracting [{}] failed with return code [{}]".format(
                                self._download_target, str( returncode )
                        )
                    )
                logger.info( "Package archive [{}] successfully extracted to [{}]".format(
                        as_info( package_file ),
                        as_info( self._extraction_dir )
                ) )
            else:
                logger.error( "Cannot extract [{}] for package [{}] as the file does not exist".format(
                        as_error( self._download_target ),
                        as_error( self._package_id )
                ) )
        else:
            logger.info( "Using package [{}] from [{}]".format(
                    as_info( self._package_id ),
                    as_notice( os.path.join( self._extraction_dir, package, self.version() ) )
            ) )


    # Observers
    def version( self ):
        return self._version


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


    def local( self ):
        return self._extraction_dir


    def storage_paths( self ):
        """On-disk paths this package owns under the storage roots (optional protocol)."""
        paths = {
            'dependencies': [],
            'downloads': [],
            'build': [],
            'develop': [],
        }
        if getattr( self, '_using_develop', False ):
            if self._package_dir:
                paths['develop'].append( self._package_dir )
            return paths

        if getattr( self, '_package_dir', None ):
            paths['dependencies'].append( self._package_dir )
        if getattr( self, '_download_target', None ):
            paths['downloads'].append( self._download_target )
        return paths


    def storage_qualifier( self ):
        return self.version()


    def storage_tool_variant( self ):
        return getattr( self, '_tool_variant', None )


    def remote_location( self ):
        """Registry identity string for listing (registry/package/version)."""
        registry = getattr( self, '_registry', None )
        package = getattr( self, '_package', None )
        version = self.version()
        parts = [ part for part in ( registry, package, version ) if part ]
        return '/'.join( str( part ) for part in parts ) if parts else None


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
        modules_dir = os.path.join( self._package_dir, 'modules' )
        if os.path.isdir( modules_dir ):
            from cuppa.cpp.cxx_modules import load_packaged_modules
            load_packaged_modules( env, modules_dir )


    def parse_pkg_config( self, libs ):
        env = self._env
        library_prefix = self._library_prefix and self._library_prefix or ""

        # Packages are not retrieved when cleaning, so their .pc files are only
        # present if a previous build downloaded them. The flags they provide
        # affect compiling and linking, not the targets to be removed, so
        # skipping them does not leave anything behind.
        if self._clean and not os.path.isdir( self._pkg_config_dir ):
            logger.info( "Package [{}] was not retrieved so pkg-config data in [{}] is not available."
                         " Skipping it as it is not needed to clean".format(
                    as_info( self._package_id ),
                    as_notice( self._pkg_config_dir )
            ) )
            return

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


    def use_libs( self, libs, depends_on=[] ):

        from SCons.Script import Flatten

        env = self._env
        libs = Flatten( [ libs ] )

        includes = env.AppendUnique( SYSINCPATH = self.include_dir() )
        if depends_on:
            env.Depends( includes, depends_on )

        if self._pkg_config_dir:
            self.parse_pkg_config( libs )
        else:
            self.use_static_libs( libs )


    def use_static_libs( self, libs ):

        from SCons.Script import Flatten

        libs = Flatten( [ libs ] )
        env = self._env
        staticlibs = []
        library_prefix = self._library_prefix and self._library_prefix or ""
        for lib in libs:
            prefix = lib.startswith( library_prefix ) and "" or library_prefix
            library_path = os.path.join( self._lib_dir, env['LIBPREFIX'] + prefix + lib + env['LIBSUFFIX'] )
            staticlibs.append( env.File( library_path ) )

        env.AppendUnique( STATICLIBS = staticlibs )
