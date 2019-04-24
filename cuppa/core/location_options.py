#          Copyright Jamie Allsop 2018-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Location Options
#-------------------------------------------------------------------------------


def add_location_options( add_option ):

    add_option( '--develop',dest='develop', action='store_true',
                            help="Tell all locations to use their develop location if specified" )


def process_location_options( cuppa_env ):

    cuppa_env['develop'] = cuppa_env.get_option( 'develop' )
