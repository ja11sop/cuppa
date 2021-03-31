#          Copyright Jamie Allsop 2018-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Location Options
#-------------------------------------------------------------------------------


def add_location_options( add_option ):

    add_option( '--develop', dest='develop', action='store_true',
                help="Tell all locations to use their develop location if specified" )

    add_option( '--location-default-branch', dest='location_default_branch', nargs=1, action='store',
                default="master",
                help="Tell cuppa what the name of the default branch is so it can be used"
                     " correctly choose between default available branches and other branches"
                     " when operating in offline mode." )

    add_option( '--location-match-current-branch', dest='location_match_current_branch', action='store_true',
                help="If the current source is checked out on a particular branch then"
                     " any locations marked as \"relative\", that is, they are specified"
                     " as a location path but with an '@' symbol at the end of the path, then"
                     " attempt to check those locations out on the same branch, if it exists"
                     " or the default branch otherwise." )

    add_option( '--location-explicit-default-branch', dest='location_explicit_default_branch', action='store_true',
                help="When a remote repository is specified and no branching or tag information"
                     " is specified then the default branch will be cloned from the remote. This"
                     " information is not made explicit in the local location folder by default."
                     " Setting this option forces the default branch to be determined and used"
                     " explicitly where possible." )

    add_option( '--location-match-branch', dest='location_match_branch', nargs='?', action='store',
                help="For any locations that are marked as \"relative\", that is, they are specified"
                     " as a location path but with an '@' symbol at the end of the path, then"
                     " attempt to check those locations out on the same branch as specified, if it exists"
                     " or the default branch otherwise." )

    add_option( '--location-match-tag', dest='location_match_tag', nargs='?', action='store',
                help="For any locations that are marked as \"relative\", that is, they are specified"
                     " as a location path but with an '@' symbol at the end of the path, then"
                     " attempt to check those locations out on the same tag as specified, if it exists"
                     " or the default branch otherwise." )


def process_location_options( cuppa_env ):

    cuppa_env['develop']                          = cuppa_env.get_option( 'develop' )
    cuppa_env['location_default_branch']          = cuppa_env.get_option( 'location_default_branch' )
    cuppa_env['location_match_current_branch']    = cuppa_env.get_option( 'location_match_current_branch' )
    cuppa_env['location_explicit_default_branch'] = cuppa_env.get_option( 'location_explicit_default_branch' )
    cuppa_env['location_match_branch']            = cuppa_env.get_option( 'location_match_branch' )
    cuppa_env['location_match_tag']               = cuppa_env.get_option( 'location_match_tag' )
