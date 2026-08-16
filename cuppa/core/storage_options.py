#          Copyright Jamie Allsop 2018-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Storage Options
#-------------------------------------------------------------------------------

"""Where cuppa keeps what it builds, retrieves, and downloads.

Four project-local / shared roots, decided in one place. `build_root` and
`artefacts_root` stay project-relative (US alias `artifacts_root`). `dependencies_root` holds ready-to-use
dependency trees and `downloads_root` holds the archives they came from; both
derive from `storage_root` unless set individually.

`resolve_root()` is the whole rule, so no subsystem re-implements the precedence and a report can
never describe a path a build then ignores. It is a pure function of the values it is handed,
which is what makes the precedence, the deprecated aliases, and the fallback to an older location
testable without a filesystem beyond a directory check.
"""

# Python Standard
import os

from collections import namedtuple

# Cuppa
from cuppa.colourise import as_error, as_info, as_notice
from cuppa.log import logger



class default(object):

    build_root     = '_build'
    artefacts_root = '_artefacts'
    artifacts_root = artefacts_root
    storage_root   = '~/.cuppa'
    dependencies = 'dependencies'
    downloads    = 'downloads'


# Where a previous cuppa kept these. Honouring an existing tree matters more here than it would
# for a pure rename, because the default location moves as well as the name: a machine that has
# already retrieved everything must not silently re-fetch it into ~/.cuppa. The project-local
# folder is listed first because that, not the shared one, is what the old default produced.
LEGACY_DEPENDENCIES = ( '_cuppa', '~/_cuppa/_download' )
LEGACY_DOWNLOADS    = ( '~/_cuppa/_cache', )
LEGACY_ARTEFACTS    = ( '_artifacts', )


# How a root was decided, so the caller can say so without repeating the rule. `origin` names the
# thing that decided it: an option name, or the older folder that is being kept in use.
Resolved = namedtuple( 'Resolved', [ 'path', 'source', 'origin' ] )


def add_storage_options( add_option ):

    add_option( '--build-root', type='string', nargs=1, action='store',
                            dest='build_root',
                            help="The root directory for build output. If not specified"
                                 " then " +  default.build_root + " is used" )

    add_option( '--artefacts-root', type='string', nargs=1, action='store',
                            dest='artefacts_root',
                            help="The root directory for generated reports and other"
                                 " project artefacts outside the build tree. If not"
                                 " specified then " + default.artefacts_root + " is used" )

    add_option( '--artifacts-root', type='string', nargs=1, action='store',
                            dest='artifacts_root',
                            help="US spelling alias for --artefacts-root" )

    add_option( '--storage-root', type='string', nargs=1, action='store',
                            dest='storage_root',
                            help="The parent directory for the dependencies and downloads roots."
                                 " If not specified then " + default.storage_root + " is used."
                                 " Set this to a path inside your project, for example"
                                 " --storage-root=_cuppa, to keep all storage with the project" )

    add_option( '--dependencies-root', type='string', nargs=1, action='store',
                            dest='dependencies_root',
                            help="The root directory holding retrieved dependency trees ready to"
                                 " build against. If not specified then <storage-root>/"
                                 + default.dependencies + " is used" )

    add_option( '--downloads-root', type='string', nargs=1, action='store',
                            dest='downloads_root',
                            help="The root directory holding downloaded archives. If not"
                                 " specified then <storage-root>/" + default.downloads
                                 + " is used" )

    add_option( '--download-root', type='string', nargs=1, action='store',
                            dest='download_root',
                            help="Deprecated alias for --dependencies-root" )

    add_option( '--cache-root', type='string', nargs=1, action='store',
                            dest='cache_root',
                            help="Deprecated alias for --downloads-root" )



def normal_path( path ):
    return os.path.normpath( os.path.expanduser( path ) )


def existing_legacy_root( candidates, anchor ):
    """The first older location that is actually there, in the form it was written in.

    A relative candidate is tested against the project but returned relative, because the
    dependencies root is excluded from sconscript discovery by folder name and only a relative
    name matches. Resolving it here would quietly start scanning retrieved trees for sconscripts.
    """
    for candidate in candidates:
        path = normal_path( candidate )
        located = path if os.path.isabs( path ) else os.path.join( anchor or '', path )
        if os.path.isdir( located ):
            return path
    return None


def resolve_root( option, alias, legacy, derived, anchor=None ):
    """Where a storage root is, and what decided it.

    An explicit value wins; then a deprecated alias, which means the same thing said by an older
    name; then an older location that already holds something, so an upgrade does not re-fetch a
    machine's worth of dependencies; then the value derived from the storage root.
    """
    if option:
        return Resolved( normal_path( option ), 'option', None )

    if alias:
        return Resolved( normal_path( alias ), 'deprecated', None )

    kept = existing_legacy_root( legacy, anchor )
    if kept:
        return Resolved( kept, 'legacy', kept )

    return Resolved( normal_path( derived ), 'derived', None )


