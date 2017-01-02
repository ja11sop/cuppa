#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   version.py
#-------------------------------------------------------------------------------

import xmlrpclib
from pkg_resources import parse_version

from cuppa.colourise import as_info, as_warning, as_emphasised
from cuppa.log import logger
from cuppa.utility.version import get_version


def check_current_version():

    installed_version = get_version()
    logger.info( "cuppa: version {}".format( as_info( installed_version ) ) )
    try:
        pypi = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
        latest_available = pypi.package_releases('cuppa')[0]
        if parse_version( installed_version ) < parse_version( latest_available ):
            logger.warn( "Newer version [{}] available. Upgrade using \"{}\"\n".format(
                    as_warning( latest_available ),
                    as_emphasised( "pip install -U cuppa" )
            ) )
    except:
        pass
