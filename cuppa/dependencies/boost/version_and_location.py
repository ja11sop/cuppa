
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

from packaging import version as packaging_version

try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen

# Cuppa Imports
import cuppa.build_platform
import cuppa.location

from cuppa.colourise          import as_info, as_notice
from cuppa.log                import logger
from cuppa.utility.python2to3 import maketrans

# Boost Imports
from cuppa.dependencies.boost.boost_exception import BoostException
from cuppa.dependencies.boost.patch_boost     import apply_patches_if_needed


def current_boost_release():
    return "1.89.0"


def boost_location_id( env ):

    location   = env.get_option( 'boost-location' )
    home       = env.get_option( 'boost-home' )
    version    = env.get_option( 'boost-version' )
    latest     = env.get_option( 'boost-latest' )
    thirdparty = env[ 'thirdparty' ]
    patch_test = env.get_option( 'boost-patch-boost-test' )

    base = None

    if location:
        base = None

    elif home:
        base = home

    elif thirdparty and version:
        base = thirdparty

    elif version:
        base = None

    elif latest:
        version = "latest"

    if not base and not version and not location:
        version = "latest"

    return ( location, version, base, patch_test )


def _home_from_path( path ):
    if os.path.exists( path ) and os.path.isdir( path ):
        return path
    return None


def get_boost_location( env, location, version, base, patched ):
    logger.debug( "Identify boost using location = [{}], version = [{}], base = [{}], patched = [{}]".format(
            as_info( str(location) ),
            as_info( str(version) ),
            as_info( str(base) ),
            as_info( str(patched) )
    ) )

    boost_home = None
    boost_location = None

    extra_sub_path = 'clean'
    if patched:
        extra_sub_path = 'patched'

    offline = env['offline']

    if location:
        location = _location_from_boost_version( location, offline )

        logger.trace( "Location after version detection = [{}]".format( as_notice( str(location) ) ) )

        if not location: # use version as a fallback in case both at specified
            location = _location_from_boost_version( version, offline )
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
        location = _location_from_boost_version( version, offline )
        boost_location = cuppa.location.Location( env, location, extra_sub_path=extra_sub_path )

    apply_patches_if_needed( patched, boost_location.local(), get_boost_version ( boost_location.local() )[0] )

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



def determine_latest_boost_version( offline ):
    current_release = current_boost_release()
    if not offline:
        try:
            boost_version_url = 'https://www.boost.org/releases/latest/'
            logger.info( "Checking current boost version from {}...".format( as_info( boost_version_url ) ) )
            html = lxml.html.parse( urlopen( boost_version_url ) )

            current_release = html.xpath("string()")
            current_release = str( re.search( r'(\d[.]\d+([.]\d+)?)', current_release ).group(1) )

            logger.info( "Latest boost release detected as [{}]".format( as_info( current_release ) ) )

        except Exception as e:
            logger.warn( "Cannot determine latest version of boost - [{}]. Assuming [{}].".format( str(e), current_release ) )
    else:
        logger.info( "In offline mode. No version of boost specified so assuming [{}]".format( as_info( current_release ) ) )

    return current_release



def _location_from_boost_version( location, offline ):
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
