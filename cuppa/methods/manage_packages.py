
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
    archive = publisher_package_archive_node( publisher, env )
    if archive is not None:
        sources.append( archive )
    return sources


def publisher_package_archive_node( publisher, env=None ):
    """Return the publisher archive File/path, or ``None`` when unset."""
    archive_fn = getattr( publisher, "package_archive", None )
    if not callable( archive_fn ):
        return None
    archive = archive_fn()
    if archive is None:
        return None
    if env is not None:
        file_fn = getattr( env, "File", None )
        if callable( file_fn ):
            return file_fn( archive )
    return archive


def declare_package_archive_side_effect( env, built_package, publisher ):
    """Tell SCons the archive is produced with the ``.packaged`` stamp.

    ``build_package`` / ``amend_package`` write the ``.tar.gz`` / ``.zip`` as a
    side effect. Listing that archive as a ``.published`` source (for MD5
    invalidation) without ``SideEffect`` lets ``-j`` demand the file before
    packaging finishes — ``Source not found``.
    """
    archive = publisher_package_archive_node( publisher, env )
    if archive is None:
        return
    side_effect = getattr( env, "SideEffect", None )
    if not callable( side_effect ):
        return
    side_effect( archive, built_package )


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
        declare_package_archive_side_effect( env, built_package, publisher )
        target = built_package

        if env['clean']:
            env.Clean( built_package, publisher.clean_targets() )

        publish = env.get_option( 'publish-package' ) and True or False
        stage = env.get_option( 'stage-package' ) and True or False
        if stage and publish:
            import SCons.Errors
            raise SCons.Errors.StopError(
                    "--stage-package and --publish-package cannot be combined; "
                    "stage builds the package archive without uploading."
            )

        if publish:
            package_published = env.File( publisher.package_published() )
            published_package = env.Command(
                    package_published,
                    publish_package_sources( publisher, built_package, env=env ),
                    publisher.publish_package,
            )
            target = published_package
            if env.get_option( 'force' ):
                always = getattr( env, 'AlwaysBuild', None )
                if callable( always ):
                    always( built_package )
                    always( published_package )

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
                '--stage-package',
                dest='stage-package',
                action='store_true',
                help=(
                        'Build and stage this package\'s archive under final/ '
                        'without uploading. Used by nested --stage-develop '
                        'sessions. Cannot be combined with --publish-package.'
                ),
        )
        add_option(
                '--amend-package-manifest',
                dest=AMEND_PACKAGE_MANIFEST_OPTION,
                action='store_true',
                help=(
                        'Rewrite cuppa-publish.json from the publisher kwargs, '
                        'retar the package archive, and skip DownloadExtract / '
                        'CMake (and RemoveEmptyDirs). Prefer an existing '
                        'final/<package>/<version>/ stage; otherwise extract a '
                        'local archive or download it from the registry first. '
                        'Removes any legacy cuppa-dependency.json twin. Pair with '
                        '--publish-package to upload. Does not restage binaries '
                        'from source_include_dir / source_lib_dir.'
                ),
        )
        add_option(
                '--build-and-publish-dependencies',
                dest='build-and-publish-dependencies',
                action='store_true',
                help=(
                        'Enable cascade for GitLab package dependencies '
                        '(requires package_source and/or --publisher-root). '
                        'Pair with a companion action: --publish-package '
                        '(nested publish + tip upload), '
                        '--publish-cascade-dependencies (nested publish, tip '
                        'build only), --cascade-plan, --collect-cascade, or '
                        '--update-publishers. Not compatible with -n/--no-exec '
                        'when nested sessions would run. Nested publishes that '
                        'are already current in the registry are skipped unless '
                        '--force is set.'
                ),
        )
        add_option(
                '--force',
                dest='force',
                action='store_true',
                help=(
                        'With --build-and-publish-dependencies, rebuild and '
                        'upload every resolved dependency even when the tip\'s '
                        'consume archive already matches the registry. Also '
                        'forces nested PublishPackage targets to rebuild.'
                ),
        )
        add_option(
                '--publish-cascade-dependencies',
                dest='publish-cascade-dependencies',
                action='store_true',
                help=(
                        'With --build-and-publish-dependencies, build and '
                        '--publish-package each resolved GitLab package '
                        'dependency (leaf-first), refresh tip consume caches, '
                        'then continue with the tip build only — do not upload '
                        'the tip. Cannot be combined with --publish-package. '
                        'Works for consume-only tips and publisher tips.'
                ),
        )
        add_option(
                '--cascade-plan',
                dest='cascade-plan',
                action='store_true',
                help=(
                        'Report the resolved cascade publish order and each '
                        'dependency\'s publisher tree, then stop without '
                        'cloning, building, publishing, or uploading anything. '
                        'Requires --build-and-publish-dependencies; '
                        '--publish-package is not needed because nothing is '
                        'published.'
                ),
        )
        add_option(
                '--collect-cascade',
                dest='collect-cascade',
                action='store_true',
                help=(
                        'Resolve the cascade graph and clone missing publisher '
                        'trees (with --clone-publishers) into the publishers '
                        'forest, reusing trees that already exist, then stop '
                        'without building or publishing. Requires '
                        '--build-and-publish-dependencies; --publish-package is '
                        'not needed. Not the same as --publish-package -n.'
                ),
        )
        add_option(
                '--update-publishers',
                dest='update-publishers',
                action='store_true',
                help=(
                        'Fetch and fast-forward publisher working trees the '
                        'cascade would use (same clean/behind gates as '
                        '--update-develop). Skips --develop trees. Requires '
                        '--build-and-publish-dependencies. Alone or with '
                        '--collect-cascade it stops before build/upload; with '
                        '--publish-package or --publish-cascade-dependencies it '
                        'updates then runs the nested publish. Not with '
                        '--cascade-plan. Live update refuses '
                        '--offline; -n still checks remotes when online. '
                        'Reports an ACTION table (updated / no change / '
                        'left alone; dry-run: would update / leave alone).'
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
                        'is a git URL. With --clone-publishers this is also '
                        'where a missing tree is cloned to.'
                ),
        )
        add_option(
                '--publish-modified',
                dest='publish-modified',
                action='store_true',
                help=(
                        'Allow a cascade publish from a publisher tree that '
                        'holds work only this machine has (uncommitted '
                        'changes, unpushed commits, or a branch with no '
                        'upstream) — whether that tree is a --develop copy, '
                        'a --publisher-root forest entry, or a '
                        '--clone-publishers clone. Cascade refuses by '
                        'default, because the registry version could not be '
                        'rebuilt from history.'
                ),
        )
        add_option(
                '--clone-publishers',
                dest='clone-publishers',
                action='store_true',
                help=(
                        'Let cascade clone a publisher tree it cannot find '
                        'locally from its package_source URL, which may be '
                        'pinned as url@branch, url@tag, or url@revision. '
                        'Cascade then runs a build in that tree (unless '
                        '--collect-cascade or --cascade-plan), so this is '
                        'opt-in; --cascade-plan reports every URL and '
                        'destination first, and --collect-cascade performs '
                        'the clones without building. Clones land under '
                        '--publisher-root when set, otherwise in '
                        '<storage-root>/publishers. Existing trees are reused '
                        'as they stand and never switched or overwritten. Not '
                        'available with --offline.'
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
