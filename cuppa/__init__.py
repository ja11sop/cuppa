
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)


def run( *args, **kwargs ):
    from inspect import getframeinfo, stack
    caller = getframeinfo(stack()[1][0])
    sconsctruct_path = caller.filename
    import cuppa.core
    cuppa.core.run( sconsctruct_path, *args, **kwargs )


def add_option( *args, **kwargs ):
    import cuppa.core
    cuppa.core.add_option( *args, **kwargs )


import cuppa.build_with_location

from cuppa.build_with_location import location_dependency
from cuppa.build_with_location import location_dependency as header_library_dependency

import cuppa.build_with_profile

from cuppa.build_with_profile import profile
