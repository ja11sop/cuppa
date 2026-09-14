
#          Copyright Jamie Allsop 2024-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   ManagePackagesMethods
#-------------------------------------------------------------------------------

# cuppa imports
import cuppa.progress

from cuppa.package_managers.package_amend import (
        OPTION_NAME as AMEND_PACKAGE_MANIFEST_OPTION,
        amend_package_manifest_enabled,
)


def publish_package_sources( publisher, built_package, env=None ):
    """Sources that must invalidate ``--publish-package`` after a retar / restage.

    The ``.packaged`` stamp is often an empty ``Touch`` file. With SCons
    ``MD5-timestamp``, retouching it does not change content, so publish would
    skip even when ``package_archive()`` was rewritten. Depend on the archive
    (or other payload) as well when the publisher exposes one.
    """
    from SCons.Script import Flatten

    sources = list( Flatten( [ built_package ] ) )
    archive_fn = getattr( publisher, "package_archive", None )
    if not callable( archive_fn ):
        return sources
    archive = archive_fn()
    if archive is None:
        return sources
    if env is not None:
        file_fn = getattr( env, "File", None )
        if callable( file_fn ):
            sources.append( file_fn( archive ) )
            return sources
    sources.append( archive )
    return sources


class PublishPackageMethod(object):

    def __call__( self, env, source, publisher=None ):

        package = env.File( publisher.package() )
        if amend_package_manifest_enabled( env ):
            amend_fn = getattr( publisher, 'amend_package', None )
            if not callable( amend_fn ):
                import SCons.Errors
                raise SCons.Errors.StopError(
                        "--{} requires a publisher that implements "
                        "amend_package (GitLab). Conan publishers do not "
                        "support metadata-only amend."
                        .format( AMEND_PACKAGE_MANIFEST_OPTION )
                )
            # Do not depend on library / CMake install sources — metadata only.
            built_package = env.Command( package, [], amend_fn )
        else:
            built_package = env.Command(
                    package,
                    [ source, publisher.sources() ],
                    publisher.build_package,
            )
        target = built_package

        if env['clean']:
            env.Clean( built_package, publisher.clean_targets() )

        publish = env.get_option( 'publish-package' ) and True or False

        if publish:
            package_published = env.File( publisher.package_published() )
            published_package = env.Command(
                    package_published,
                    publish_package_sources( publisher, built_package, env=env ),
                    publisher.publish_package,
            )
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
        add_option(
                '--amend-package-manifest',
                dest=AMEND_PACKAGE_MANIFEST_OPTION,
                action='store_true',
                help=(
                        'Rewrite cuppa-dependency.json from the publisher kwargs, '
                        'retar the existing package archive (stage or registry), '
                        'and skip DownloadExtract / CMake rebuild. Pair with '
                        '--publish-package to upload.'
                ),
        )
        add_option(
                '--build-and-publish-dependencies',
                dest='build-and-publish-dependencies',
                action='store_true',
                help=(
                        'Before publishing this package, build and '
                        '--publish-package each GitLab package dependency in '
                        'order (requires package_source and/or --publisher-root). '
                        'Requires --publish-package.'
                ),
        )
        add_option(
                '--publisher-root',
                dest='publisher-root',
                type='string',
                nargs=1,
                help=(
                        'Root directory of a publisher forest used to resolve '
                        'package dependencies when package_source is omitted or '
                        'is a git URL (Phase 1 resolves local trees only).'
                ),
        )


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
