#          Copyright Jamie Allsop 2018-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Location Options
#-------------------------------------------------------------------------------

# Python Standard
# None


# Custom
import cuppa.core.options


def add_location_options():

    add_option = cuppa.core.options.add_option

    add_option( '--download-root', type='string', nargs=1, action='store',
                            dest='download_root',
                            help="The root directory for downloading external libraries to."
                                 " If not specified then _cuppa is used" )

    add_option( '--cache-root', type='string', nargs=1, action='store',
                            dest='cache_root',
                            help="The root directory for caching downloaded external archived libraries."
                                 " If not specified then ~/_cuppa/cache is used" )
