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

        add_option( '--' + cls.package_manager_option(), dest=cls.package_manager_option(), type='string', nargs=1, action='store',
                    help = cls._name + ' package manager to use' )

        if cls._package_manager == "gitlab":
            GitlabPackageDependency.add_options( cls._package_manager, cls._name, add_option )


    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        add_dependency( cls._name, cls.create )


    @classmethod
    def default_version( cls, version, env ):
        pass


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
                package = GitlabPackageDependency( env, **package_args )

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
        self._package.initialise_build_variant( env, toolchain, variant )


    def use_libs( self, libs, depends_on=[] ):
        self._package.use_libs( libs, depends_on=depends_on )


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
