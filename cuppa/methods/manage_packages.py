
#          Copyright Jamie Allsop 2024-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ManagePackagesMethods
#-------------------------------------------------------------------------------

# cuppa imports
import cuppa.progress


class PublishPackageMethod(object):

    def __call__( self, env, source, publisher=None ):

        package = env.File( publisher.package() )
        built_package = env.Command( package, [ source, publisher.sources() ], publisher.build_package )
        target = built_package

        if env['clean']:
            env.Clean( built_package, publisher.clean_targets() )

        publish = env.get_option( 'publish-package' ) and True or False

        if publish:
            package_published = env.File( publisher.package_published() )
            published_package = env.Command( package_published, built_package, publisher.publish_package )
            target = published_package

        cuppa.progress.NotifyProgress.add( env, target )
        return target


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "PublishPackage", cls() )


    @classmethod
    def add_options( cls, add_option ):
        add_option( '--publish-package', dest='publish-package', action='store_true',
                    help='Specify that you want to publish a package.' )



class InstallPackageMethod(object):

    def __call__( self, env, package_installer=None ):

        package_include_dir = env.Dir( package_installer.include_dir() )

        extracted_package = env.Command( package_include_dir, [], package_installer )

        env.Clean( extracted_package, package_installer.package_dir() )
        env.Clean( extracted_package, package_installer.download_target() )

        env.AppendUnique( SYSINCPATH = package_include_dir )

        cuppa.progress.NotifyProgress.add( env, extracted_package )
        return extracted_package


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "InstallPackage", cls() )



# Example for boost

# from cuppa.dependencies.boost.library_dependencies import add_dependent_libraries
#
# boost_libraries = add_dependent_libraries( 1.86, "static", [
#     'log_setup',
#     'log',
#     'system',
#     'program_options',
#     'unit_test_framework',
# ] )
#
# from cuppa.package_managers.gitlab import GitlabPackageInstaller
#
# installer = GitlabPackageInstaller(
#         env,
#         registry = 'https://your.domain/api/v4/projects/group%2Fregistry',
#         package  = 'boost',
#         version  = "1.86",
#         variant  = "rel"
# )
#
# extracted_package = env.InstallPackage( installer )
#
# env.AppendUnique( STATICLIBS = installer.static_libs( env, "boost_", boost_libraries ) )
