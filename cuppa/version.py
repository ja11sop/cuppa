#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   version.py
#-------------------------------------------------------------------------------


import sys
import os
import xmlrpclib
import pip
from pkg_resources import parse_version


def get_version():
    module = sys.modules[__name__]
    if not hasattr( module, '_version' ):
        version_path = os.path.join( os.path.split( __file__ )[0], 'VERSION' )
        with open( version_path ) as version_file:
            module._version = version_file.read().strip()
    return module._version


def check_current_version():

    installed_version = get_version()
    sys.stdout.write( "cuppa: version {}".format( installed_version ) )
    try:
        pypi = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
        latest_available = pypi.package_releases('cuppa')[0]
        if parse_version( installed_version ) < parse_version( latest_available ):
            sys.stdout.write( " - " )
            sys.stdout.write( "Newer version [{}] available\n".format( latest_available ) )
        else:
            sys.stdout.write( "\n" )
    except:
        pass
