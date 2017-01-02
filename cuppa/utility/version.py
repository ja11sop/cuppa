#          Copyright Jamie Allsop 2017-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   version.py
#-------------------------------------------------------------------------------

import sys
import os


def get_version():
    module = sys.modules[__name__]
    if not hasattr( module, '_version' ):
        version_path = os.path.join( os.path.split( __file__ )[0], '../VERSION' )
        with open( version_path ) as version_file:
            module._version = version_file.read().strip()
    return module._version

