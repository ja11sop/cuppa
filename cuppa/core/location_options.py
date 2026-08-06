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

    add_option( '--location-base-branch', dest='location_base_branch', nargs=1, action='store',
                type='string', default=None,
                help="Develop home branch: where --checkout-develop-branch creates a missing"
                     " feature branch from, and where bare --reset-develop-branch returns."
                     " When unset, defaults to --location-default-branch. Use this for a"
                     " long-running integration line that is not the published default." )

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

    add_option( '--list-develop', dest='list_develop', action='store_true',
                help="Report the state of the local working copies that --develop builds against,"
                     " and exit. Shows the branch each copy is on, whether it is behind its"
                     " upstream as of your last fetch, and whether it has uncommitted or unpushed"
                     " work, warning where that will not be visible to a build that does not use"
                     " --develop. No remote is contacted." )

    add_option( '--clone-develop', dest='clone_develop', action='store_true',
                help="Clone each configured develop path that is missing or empty from the"
                     " dependency's unexpanded git URL, check out a branch that --list-develop"
                     " will call ok, and exit. Recurses submodules. Refuses non-empty destinations"
                     " and tag/revision pins. Not available with --offline." )

    add_option( '--checkout-develop-branch', dest='checkout_develop_branch', action='store',
                metavar='NAME',
                help="Switch every develop git working copy to branch NAME (create it if needed)."
                     " Use NAME=current for the consumer project's current branch. Clean copies"
                     " left on a stale feature branch move via the develop base branch + pull"
                     " first. Dirty or unpushed copies are left alone and reported. Not available"
                     " with --offline." )

    add_option( '--reset-develop-branch', dest='reset_develop_branch', nargs='?',
                action='store', type='string', const='__BASE__', default=None, metavar='NAME',
                help="Return each develop git working copy to a branch, then fetch and"
                     " fast-forward where safe (same gates as --update-develop). Bare flag or"
                     " NAME=base uses --location-base-branch (else the published default)."
                     " NAME=current uses the consumer project's branch; NAME=default uses"
                     " --location-default-branch; any other NAME is taken literally. Does not"
                     " delete leftover feature branches. Not available with --offline." )

    add_option( '--update-develop', dest='update_develop', action='store_true',
                help="Fetch each local working copy used by --develop and fast-forward the ones"
                     " that are clean and behind their upstream, then exit. Copies that are"
                     " modified, ahead, diverged or detached are left alone and reported."
                     " Nothing is stashed, reset or switched. Not available with --offline." )


def process_location_options( cuppa_env ):

    cuppa_env['develop']                          = cuppa_env.get_option( 'develop' )
    cuppa_env['list_develop']                     = cuppa_env.get_option( 'list_develop' )
    cuppa_env['clone_develop']                    = cuppa_env.get_option( 'clone_develop' )
    cuppa_env['checkout_develop_branch']          = cuppa_env.get_option( 'checkout_develop_branch' )
    cuppa_env['reset_develop_branch']             = cuppa_env.get_option( 'reset_develop_branch' )
    cuppa_env['update_develop']                   = cuppa_env.get_option( 'update_develop' )
    cuppa_env['location_default_branch']          = cuppa_env.get_option( 'location_default_branch' )
    cuppa_env['location_base_branch']             = cuppa_env.get_option( 'location_base_branch' )
    cuppa_env['location_match_current_branch']    = cuppa_env.get_option( 'location_match_current_branch' )
    cuppa_env['location_explicit_default_branch'] = cuppa_env.get_option( 'location_explicit_default_branch' )
    cuppa_env['location_match_branch']            = cuppa_env.get_option( 'location_match_branch' )
    cuppa_env['location_match_tag']               = cuppa_env.get_option( 'location_match_tag' )
