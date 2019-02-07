#          Copyright Jamie Allsop 2011-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Base Options
#-------------------------------------------------------------------------------

# Python Standard
# None

# Scons
import SCons.Script

# Custom
import cuppa.core.options
import cuppa.core.storage_options
import cuppa.core.location_options



SCons.Script.Decider( 'MD5-timestamp' )


def set_base_options():
    SCons.Script.SetOption( 'warn', 'no-duplicate-environment' )


def add_base_options():

    add_option = cuppa.core.options.add_option

    add_option( '--cuppa-mode', dest='cuppa-mode', action='store_true',
                            help="Runs scons as if called through cuppa. Implicitly set when ran from cuppa" )

    add_option( '--raw-output', dest='raw_output', action='store_true',
                            help="Disable output processing like colourisation of output" )

    add_option( '--standard-output', dest='standard_output', action='store_true',
                            help="Perform standard output processing but not colourisation of output" )

    add_option( '--minimal-output', dest='minimal_output', action='store_true',
                            help="Show only errors and warnings in the output" )

    add_option( '--ignore-duplicates', dest='ignore_duplicates', action='store_true',
                            help="Do not show repeated errors or warnings" )

    add_option( '--offline', dest='offline', action='store_true',
                            help="Run in offline mode so don't attempt to check the cuppa version or update"
                                 " remote repositories. Useful for running builds on firewalled machines" )

    add_option( '--projects', type='string', nargs=1,
                            action='callback', callback=cuppa.core.options.list_parser( 'projects' ),
                            help="Projects to build (alias for scripts)" )

    add_option( '--scripts', type='string', nargs=1,
                            action='callback', callback=cuppa.core.options.list_parser( 'projects' ),
                            help="Sconscripts to run" )

    add_option( '--thirdparty', type='string', nargs=1, action='store',
                            dest='thirdparty',
                            metavar='DIR',
                            help="Thirdparty directory" )

    add_option( '--runner', type='string', nargs=1, action='store',
                            dest='runner',
                            help="The test runner to use for executing tests. The default is the"
                                 " process test runner" )

    add_option( '--dump',   dest='dump', action='store_true',
                            help="Dump the default environment and exit" )

    add_option( '--parallel', dest='parallel', action='store_true',
                            help="Enable parallel builds utilising the available concurrency."
                                 " Translates to -j N with N chosen based on the current hardware" )

    add_option( '--show-test-output', dest='show-test-output', action='store_true',
                            help="When executing tests display all outout to stdout and stderr as appropriate" )

    add_option( '--suppress-process-output', dest='suppress-process-output', action='store_true',
                            help="When executing processes suppress all output to stdout and stderr" )

    verbosity_choices = ( 'trace', 'debug', 'exception', 'info', 'warn', 'error' )

    add_option( '--verbosity', dest='verbosity', choices=verbosity_choices, nargs=1, action='store',
                            help="The verbosity level that you wish to run cuppa at. The default level"
                                 " is \"info\". VERBOSITY may be one of {}".format( str(verbosity_choices) ) )

    add_option( '--enable-thirdparty-logging', dest='enable-thirdparty-logging', action='store_true',
                            help="Enables log messages from thirdparty modules that cuppa uses, for example from pip" )

    add_option( '--propagate-env', dest='propagate-env', action='store_true',
                            help="Propagate the current environment including PATH to all sub-processes when"
                                 " building" )

    add_option( '--propagate-path', dest='propagate-path', action='store_true',
                            help="Propagate the current environment PATH (only) to all sub-processes when"
                                 " building" )

    add_option( '--merge-path', dest='merge-path', action='store_true',
                            help="Merge the current environment PATH (only) to all sub-processes when"
                                 " building" )

    add_option( '--use-shell', dest='use-shell', action='store_true',
                            help="Setting to true means all subprocess calls are called with Shell=True" )

#    add_option( '--b2',     dest='b2', action='store_true',
#                            help='Execute boost.build by calling b2 or bjam' )

#    add_option( '--b2-path', type='string', nargs=1, action='store',
#                            dest='b2_path',
#                            help='Specify a path to bjam or b2' )

    decider_choices = ( 'timestamp-newer', 'timestamp-match', 'MD5', 'MD5-timestamp' )

    add_option( '--decider', dest='decider', choices=decider_choices, nargs=1, action='store',
                            help="The decider to use for determining if a dependency has changed."
                                 " Refer to the Scons manual for more details. By default \"MD5-timestamp\""
                                 " is used. DECIDER may be one of {}".format( str(decider_choices) ) )

    cuppa.core.storage_options.add_storage_options( add_option )

    cuppa.core.location_options.add_location_options( add_option )
