#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   build_with_package
#-------------------------------------------------------------------------------

import os

from cuppa.log import logger
from cuppa.colourise import as_notice, as_error, as_info, colour_items

from cuppa.package_managers.gitlab import GitlabPackageDependency


# SCons AddOption is process-global. Transitive synthesis may call add_options
# again on a later toolchain/variant env whose cloned ``dependencies`` dict
# does not yet contain the name — skip duplicate option strings.
_registered_package_option_names = set()


def _reset_registered_package_options_for_tests():
    """Clear idempotency state between unit tests."""
    _registered_package_option_names.clear()


class base(object):

    _name = None
    _package_manager = None
    _registry = None
    _develop = None
    _cached_packages = {}


    @classmethod
    def package_manager_option( cls ):
        return cls._name + "-package-manager"


    @classmethod
    def add_options( cls, add_option ):
        option_name = cls.package_manager_option()
        if option_name in _registered_package_option_names:
            return

        add_option( '--' + option_name, dest=option_name, type='string', nargs=1, action='store',
                    help = cls._name + ' package manager to use' )

        if cls._package_manager == "gitlab":
            GitlabPackageDependency.add_options( cls._package_manager, cls._name, add_option )

        _registered_package_option_names.add( option_name )


    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        add_dependency( cls._name, cls.create )


    @classmethod
    def default_version( cls, version, env ):
        """Resolve ``None`` / ``\"latest\"`` to the newest version in the GitLab registry."""
        if getattr( cls, '_package_manager', None ) != 'gitlab':
            return
        if version is not None and version != 'latest':
            return

        import SCons.Errors
        from cuppa.package_managers.gitlab_latest import (
                GitlabLatestError,
                resolve_latest_package_version,
        )

        try:
            cls._version = resolve_latest_package_version(
                    env,
                    registry=cls._registry,
                    package=cls._package,
                    custom_token=getattr( cls, '_custom_token', None ),
                    dependency_name=cls._name,
            )
        except GitlabLatestError as error:
            terse = False
            if hasattr( env, "get" ):
                terse = bool( env.get( "terse_output" ) )
            if not terse:
                logger.error( "[{}] {}".format( as_error( cls._name ), as_error( str( error ) ) ) )
            raise SCons.Errors.StopError(
                    "Cannot resolve registry latest for package [{}]: {}".format(
                            cls._name,
                            error,
                    )
            )


    @classmethod
    def package_info( cls, env ):

        package_manager = env.get_option( cls.package_manager_option() )

        if not package_manager and cls._package_manager:
            package_manager = cls._package_manager

        if package_manager == "gitlab":
            return { "manager": package_manager, "package": GitlabPackageDependency.package_id( cls, env ) }

        return None


    @classmethod
    def _get_package( cls, env ):

        import SCons.Errors

        package_info = cls.package_info( env )

        if not package_info:
            return None

        package_id = ( package_info["manager"], package_info["package"]["id"] )

        if package_id not in cls._cached_packages:

            package_manager = package_info["manager"]
            package_args = package_info["package"]["args"]

            logger.debug( "Package args for [{}]({}) are [{}]".format(
                    as_notice( cls._name.title() ),
                    as_info( str(package_id) ),
                    colour_items( package_args )
            ) )

            package = None

            if package_manager == "gitlab":
                package = GitlabPackageDependency(
                        env, dependency_name=cls._name, **package_args
                )

            if package:
                cls._cached_packages[package_id] = package

                logger.debug( "Adding package [{}]({}) to cached packages".format(
                        as_notice( cls._name.title() ),
                        as_notice( str(package_id) )
                ) )

            else:
                logger.error( "Could not get package for [{}] identifed as [{}].".format(
                        as_error( cls._name.title() ),
                        as_error( str(package_id) )
                ) )
                raise SCons.Errors.StopError( "Could not get package for [{}] identifed as [{}].".format(
                        cls._name.title(),
                        str(package_id)
                ) )

        else:
            logger.debug( "Loading package [{}]({}) from cached packages".format(
                    as_notice( cls._name.title() ),
                    as_notice( str(package_id) )
            ) )

        return cls._cached_packages[package_id]


    @classmethod
    def create( cls, env ):

        package = cls._get_package( env )
        if not package:
            return None

        # Now create an instance of the package dependency
        return cls( env, package )


    def __init__( self, env, package ):
        self._package = package


    def __call__( self, env, toolchain, variant ):
        self._package.initialise_build_variant(
                env, toolchain, variant, dependency_name=self._name
        )
        self._register_terse_location( env )


    def _register_terse_location( self, env ):
        """Map ``<packages>/<name>`` from the resolved extract or develop tree."""
        if not env.get( "terse_output" ):
            return
        package = getattr( self, "_package", None )
        name = getattr( self, "_name", None )
        if package is None or not name:
            return
        dir_fn = getattr( package, "package_dir", None )
        pkg_dir = dir_fn() if callable( dir_fn ) else getattr( package, "_package_dir", None )
        if not pkg_dir:
            return
        extract_fn = getattr( package, "extraction_dir", None )
        extract = extract_fn() if callable( extract_fn ) else None
        folder = os.path.basename( str( pkg_dir ).rstrip( "\\/" ) )
        import cuppa.progress
        if extract:
            try:
                pkg_abs = os.path.normpath( pkg_dir )
                extract_abs = os.path.normpath( extract )
                if (
                        pkg_abs == extract_abs
                        or pkg_abs.startswith( extract_abs + os.sep )
                        or pkg_abs.startswith( extract_abs + "/" )
                ):
                    cuppa.progress.label_terse_location(
                            env, "packages", extract, scope="variant",
                            kind="root",
                    )
                    rel = os.path.relpath( pkg_abs, extract_abs ).replace( "\\", "/" )
                    if rel and rel != ".":
                        folder = rel
            except ValueError:
                pass
        cuppa.progress.label_terse_location(
                env, name, pkg_dir, scope="sconstruct", build_folder=folder,
                kind="package",
        )


    def storage_paths( self ):
        """Delegate to the resolved package (optional storage protocol)."""
        package = getattr( self, '_package', None )
        if package is None:
            return None
        method = getattr( package, 'storage_paths', None )
        return method() if method else None


    def storage_qualifier( self ):
        package = getattr( self, '_package', None )
        if package is None:
            return None
        method = getattr( package, 'storage_qualifier', None )
        if callable( method ):
            return method()
        version = getattr( package, 'version', None )
        return version() if callable( version ) else None


    def storage_tool_variant( self ):
        package = getattr( self, '_package', None )
        if package is None:
            return None
        method = getattr( package, 'storage_tool_variant', None )
        return method() if callable( method ) else None


    def remote_location( self ):
        package = getattr( self, '_package', None )
        if package is None:
            return None
        method = getattr( package, 'remote_location', None )
        return method() if callable( method ) else None


    def use_libs( self, libs, depends_on=[] ):
        self._package.use_libs(
                libs, depends_on=depends_on, dependency_name=self._name
        )


    def use_all_libs( self, depends_on=[] ):
        use_all = getattr( self._package, 'use_all_libs', None )
        if not callable( use_all ):
            import SCons.Errors
            raise SCons.Errors.StopError(
                    "Package [{}] does not support use_all_libs().".format( self._name )
            )
        use_all( depends_on=depends_on, dependency_name=self._name )


    def package( self ):
        return self._package


    def local_sub_path( self, *paths ):
        return os.path.join( self._package.local(), *paths )


    def local_abs_path( self, *paths ):
        return os.path.abspath( os.path.join( self._package.local(), *paths ) )


    @classmethod
    def name( cls ):
        return cls._name



