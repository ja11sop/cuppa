
#          Copyright Jamie Allsop 2011-2019
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

from cuppa.colourise          import as_info, as_notice
from cuppa.log                import logger
from cuppa.utility.python2to3 import maketrans

# Boost Imports
from cuppa.dependencies.boost.boost_exception import BoostException
from cuppa.dependencies.boost.patch_boost     import apply_patch_if_needed



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

    if patched:
        apply_patch_if_needed( boost_location.local(), get_boost_version ( boost_location.local() )[0] )

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



def _determine_latest_boost_verion( offline ):
    current_release = "1.71.0"
    if not offline:
        try:
            boost_version_url = 'https://www.boost.org/users/download/'
            logger.info( "Checking current boost version from {}...".format( as_info( boost_version_url ) ) )
            html = lxml.html.parse( urlopen( boost_version_url ) )

            current_release = html.xpath("/html/body/div[2]/div/div[1]/div/div/div[2]/h3[1]/span")[0].text
            current_release = str( re.search( r'(\d[.]\d+([.]\d+)?)', current_release ).group(1) )

            logger.info( "Latest boost release detected as [{}]".format( as_info( current_release ) ) )

        except Exception as e:
            logger.warn( "Cannot determine latest version of boost - [{}]. Assuming [{}].".format( str(e), current_release ) )
    else:
        logger.info( "In offline mode. No version of boost specified so assuming [{}]".format( as_info( current_release ) ) )

    return current_release



def _location_from_boost_version( location, offline ):
    if location == "latest" or location == "current":
        location = _determine_latest_boost_verion( offline )
    if location:
        match = re.match( r'(boost_)?(?P<version>\d[._]\d\d(?P<minor>[._]\d)?)', location )
        if match:
            version = match.group('version')
            if not match.group('minor'):
                version += "_0"
            logger.debug( "Only boost version specified, retrieve from SourceForge if not already cached" )
            extension = ".tar.gz"
            if cuppa.build_platform.name() == "Windows":
                extension = ".zip"

            # Boost 1.71.0 source files are missing from the sourceforge repository.
            if "1.71" in version:
                return "https://dl.bintray.com/boostorg/release/{numeric_version}/source/boost_{string_version}{extension}".format(
                            numeric_version = version.translate( maketrans( '._', '..' ) ),
                            string_version = version.translate( maketrans( '._', '__' ) ),
                            extension = extension
                        )
            return "http://sourceforge.net/projects/boost/files/boost/{numeric_version}/boost_{string_version}{extension}/download".format(
                        numeric_version = version.translate( maketrans( '._', '..' ) ),
                        string_version = version.translate( maketrans( '._', '__' ) ),
                        extension = extension
                    )
    return location
