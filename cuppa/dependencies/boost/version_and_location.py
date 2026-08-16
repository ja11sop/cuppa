#          Copyright Jamie Allsop 2011-2023
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Version and Location
#-------------------------------------------------------------------------------
import os
import re
import lxml.html

try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen

# Cuppa Imports
import cuppa.build_platform
import cuppa.location
from cuppa.configure          import global_config_path, read_setting, upsert_setting
from cuppa.colourise          import as_info, as_notice
from cuppa.log                import logger
from cuppa.utility.python2to3 import maketrans
from cuppa.utility            import storage as storage_util

# Boost Imports
from cuppa.dependencies.boost.boost_exception import BoostException
from cuppa.dependencies.boost.patch_boost     import apply_patches_if_needed


BOOST_LATEST_VERSION_KEY = 'boost_latest_version'


def current_boost_release():
    return "1.91.0"


def boost_patched_requested( env ):
    """True when the patched Boost home is selected (``clean/`` vs ``patched/``)."""
    return bool(
            env.get_option( 'boost-patched' )
            or env.get_option( 'boost-patch-boost-test' )
    )


def boost_location_id( env ):

    location   = env.get_option( 'boost-location' )
    home       = env.get_option( 'boost-home' )
    version    = env.get_option( 'boost-version' )
    latest     = env.get_option( 'boost-latest' )
    thirdparty = env[ 'thirdparty' ]
    patch_test = boost_patched_requested( env )

    base = None

    if location:
        base = None

    elif home:
        base = home

    elif thirdparty and version:
        base = thirdparty

    elif version:
        base = None

    # --boost-latest overrides --boost-version on the download path (not with
    # --boost-home / --boost-location, where the tree is already pinned).
    if latest and not location and not home:
        version = "latest"

    # Default (nothing specified): leave version unset. Resolve uses stored
    # boost_latest_version, then an online scrape on Boost use, then
    # current_boost_release(). --boost-latest forces a fresh scrape first.

    return ( location, version, base, patch_test )


def _home_from_path( path ):
    if os.path.exists( path ) and os.path.isdir( path ):
        return path
    return None


def boost_version_key( version ):
    """Comparable tuple for Boost dotted/underscored version strings."""
    if version is None:
        return ()
    text = str( version ).strip().replace( '_', '.' )
    parts = []
    for piece in text.split( '.' ):
        if piece.isdigit():
            parts.append( int( piece ) )
        else:
            match = re.match( r'(\d+)', piece )
            if match:
                parts.append( int( match.group( 1 ) ) )
            else:
                parts.append( 0 )
    return tuple( parts )


def version_is_higher( candidate, stored ):
    if not candidate:
        return False
    if not stored:
        return True
    return boost_version_key( candidate ) > boost_version_key( stored )


def boost_latest_conf_path( env ):
    """Project ``configure.conf`` when downloads_root is under the project; else ``~/.cuppaconfig``."""
    downloads_root = env.get( 'downloads_root' ) if hasattr( env, 'get' ) else None
    if downloads_root is None:
        try:
            downloads_root = env['downloads_root']
        except Exception:
            downloads_root = None

    sconstruct_dir = None
    for key in ( 'abs_sconstruct_dir', 'sconstruct_dir' ):
        try:
            sconstruct_dir = env[key] if key in env else None
        except Exception:
            sconstruct_dir = None
        if sconstruct_dir:
            break

    project_conf = None
    try:
        project_conf = env.get_option( 'use_conf' ) if hasattr( env, 'get_option' ) else None
    except Exception:
        project_conf = None
    if not project_conf:
        project_conf = 'configure.conf'
    if sconstruct_dir and not os.path.isabs( project_conf ):
        project_conf = os.path.join( os.path.abspath( sconstruct_dir ), project_conf )

    if downloads_root and sconstruct_dir and storage_util.is_contained(
            os.path.abspath( downloads_root ),
            os.path.abspath( sconstruct_dir ),
    ):
        return project_conf

    return global_config_path()


def stored_boost_latest_version( env ):
    return read_setting( boost_latest_conf_path( env ), BOOST_LATEST_VERSION_KEY )


def scrape_latest_boost_version():
    """Scrape https://www.boost.org/releases/latest/. Return version string or None on failure."""
    try:
        boost_version_url = 'https://www.boost.org/releases/latest/'
        logger.info( "Checking current boost version from {}...".format( as_info( boost_version_url ) ) )
        html = lxml.html.parse( urlopen( boost_version_url ) )

        current_release = html.xpath( "string()" )
        current_release = str( re.search( r'(\d[.]\d+([.]\d+)?)', current_release ).group( 1 ) )

        logger.info( "Latest boost release detected as [{}]".format( as_info( current_release ) ) )
        return current_release

    except Exception as e:
        logger.warn( "Cannot determine latest version of boost - [{}].".format( str( e ) ) )
        return None