def package_dependency( name, package_manager=None, registry=None, develop=None, **kwargs ):

    import SCons.Errors

    if not package_manager:
        package_manager = 'gitlab'

    logger.debug( "Creating [{}] a [{}] package dependency type from [{}]".format(
            as_info( name ),
            as_notice( package_manager ),
            as_info( str(registry) )
    ) )

    if not registry:
        logger.error(
                "Cannot use [{}] package [{}] with no registry specified (and develop [{}])."
                .format(
                        as_notice( str(package_manager) ),
                        as_error( name.title() ),
                        as_info( str(develop) )
                )
        )
        raise SCons.Errors.StopError( "Cannot use [{}] package [{}] with no registry specified (and develop [{}]).".format(
                str(package_manager),
                name.title(),
                str(develop)
        ) )

    # These arguments are common to all package managers
    argument_dict = dict(kwargs)
    argument_dict['name'] = name
    argument_dict['package_manager'] = package_manager
    argument_dict['registry'] = registry
    argument_dict['develop'] = develop

    class_variables = {}
    for arg, value in argument_dict.items():
        class_variables[ '_' + arg ] = value

    if package_manager == 'gitlab':
        for option in GitlabPackageDependency._options:
            member = GitlabPackageDependency._member( option )
            if not member in class_variables:
                class_variables[ member ] = None

    type_name = 'BuildWithPackage' + name.title().replace("_","")

    logger.debug( "[{}], a [{}] package type for [{}] initialised with the cls members [{}]".format(
            as_info( type_name ),
            as_notice( package_manager ),
            as_info( registry ),
            colour_items( class_variables )
    ) )

    return type(
            type_name,
            ( base, ),
            class_variables
    )
