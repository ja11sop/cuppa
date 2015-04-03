
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)


def run( *args, **kwargs ):
    import cuppa.core
    cuppa.core.run( *args, **kwargs )


def add_option( *args, **kwargs ):
    import cuppa.core
    cuppa.core.add_option( *args, **kwargs )


import cuppa.build_with_header_library

from cuppa.build_with_header_library import header_library_dependency