def resolve_boost_latest_version( env, force_scrape=False ):
    """Resolve the Boost version for a latest/default download path.

    Returns ``(version, source)`` where ``source`` is one of
    ``scraped``, ``stored``, ``compiled_in``, ``scrape_failed_fallback``.

    When no explicit ``--boost-version=`` pins the download, latest resolution
    is implied: stored value, then an online scrape when not offline, then the
    compiled-in default. ``force_scrape`` (``--boost-latest``) skips the stored
    value and checks boost.org first so you can override a pin or refresh the
    remembered latest.
    """
    offline = bool( env['offline'] ) if 'offline' in env else False

    if force_scrape and not offline:
        scraped = scrape_latest_boost_version()
        if scraped:
            return scraped, 'scraped'
        fallback = current_boost_release()
        logger.warn(
                "Boost latest scrape failed; using compiled-in default [{}] "
                "(not persisted as a scrape result).".format( as_info( fallback ) )
        )
        return fallback, 'scrape_failed_fallback'

    stored = stored_boost_latest_version( env )
    if stored:
        logger.info(
                "Using stored {} = [{}] from [{}]".format(
                        as_notice( BOOST_LATEST_VERSION_KEY ),
                        as_info( str( stored ) ),
                        as_info( boost_latest_conf_path( env ) ),
                )
        )
        return str( stored ), 'stored'

    if not offline:
        scraped = scrape_latest_boost_version()
        if scraped:
            return scraped, 'scraped'

    if force_scrape and offline:
        logger.info(
                "In offline mode with --boost-latest; no stored {} so assuming [{}]".format(
                        as_notice( BOOST_LATEST_VERSION_KEY ),
                        as_info( current_boost_release() ),
                )
        )
    else:
        logger.info(
                "No stored {}; using compiled-in default [{}]".format(
                        as_notice( BOOST_LATEST_VERSION_KEY ),
                        as_info( current_boost_release() ),
                )
        )
    return current_boost_release(), 'compiled_in'


def determine_latest_boost_version( offline ):
    """Legacy helper: scrape when online, else compiled-in default."""
    if offline:
        logger.info(
                "In offline mode. No version of boost specified so assuming [{}]".format(
                        as_info( current_boost_release() )
                )
        )
        return current_boost_release()
    scraped = scrape_latest_boost_version()
    if scraped:
        return scraped
    current_release = current_boost_release()
    logger.warn(
            "Cannot determine latest version of boost. Assuming [{}].".format(
                    as_info( current_release )
            )
    )
    return current_release


def _is_latest_token( token ):
    return token is None or token in ( 'latest', 'current' )


def _concrete_boost_version( env, token, force_scrape ):
    if _is_latest_token( token ):
        version, source = resolve_boost_latest_version( env, force_scrape=force_scrape )
        return version, source
    return token, 'explicit'


def archive_present_under_downloads( env, boost_location ):
    downloads_root = env.get( 'downloads_root' ) if hasattr( env, 'get' ) else None
    if downloads_root is None:
        try:
            downloads_root = env['downloads_root']
        except Exception:
            return False
    if not downloads_root or not boost_location:
        return False
    local_folder = getattr( boost_location, '_local_folder', None )
    if not local_folder:
        return False
    cached = boost_location.get_cached_archive( downloads_root, local_folder )
    if cached and os.path.exists( cached ):
        return True
    candidate = os.path.join( downloads_root, local_folder )
    return os.path.exists( candidate )


def maybe_persist_boost_latest( env, version, source, boost_location ):
    """Upsert boost_latest_version when higher and archive is under downloads_root."""
    if source == 'scrape_failed_fallback':
        return False
    if source == 'explicit':
        return False
    if not version or not archive_present_under_downloads( env, boost_location ):
        return False

    conf_path = boost_latest_conf_path( env )
    stored = read_setting( conf_path, BOOST_LATEST_VERSION_KEY )
    if not version_is_higher( version, stored ):
        return False

    upsert_setting( conf_path, BOOST_LATEST_VERSION_KEY, str( version ) )
    logger.info(
            "Stored {} = [{}] in [{}]".format(
                    as_notice( BOOST_LATEST_VERSION_KEY ),
                    as_info( str( version ) ),
                    as_info( conf_path ),
            )
    )
    # Keep in-process configured_options in sync when present
    try:
        options = env['configured_options']
        if isinstance( options, dict ):
            options[BOOST_LATEST_VERSION_KEY] = str( version )
    except Exception:
        pass
    return True