def report( resolved, name, deprecated_option, replaced_by ):
    """Say how a root was decided when the reason is something to act on.

    Using an old option name is a deprecation, which is the reader's to fix. Keeping an older
    folder is cuppa choosing for them so that nothing is re-fetched, which they have not done
    anything wrong to deserve, but do need to know about.
    """
    if resolved.source == 'deprecated':
        logger.warn( "[{}] is deprecated, use [{}] instead. Using [{}] for {}".format(
                as_notice( deprecated_option ),
                as_info( replaced_by ),
                as_notice( resolved.path ),
                name
        ) )
    elif resolved.source == 'legacy':
        logger.info( "Using the existing [{}] for {} rather than the new default. Move it and"
                     " set [{}] when you want the new location".format(
                as_notice( resolved.origin ),
                name,
                as_info( replaced_by )
        ) )


def resolve_artefacts_root( cuppa_env ):
    """Resolve project artefacts root from British or US CLI spellings."""
    british = cuppa_env.get_option( 'artefacts_root' )
    us = cuppa_env.get_option( 'artifacts_root' )
    if british and us and normal_path( british ) != normal_path( us ):
        logger.warn(
            "[{}] and [{}] disagree; using [{}]".format(
                as_notice( '--artefacts-root' ),
                as_notice( '--artifacts-root' ),
                as_notice( normal_path( british ) ),
            ),
        )
    if british or us:
        return normal_path( british or us )
    anchor = cuppa_env.get( 'sconstruct_dir' )
    kept = existing_legacy_root( LEGACY_ARTEFACTS, anchor )
    if kept:
        return kept
    return default.artefacts_root


def process_storage_options( cuppa_env ):

    build_root = cuppa_env.get_option( 'build_root', default=default.build_root )
    anchor = cuppa_env.get( 'sconstruct_dir' )
    artefacts_root = resolve_artefacts_root( cuppa_env )

    cuppa_env['build_root']     = normal_path( build_root )
    cuppa_env['abs_build_root'] = os.path.abspath( cuppa_env['build_root'] )
    cuppa_env['artefacts_root'] = artefacts_root
    cuppa_env['abs_artefacts_root'] = os.path.abspath( cuppa_env['artefacts_root'] )
    cuppa_env['artifacts_root'] = cuppa_env['artefacts_root']
    cuppa_env['abs_artifacts_root'] = cuppa_env['abs_artefacts_root']

    if (
        not cuppa_env.get_option( 'artefacts_root' )
        and not cuppa_env.get_option( 'artifacts_root' )
    ):
        kept = existing_legacy_root( LEGACY_ARTEFACTS, anchor )
        if kept:
            logger.info(
                "Using the existing [{}] for artefacts rather than the new default. "
                "Move it and set [{}] when you want the new location".format(
                    as_notice( kept ),
                    as_info( '--artefacts-root' ),
                ),
            )

    storage_root = normal_path(
            cuppa_env.get_option( 'storage_root', default=default.storage_root ) )

    anchor = cuppa_env.get( 'sconstruct_dir' )

    dependencies = resolve_root(
            cuppa_env.get_option( 'dependencies_root' ),
            cuppa_env.get_option( 'download_root' ),
            LEGACY_DEPENDENCIES,
            os.path.join( storage_root, default.dependencies ),
            anchor
    )

    downloads = resolve_root(
            cuppa_env.get_option( 'downloads_root' ),
            cuppa_env.get_option( 'cache_root' ),
            LEGACY_DOWNLOADS,
            os.path.join( storage_root, default.downloads ),
            anchor
    )

    report( dependencies, "dependencies", "--download-root", "--dependencies-root" )
    report( downloads, "downloads", "--cache-root", "--downloads-root" )

    cuppa_env['storage_root']      = storage_root
    cuppa_env['dependencies_root'] = dependencies.path
    cuppa_env['downloads_root']    = downloads.path

    # The old keys stay as aliases of the resolved values for at least one minor release, so a
    # third-party dependency plugin reading env['download_root'] keeps working through the rename.
    cuppa_env['download_root']     = dependencies.path
    cuppa_env['cache_root']        = downloads.path

    cuppa_env['storage_roots_reported'] = False

    if not os.path.exists( cuppa_env['downloads_root'] ):
        try:
            os.makedirs( cuppa_env['downloads_root'] )
        except os.error as e:
            logger.error( "Creating downloads_root directory [{}] failed with error: {}"
                         .format( cuppa_env['downloads_root'], as_error(str(e)) ) )
            raise


def report_roots( cuppa_env ):
    """Name the roots the first time a run reaches for one.

    They are shared between projects and hidden by default, so where they are needs to be visible
    in build output rather than only in documentation. Saying it on the first retrieval, rather
    than on every run, keeps it where it means something.
    """
    if cuppa_env.get( 'storage_roots_reported' ):
        return

    cuppa_env['storage_roots_reported'] = True

    logger.info( "Using [{}] for dependencies and [{}] for downloads".format(
            as_info( os.path.abspath( os.path.expanduser( cuppa_env['dependencies_root'] ) ) ),
            as_info( os.path.abspath( os.path.expanduser( cuppa_env['downloads_root'] ) ) )
    ) )