def get_boost_location( env, location, version, base, patched ):
    logger.debug( "Identify boost using location = [{}], version = [{}], base = [{}], patched = [{}]".format(
            as_info( str(location) ),
            as_info( str(version) ),
            as_info( str(base) ),
            as_info( str(patched) )
    ) )

    boost_home = None
    boost_location = None
    resolved_version = None
    resolve_source = 'explicit'
    force_scrape = bool( env.get_option( 'boost-latest' ) )

    extra_sub_path = 'clean'
    if patched:
        extra_sub_path = 'patched'

    offline = env['offline']

    if location:
        concrete, resolve_source = _concrete_boost_version( env, location, force_scrape )
        if _is_latest_token( location ):
            resolved_version = concrete
        location = _location_from_boost_version( concrete, offline )

        logger.trace( "Location after version detection = [{}]".format( as_notice( str(location) ) ) )

        if not location: # use version as a fallback in case both at specified
            concrete, resolve_source = _concrete_boost_version( env, version, force_scrape )
            if _is_latest_token( version ):
                resolved_version = concrete
            location = _location_from_boost_version( concrete, offline )
        boost_location = cuppa.location.Location( env, location, extra_sub_path=extra_sub_path, name_hint="boost" )

    elif base: # Find boost locally
        if not os.path.isabs( base ):
            base = os.path.abspath( base )

        if not version:
            boost_home = base
        elif version:
            search_list = [
                os.path.join( base, 'boost', version, 'source' ),
                os.path.join( base, 'boost', 'boost_' + version ),
                os.path.join( base, 'boost', version ),
                os.path.join( base, 'boost_' + version ),
            ]

            def exists_in( locations ):
                for location in locations:
                    home = _home_from_path( location )
                    if home:
                        return home
                return None

            boost_home = exists_in( search_list )
            if not boost_home:
                raise BoostException("Cannot construct Boost Object. Home for Version [{}] cannot be found. Seached in [{}]".format(version, str([l for l in search_list])))
        else:
            raise BoostException("Cannot construct Boost Object. No Home or Version specified")

        logger.debug( "Using boost found at [{}]".format( as_info( boost_home ) ) )
        boost_location = cuppa.location.Location( env, boost_home, extra_sub_path=extra_sub_path )
    else:
        concrete, resolve_source = _concrete_boost_version( env, version, force_scrape )
        if _is_latest_token( version ):
            resolved_version = concrete
        location = _location_from_boost_version( concrete, offline )
        boost_location = cuppa.location.Location( env, location, extra_sub_path=extra_sub_path )

    apply_patches_if_needed( patched, boost_location.local(), get_boost_version ( boost_location.local() )[0] )

    if resolved_version:
        maybe_persist_boost_latest( env, resolved_version, resolve_source, boost_location )

    return boost_location



def get_boost_version( location ):
    version_hpp_path = os.path.join( location, 'boost', 'version.hpp' )
    if not os.path.exists( version_hpp_path ):
        raise BoostException("Boost version.hpp file not found")
    with open( version_hpp_path ) as version_hpp:
        for line in version_hpp:
            match = re.search( r'BOOST_VERSION\s+(?P<version>\d+)', line )
            if match:
                int_version = int(match.group('version'))
                major = int_version//100000
                minor = int_version//100%1000
                patch = int_version%100
                full_version = "{}.{}.{}".format( major, minor, patch )
                short_version = "{}_{}".format( major, minor )
                numeric_version = float(major) + float(minor)/100
                return full_version, short_version, numeric_version
    raise BoostException("Could not determine BoostVersion")



def _location_from_boost_version( location, offline ):
    # latest/current tokens must already be resolved to a concrete version
    if location == "latest" or location == "current":
        location = determine_latest_boost_version( offline )
    if location:
        match = re.match( r'(boost_)?(?P<version>\d[._]\d\d(?P<minor>[._]\d)?)(?:[_\-.]rc(?P<release_candidate>\d))?', location )
        if match:
            logger.debug( "Only boost version specified, retrieve from SourceForge if not already cached" )

            extension = ".tar.gz"
            if cuppa.build_platform.name() == "Windows":
                extension = ".zip"

            boost_version = match.group('version')
            if not match.group('minor'):
                boost_version += "_0"
            numeric_version = boost_version.translate( maketrans( '._', '..' ) )

            string_version = boost_version.translate( maketrans( '._', '__' ) )
            if match.group('release_candidate'):
                string_version += "_rc{}".format( match.group('release_candidate') )

            # All files are now available from archives.boost.io.
            return "https://archives.boost.io/release/{numeric_version}/source/boost_{string_version}{extension}".format(
                        numeric_version = numeric_version,
                        string_version = string_version,
                        extension = extension
                    )
    return location
