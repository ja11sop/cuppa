#          Copyright Jamie Allsop 2011-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Construct
#-------------------------------------------------------------------------------

# Python Standard
import os.path
import os
import re
import fnmatch
import multiprocessing
import pkg_resources
import six
from urllib.parse import urlparse

# Scons
import SCons.Script

# Custom
import cuppa.core.environment
import cuppa.core.base_options
import cuppa.core.storage_options
import cuppa.core.location_options
import cuppa.core.options
import cuppa.modules.registration
import cuppa.build_platform
import cuppa.output_processor
import cuppa.recursive_glob
import cuppa.configure
import cuppa.version
import cuppa.scms
#import cuppa.progress
#import cuppa.tree
#import cuppa.cpp.stdcpp

from cuppa.colourise import colouriser, as_emphasised, as_info, as_error, as_notice, colour_items, as_info_label
from cuppa.log import set_logging_level, reset_logging_format, logger, enable_thirdparty_logging
from cuppa.utility.types import is_string

from cuppa.toolchains             import *
from cuppa.methods                import *
from cuppa.dependencies           import *
from cuppa.packages               import *
from cuppa.profiles               import *
from cuppa.variants               import *
from cuppa.project_generators     import *



class ConstructException(Exception):

    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)



class ParseToolchainsOption(object):

    def __init__( self, supported_toolchains, available_toolchains ):
        self._supported = supported_toolchains
        self._available = available_toolchains

    def __call__(self, option, opt, value, parser):
        toolchains = set()
        requested = value.split(',')
        for toolchain in requested:
            supported = fnmatch.filter( self._supported, toolchain )

            if not supported:
                logger.warn( "Requested toolchain [{}] does not match any supported, skipping".format( as_info(toolchain) ) )
            else:
                available = fnmatch.filter( self._available, toolchain )

                if not available:
                    logger.warn( "Requested toolchain [{}] does not match any available, skipping".format( as_info(toolchain) ) )
                else:
                    toolchains.update( available )

        if not toolchains:
            logger.error( "None of the requested toolchains are available" )

        parser.values.toolchains = list(toolchains)


#  class ParseTargetArchsOption(object):
#
#     def __init__( self, available_toolchains ):
#         self._available = available_toolchains
#
#     def __call__(self, option, opt, value, parser):
#         target_archs = set()
#         requested = value.split(',')
#         for target_arch in requested:
#             supported = fnmatch.filter( self._supported, toolchain )
#
#             if not supported:
#                 print "cuppa: requested toolchain(s) [{}] does not match any supported, skipping".format( toolchain )
#             else:
#                 available = fnmatch.filter( self._available, toolchain )
#
#                 if not available:
#                     print "cuppa: requested toolchain(s) [{}] supported does not match any available, skipping".format( toolchain )
#                 else:
#                     toolchains.update( available )
#
#         if not toolchains:
#             print "cuppa: None of the requested toolchains are available"
#
#         parser.values.toolchains = list(toolchains)



class Construct(object):

    platforms_key    = 'platforms'
    variants_key     = 'variants'
    actions_key      = 'actions'
    toolchains_key   = 'toolchains'
    dependencies_key = 'dependencies'
    packages_key     = 'packages'
    profiles_key     = 'profiles'
    methods_key      = 'methods'
    project_generators_key = 'project_generators'


    def add_platforms( self, env ):
        platforms = self.platforms_key
        env[platforms] = cuppa.build_platform.Platform.supported()


    def add_project_generators( self, env ):
        cuppa.modules.registration.add_to_env( self.project_generators_key, env )


    def add_variants( self, env ):
        variants = self.variants_key
        cuppa.modules.registration.add_to_env( variants, env, env.add_variant, env.add_action )
        cuppa.modules.registration.add_options( variants )


    def add_toolchains( self, env ):
        toolchains = self.toolchains_key
        cuppa.modules.registration.add_to_env( toolchains, env, env.add_available_toolchain, env.add_supported_toolchain )

        logger.trace( "supported toolchains are [{}]".format(
                colour_items( env["supported_toolchains"] )
        ) )
        logger.info( "available toolchains are [{}]".format(
                colour_items( sorted( env[toolchains].keys(), reverse=True ), as_info )
        ) )

        SCons.Script.AddOption(
            '--toolchains',
            type     = 'string',
            nargs    = 1,
            action   = 'callback',
            callback = ParseToolchainsOption( env['supported_toolchains'], env[toolchains].keys() ),
            help     = 'The Toolchains you wish to build against. A comma separated list with wildcards'
                       ' may be provided. For example --toolchains=gcc*,clang37,clang36'
        )

        # TODO
        # SCons.Script.AddOption(
            # '--target-arch',
            # type     = 'string',
            # nargs    = 1,
            # action   = 'callback',
            # callback = ParseTargetArchsOption( env[toolchains] ),
            # help = 'The Target Archictectures you wish to generate executables for. You may'
                   # ' specify a number a comma separated list of architectures. You may also'
                   # ' restrict an acrhitecture to a specific toolchain by prepending it with a'
                   # ' toolchain name followed by a ":". Only valid architectures for each toolchain'
                   # ' will be built. Example --target-arch=64,vc100:amd64,x86 is valid.'
        # )



    def initialise_options( self, options, default_options, profiles, dependencies ):
        options['default_options'] = default_options or {}
        # env.AddMethod( self.get_option, "get_option" )
        cuppa.core.base_options.add_base_options()
        cuppa.modules.registration.add_options( self.toolchains_key )
        cuppa.modules.registration.add_options( self.dependencies_key )
        cuppa.modules.registration.add_options( self.profiles_key )
        cuppa.modules.registration.add_options( self.project_generators_key )
        cuppa.modules.registration.add_options( self.methods_key )

        for method_plugin in pkg_resources.iter_entry_points( group='cuppa.method.plugins', name=None ):
            try:
                method_plugin.load().add_options( SCons.Script.AddOption )
            except AttributeError:
                pass

        if profiles:
            for profile in profiles:
                profile.add_options( SCons.Script.AddOption )

        for profile_plugin in pkg_resources.iter_entry_points( group='cuppa.profile.plugins', name=None ):
            try:
                profile_plugin.load().add_options( SCons.Script.AddOption )
            except AttributeError:
                pass

        if dependencies:
            for dependency in dependencies:
                dependency.add_options( SCons.Script.AddOption )

        for dependency_plugin in pkg_resources.iter_entry_points( group='cuppa.dependency.plugins', name=None ):
            try:
                dependency_plugin.load().add_options( SCons.Script.AddOption )
            except AttributeError:
                pass



    def print_construct_variables( self, env ):
        keys = {
                'raw_output',
                'standard_output',
                'minimal_output',
                'offline',
                'ignore_duplicates',
                'working_dir',
                'launch_dir',
                'launch_offset_dir',
                'run_from_launch_dir',
                'base_path',
                'branch_root',
                'branch_dir',
                'download_root',
                'cache_root',
                'thirdparty',
                'build_root',
                'default_dependencies',
                'BUILD_WITH',
                'dependencies',
                'sconscript_dir',
                'sconscript_file',
                'build_dir',
                'offset_dir',
                'parallel',
                'show_test_output',
                'propagate_env',
                'propagate_path',
                'decider'
        }

        for key in keys:
            if key in env:
                print( "cuppa: Env[%s] = %s" % ( key, env[key] ) )


    @classmethod
    def _set_verbosity_level( cls, cuppa_env ):
        verbosity = None

        ## Check if -Q was passed on the command-line
        scons_no_progress = cuppa_env.get_option( 'no_progress' )
        if scons_no_progress:
            verbosity = 'warn'

        ## Check if -s, --quiet or --silent was passed on the command-line
        scons_silent = cuppa_env.get_option( 'silent' )
        if scons_silent:
            verbosity = 'error'

        cuppa_verbosity = cuppa_env.get_option( 'verbosity' )
        if cuppa_verbosity:
            verbosity = cuppa_verbosity

        if verbosity:
            set_logging_level( verbosity )


    @classmethod
    def _set_output_format( cls, cuppa_env ):
        cuppa_env['raw_output']      = cuppa_env.get_option( 'raw_output' ) and True or False
        cuppa_env['standard_output'] = cuppa_env.get_option( 'standard_output' ) and True or False

        if not cuppa_env['raw_output'] and not cuppa_env['standard_output']:
            cuppa_env.colouriser().enable()
            reset_logging_format()


    @classmethod
    def _normalise_with_defaults( cls, values, default_values, name ):

        warning = None
        if isinstance( values, dict ):
            warning = "Dictionary passed for {}, this approach has been deprecated, please use a list instead".format( name )
            values = [ v for v in six.itervalues(values) ]

        default_value_objects = []
        default_value_names = []

        for value in default_values:
            if not is_string( value ):
                default_value_objects.append( value )
                try:
                    name = getattr( value, 'name' )
                    if callable( name ):
                        default_value_names.append( name() )
                    else:
                        default_value_names.append( value.__name__ )
                except:
                    default_value_names.append( value.__name__ )
            else:
                default_value_names.append( value )

        default_values = default_value_names
        values = values + default_value_objects

        return values, default_values, warning


    def __init__( self,
                  sconstruct_path,
                  base_path            = os.path.abspath( '.' ),
                  branch_root          = None,
                  default_options      = {},
                  default_projects     = [],
                  default_variants     = [],
                  default_dependencies = [],
                  default_profiles     = [],
                  dependencies         = [],
                  profiles             = [],
                  default_runner       = None,
                  configure_callback   = None,
                  tools                = [] ):

        cuppa.core.base_options.set_base_options()

        cuppa_env = cuppa.core.environment.CuppaEnvironment()
        cuppa_env.add_tools( tools )

        dependencies, default_dependencies, dependencies_warning = self._normalise_with_defaults( dependencies, default_dependencies, "dependencies" )
        profiles, default_profiles, profiles_warning = self._normalise_with_defaults( profiles, default_profiles, "profiles" )

        self.initialise_options( cuppa_env, default_options, profiles, dependencies )
        cuppa_env['configured_options'] = {}
        self._configure = cuppa.configure.Configure( cuppa_env, callback=configure_callback )

        enable_thirdparty_logging( cuppa_env.get_option( 'enable-thirdparty-logging' ) and True or False )
        self._set_verbosity_level( cuppa_env )

        cuppa_env['sconstruct_path'] = sconstruct_path
        cuppa_env['sconstruct_dir'], cuppa_env['sconstruct_file'] = os.path.split(sconstruct_path)

        self._set_output_format( cuppa_env )

        self._configure.load()

        cuppa_env['offline'] = cuppa_env.get_option( 'offline' )

        cuppa.version.check_current_version( cuppa_env['offline'] )

        if cuppa_env['offline']:
            logger.info( as_info_label( "Running in OFFLINE mode" ) )

        logger.info( "using sconstruct file [{}]".format( as_notice( cuppa_env['sconstruct_file'] ) ) )

        if dependencies_warning:
            logger.warn( dependencies_warning )

        if profiles_warning:
            logger.warn( profiles_warning )

        help = cuppa_env.get_option( 'help' ) and True or False

        cuppa_env['minimal_output']       = cuppa_env.get_option( 'minimal_output' )
        cuppa_env['ignore_duplicates']    = cuppa_env.get_option( 'ignore_duplicates' )

        cuppa_env['working_dir']          = os.getcwd()
        cuppa_env['launch_dir']           = os.path.relpath( SCons.Script.GetLaunchDir(), cuppa_env['working_dir'] )
        cuppa_env['run_from_launch_dir']  = cuppa_env['launch_dir'] == "."

        cuppa_env['launch_offset_dir']    = "."

        if not cuppa_env['run_from_launch_dir']:
            levels = len( cuppa_env['launch_dir'].split( os.path.sep ) )
            cuppa_env['launch_offset_dir'] = os.path.sep.join( ['..' for i in range(levels)] )

        cuppa_env['base_path']   = os.path.normpath( os.path.expanduser( base_path ) )
        cuppa_env['branch_root'] = branch_root and os.path.normpath( os.path.expanduser( branch_root ) ) or base_path
        cuppa_env['branch_dir']  = cuppa_env['branch_root'] and os.path.relpath( cuppa_env['base_path'], cuppa_env['branch_root'] ) or None

        thirdparty = cuppa_env.get_option( 'thirdparty' )
        if thirdparty:
            thirdparty = os.path.normpath( os.path.expanduser( thirdparty ) )

        cuppa_env['thirdparty'] = thirdparty

        cuppa.core.storage_options.process_storage_options( cuppa_env )
        cuppa.core.location_options.process_location_options( cuppa_env )

        cuppa_env['current_branch'] = ''
        cuppa_env['current_revision'] = ''
        if not help and not self._configure.handle_conf_only():

            url, repo, branch, remote, rev = cuppa.scms.scms.get_current_rev_info( cuppa_env['sconstruct_dir'] )
            cuppa_env['current_repo_path'] = urlparse( url )[2]
            if cuppa_env['current_repo_path']:
                if cuppa_env['current_repo_path'].startswith( "git@" ):
                    cuppa_env['current_repo_path'] = os.path.splitext( cuppa_env['current_repo_path'].split(":")[1] )[0]

                logger.info( "Current build is on branch [{}] at revision [{}] from remote [{}] in repo [{}] at url [{}] with path [{}]".format(
                            as_info( str(branch) ),
                            as_info( str(rev) ),
                            as_info( str(remote) ),
                            as_info( str(repo) ),
                            as_info( str(url) ),
                            as_info( cuppa_env['current_repo_path'] )
                ) )

                if cuppa_env['location_match_current_branch']:
                    logger.info( "Setting [{}] is set".format( as_info( "location_match_current_branch" ) ) )
                    if branch:
                        cuppa_env['current_branch'] = branch
                    if rev:
                        cuppa_env['current_revision'] = rev
                elif cuppa_env['location_match_branch']:
                    logger.info( "Setting [{}] is set".format( as_info( "location_match_branch" ) ) )
                    logger.info( "Build will attempt to build against repositories using the explicitly chosen branch [{}]".format(
                            as_info( str(cuppa_env['location_match_branch']) )
                    ) )
                    cuppa_env['current_branch'] = cuppa_env['location_match_branch']
                elif cuppa_env['location_match_tag']:
                    logger.info( "Setting [{}] is set".format( as_info( "location_match_tag" ) ) )
                    logger.info( "Build will attempt to build against repositories using the explicitly chosen tag [{}]".format(
                            as_info( str(cuppa_env['location_match_tag']) )
                    ) )
                    cuppa_env['current_revision'] = cuppa_env['location_match_tag']
                else:
                    cuppa_env['current_branch'] = branch and branch or ''
                    cuppa_env['current_revision'] = rev and rev or ''

        cuppa_env['default_projects']     = default_projects
        cuppa_env['default_variants']     = default_variants and set( default_variants ) or set()
        cuppa_env['default_dependencies'] = default_dependencies and default_dependencies or []
        cuppa_env['BUILD_WITH']           = cuppa_env['default_dependencies']
        cuppa_env['dependencies']         = {}
        cuppa_env['default_profiles']     = default_profiles and default_profiles or []
        cuppa_env['BUILD_PROFILE']        = cuppa_env['default_profiles']
        cuppa_env['profiles']             = {}

        test_runner = cuppa_env.get_option( 'runner', default=default_runner and default_runner or 'process' )
        cuppa_env['default_runner']  = test_runner

        cuppa_env['propagate_env']       = cuppa_env.get_option( 'propagate-env' )       and True or False
        cuppa_env['propagate_path']      = cuppa_env.get_option( 'propagate-path' )      and True or False
        cuppa_env['merge_path']          = cuppa_env.get_option( 'merge-path' )          and True or False
        cuppa_env['show_test_output']    = cuppa_env.get_option( 'show-test-output' )    and True or False
        cuppa_env['suppress_process_output'] = cuppa_env.get_option( 'suppress-process-output' ) and True or False
        cuppa_env['dump']                = cuppa_env.get_option( 'dump' )                and True or False
        cuppa_env['clean']               = cuppa_env.get_option( 'clean' )               and True or False

        self.add_variants   ( cuppa_env )
        self.add_toolchains ( cuppa_env )
        self.add_platforms  ( cuppa_env )

        cuppa_env['platform'] = cuppa.build_platform.Platform.current()

        toolchains = cuppa_env.get_option( 'toolchains' )
        cuppa_env[ 'target_architectures' ] = None

        if not help and not self._configure.handle_conf_only():
            default_toolchain = cuppa_env['platform'].default_toolchain()

            if not toolchains:
                toolchains = [ cuppa_env[self.toolchains_key][default_toolchain] ]
            else:
                toolchains = [ cuppa_env[self.toolchains_key][t] for t in toolchains ]

            cuppa_env['active_toolchains'] = toolchains

            def add_profile( name, profile ):
                cuppa_env['profiles'][name] = profile

            def add_dependency( name, dependency ):
                cuppa_env['dependencies'][name] = dependency

            cuppa.modules.registration.get_options( "methods", cuppa_env )

            if not help and not self._configure.handle_conf_only():
                cuppa_env[self.project_generators_key] = {}
                cuppa.modules.registration.add_to_env( "dependencies",       cuppa_env, add_dependency )
                cuppa.modules.registration.add_to_env( "profiles",           cuppa_env, add_profile )
                cuppa.modules.registration.add_to_env( "methods",            cuppa_env )
                cuppa.modules.registration.add_to_env( "project_generators", cuppa_env )

                for method_plugin in pkg_resources.iter_entry_points( group='cuppa.method.plugins', name=None ):
                    method_plugin.load().add_to_env( cuppa_env )

                for profile_plugin in pkg_resources.iter_entry_points( group='cuppa.profile.plugins', name=None ):
                    profile_plugin.load().add_to_env( cuppa_env )

                if profiles:
                    for profile in profiles:
                        profile.add_to_env( cuppa_env, add_profile )

                logger.trace( "available profiles are [{}]".format(
                        colour_items( sorted( cuppa_env["profiles"].keys() ) )
                ) )

                logger.info( "default profiles are [{}]".format(
                        colour_items( sorted( cuppa_env["default_profiles"] ), as_info )
                ) )

                for dependency_plugin in pkg_resources.iter_entry_points( group='cuppa.dependency.plugins', name=None ):
                    dependency_plugin.load().add_to_env( cuppa_env, add_dependency )

                if dependencies:
                    for dependency in dependencies:
                        dependency.add_to_env( cuppa_env, add_dependency )


                logger.trace( "available dependencies are [{}]".format(
                        colour_items( sorted( cuppa_env["dependencies"].keys() ) )
                ) )

                logger.info( "default dependencies are [{}]".format(
                        colour_items( sorted( cuppa_env["default_dependencies"] ), as_info )
                ) )


            # TODO - default_profile

            if cuppa_env['dump']:
                logger.info( as_info_label( "Running in DUMP mode, no building will be attempted" ) )
                cuppa_env.dump()

            job_count = cuppa_env.get_option( 'num_jobs' )
            parallel  = cuppa_env.get_option( 'parallel' )
            parallel_mode = "manually"

            if job_count==1 and parallel:
                job_count = multiprocessing.cpu_count()
                if job_count > 1:
                    SCons.Script.SetOption( 'num_jobs', job_count )
                    parallel_mode = "automatically"
            cuppa_env['job_count'] = job_count
            cuppa_env['parallel']  = parallel
            if job_count>1:
                logger.info( "Running in {} with option [{}] set {} as [{}]".format(
                        as_emphasised("parallel mode"),
                        as_info( "jobs" ),
                        as_emphasised(parallel_mode),
                        as_info( str( SCons.Script.GetOption( 'num_jobs') ) )
                ) )

        if not help and self._configure.handle_conf_only():
            self._configure.save()

        if not help and not self._configure.handle_conf_only():
            self.build( cuppa_env )

        if self._configure.handle_conf_only():
            print( "cuppa: Handling configuration only, so no builds will be attempted." )
            print( "cuppa: With the current configuration executing 'cuppa -D' would be equivalent to:" )
            print( "" )
            print( "cuppa -D {}".format( self._command_line_from_settings( cuppa_env['configured_options'] ) ) )
            print( "" )
            print( "cuppa: Nothing to be done. Exiting." )
            SCons.Script.Exit()


    def _command_line_from_settings( self, settings ):
        commands = []
        for key, value in six.iteritems(settings):
            command = as_emphasised( "--" + key )
            if value != True and value != False:
                if not isinstance( value, list ):
                    command += "=" + as_info( str(value) )
                else:
                    command += "=" + as_info( ",".join( value ) )
            commands.append( command )
        commands.sort()
        return " ".join( commands )


    def get_active_actions( self, cuppa_env, current_variant, active_variants, active_actions ):
        available_variants = cuppa_env[ self.variants_key ]
        available_actions  = cuppa_env[ self.actions_key ]
        specified_actions  = {}

        for key, action in available_actions.items():
            if cuppa_env.get_option( action.name() ) or action.name() in active_actions:
                specified_actions[ action.name() ] = action

        if not specified_actions:
            if active_variants:
                for variant_name in active_variants:
                    if variant_name in available_actions.keys():
                        specified_actions[ variant_name ] = available_actions[ variant_name ]

        active_actions = {}

        for key, action in specified_actions.items():
            if key not in available_variants:
                active_actions[ key ] = action
            elif key == current_variant.name():
                active_actions[ key ] = action

        logger.debug( "Specifying active_actions of [{}] for variant [{}]".format( colour_items( specified_actions, as_info ), current_variant.name() ) )

        return active_actions


    def propagate_env_variables( self, env, variant, target_arch, propagate_environment, propagate_path, merge_path ):

        def get_paths_from( environment, variable='PATH' ):
            return variable in environment and environment[variable].split(os.pathsep) or []

        # Always propagate PKG_CONFIG_PATH as this will be needed to discover packages on
        # the system
        pkg_config_paths = get_paths_from( os.environ, variable='PKG_CONFIG_PATH' )
        if pkg_config_paths:
            env['ENV']['PKG_CONFIG_PATH'] = pkg_config_paths
            logger.debug( "propagating PKG_CONFIG_PATH for [{}:{}] to all subprocesses: [{}]".format(
                    variant.name(),
                    target_arch,
                    colour_items( pkg_config_paths ) )
            )

        if propagate_environment or propagate_path or merge_path:

            def merge_paths( default_paths, env_paths ):
                path_set = set( default_paths + env_paths )
                def record_path( path ):
                    path_set.discard(path)
                    return path
                return [ record_path(p) for p in default_paths + env_paths if p in path_set ]

            default_paths = get_paths_from( env['ENV'] )
            env_paths = get_paths_from( os.environ )
            if propagate_environment:
                env['ENV'] = os.environ.copy()
                logger.debug( "propagating environment for [{}:{}] to all subprocesses: [{}]".format(
                        variant.name(),
                        target_arch,
                        as_notice( str(env['ENV']) ) )
                )
            if propagate_path and not propagate_environment:
                env['ENV']['PATH'] = env_paths
                logger.debug( "propagating PATH for [{}:{}] to all subprocesses: [{}]".format(
                        variant.name(),
                        target_arch,
                        colour_items( env_paths ) )
                )
            elif merge_path:
                merged_paths = merge_paths( default_paths, env_paths )
                env['ENV']['PATH'] = os.pathsep.join( merged_paths )
                logger.debug( "merging PATH for [{}:{}] to all subprocesses: [{}]".format(
                        variant.name(),
                        target_arch,
                        colour_items( merged_paths ) )
                )


    def create_build_envs( self, toolchain, cuppa_env ):

        variants = cuppa_env[ self.variants_key ]
        actions  = cuppa_env[ self.actions_key ]

        target_architectures = cuppa_env[ 'target_architectures' ]

        if not target_architectures:
            target_architectures = [ None ]

        def get_active_from_options( tasks ):
            active_tasks = {}
            for key, task in tasks.items():
                if cuppa_env.get_option( task.name() ):
                    active_tasks[ task.name() ] = task
            return active_tasks

        active_variants = get_active_from_options( variants )
        active_actions  = get_active_from_options( actions )

        def get_active_from_defaults( default_tasks, tasks ):
            active_tasks = {}
            for task in default_tasks:
                if task in tasks.keys():
                    active_tasks[ task ] = tasks[ task ]
            return active_tasks

        if not active_variants and not active_actions:
            default_variants = cuppa_env['default_variants'] or toolchain.default_variants()
            if default_variants:
                active_variants = get_active_from_defaults( default_variants, variants )
                active_actions = get_active_from_defaults( default_variants, actions )
                if active_variants:
                    logger.info( "Default build variants of [{}] being used.".format( colour_items( active_variants, as_info ) ) )
                if active_actions:
                    logger.info( "Default build actions of [{}] being used.".format( colour_items( active_actions, as_info ) ) )

        if not active_variants:
            active_variants = get_active_from_defaults( toolchain.default_variants(), variants )
            logger.info( "No active variants specified so toolchain defaults of [{}] being used.".format( colour_items( active_variants, as_info ) ) )

        logger.debug( "Using active_variants = [{}]".format( colour_items( active_variants, as_info ) ) )
        logger.debug( "Using active_actions = [{}]".format( colour_items( active_actions, as_info ) ) )

        def sanitise_abi( abi ):
            return abi.replace( "+", "x" )

        build_envs = []

        for key, variant in active_variants.items():

            for target_arch in target_architectures:

                env, target_arch = toolchain.make_env( cuppa_env, variant, target_arch )

                if env:

                    abi = sanitise_abi( toolchain.abi( env ) )

                    self.propagate_env_variables(
                            env,
                            variant,
                            target_arch,
                            cuppa_env['propagate_env'],
                            cuppa_env['propagate_path'],
                            cuppa_env['merge_path']
                    )

                    build_envs.append( {
                        'variant': key,
                        'target_arch': target_arch,
                        'abi': abi,
                        'raw_abi': toolchain.abi( env ),
                        'env': env } )

                    if not cuppa_env['raw_output']:
                        cuppa.output_processor.Processor.install( env )

                    env['toolchain']       = toolchain
                    env['variant']         = variant
                    env['target_arch']     = target_arch
                    env['abi']             = sanitise_abi( toolchain.abi( env ) )
                    env['raw_abi']         = toolchain.abi( env )
                    env['variant_actions'] = self.get_active_actions( cuppa_env, variant, active_variants, active_actions )

        return build_envs


    def get_sub_sconscripts( self, path, exclude_dirs ):
        file_regex = re.compile( r'([^.]+[.])?sconscript$', re.IGNORECASE )
        discard_if_subdir_contains_regex = re.compile( r'(SC|Sc|sc)onstruct' )

        def up_dir( path ):
            element = next( e for e in path.split(os.path.sep) if e )
            return element == ".."

        exclude_dirs = [ re.escape(d) for d in exclude_dirs if not os.path.isabs(d) and not up_dir(d) ]
        exclude_dirs = "|".join( exclude_dirs )
        exclude_dirs_regex = re.compile( exclude_dirs, re.IGNORECASE )

        return cuppa.recursive_glob.glob(
                path,
                file_regex,
                exclude_dirs_pattern= exclude_dirs_regex,
                discard_pattern=discard_if_subdir_contains_regex
        )


#    def on_progress( self, progress, sconscript, variant, env, target, source ):
#        if progress == 'begin':
#            self.on_sconscript_begin( env, sconscript )
#        elif progress == 'started':
#            self.on_variant_started( env, sconscript, target, source )
#        elif progress == 'finished':
#            self.on_variant_finished( sconscript, target, source )
#        elif progress == 'end':
#            self.on_sconscript_end( sconscript )
#        elif progress =='sconstruct_end':
#            self.on_sconstruct_end( env )
#
#    def on_sconscript_begin( self, env, sconscript ):
#        pass
#
#    def on_variant_started( self, env, sconscript, target, source ):
#        pass
#
#    def on_variant_finished( self, sconscript, root_node, source ):
#        pass
#        #cuppa.tree.print_tree( root_node )
#
#    def on_sconscript_end( self, sconscript ):
#        pass
#
#    def on_sconstruct_end( self, env ):
#        pass


    def build( self, cuppa_env ):

#        cuppa.progress.NotifyProgress.register_callback( None, self.on_progress )

        cuppa_env['empty_env'] = cuppa_env.create_env()
        projects   = cuppa_env.get_option( 'projects' )
        toolchains = cuppa_env['active_toolchains']

        if not projects:
            projects = cuppa_env['default_projects']

            if not projects or not cuppa_env['run_from_launch_dir']:
                sub_sconscripts = self.get_sub_sconscripts(
                        cuppa_env['launch_dir'],
                        [ cuppa_env['build_root'], cuppa_env['download_root'] ]
                )
                if sub_sconscripts:
                    projects = sub_sconscripts
                    logger.info( "Using sub-sconscripts [{}]".format( colour_items( projects ) ) )
            elif projects:
                logger.info( "Using default_projects [{}]".format( colour_items( projects ) ) )

        if projects:

            sconscripts = []

            for project in projects:

                if(     not os.path.exists( project )
                    and not cuppa_env['run_from_launch_dir']
                    and not os.path.isabs( project ) ):

                    path = os.path.join( cuppa_env['launch_dir'], project )

                    if os.path.exists( path ):
                        if os.path.isdir( path ):
                            sub_sconscripts = self.get_sub_sconscripts(
                                project,
                                [ cuppa_env['build_root'], cuppa_env['download_root'] ]
                            )
                            if sub_sconscripts:
                                logger.info( "Reading project folder [{}] and using sub-sconscripts [{}]".format(
                                        project, colour_items( sub_sconscripts )
                                ) )
                                sconscripts.extend( sub_sconscripts )
                        else:
                            sconscripts.append( path )

                elif os.path.exists( project ) and os.path.isdir( project ):
                    sub_sconscripts = self.get_sub_sconscripts(
                            project,
                            [ cuppa_env['build_root'], cuppa_env['download_root'] ]
                    )
                    if sub_sconscripts:
                        logger.info( "Reading project folder [{}] and using sub-sconscripts [{}]".format(
                                project, colour_items( sub_sconscripts )
                        ) )
                        sconscripts.extend( sub_sconscripts )
                else:
                    sconscripts.append( project )

            for toolchain in toolchains:
                build_envs = self.create_build_envs( toolchain, cuppa_env )
                for build_env in build_envs:
                    for sconscript in sconscripts:
                        decider = cuppa_env.get_option( 'decider' )
                        if decider:
                            build_env['env'].Decider( decider )
                        self.call_project_sconscript_files( toolchain, build_env['variant'], build_env['target_arch'], build_env['abi'], build_env['env'], sconscript )

            if cuppa_env['dump']:
                print( "cuppa: Performing dump only, so no builds will be attempted." )
                print( "cuppa: Nothing to be done. Exiting." )
                SCons.Script.Exit()

        else:
            logger.warn( "No projects to build. Nothing to be done" )


    def call_project_sconscript_files( self, toolchain, variant, target_arch, abi, sconscript_env, project ):

        sconscript_file = project

        if os.path.exists( sconscript_file ) and os.path.isfile( sconscript_file ):

            logger.debug( "project exists and added to build [{}] using [{},{},{}]".format(
                    as_notice( sconscript_file ),
                    as_notice( toolchain.name() ),
                    as_notice( variant ),
                    as_notice( target_arch )
            ) )

            path_without_ext = os.path.splitext( sconscript_file )[0]

            sconstruct_offset_path, sconscript_name = os.path.split( sconscript_file )

            name = os.path.splitext( sconscript_name )[0]
            sconscript_env['sconscript_name_id'] = name
            if name.lower() == "sconscript":
                sconscript_env['sconscript_name_id'] = ""
                path_without_ext = sconstruct_offset_path
                name = path_without_ext

            sconscript_env['sconscript_file'] = sconscript_file

            build_root = sconscript_env['build_root']
            working_folder = 'working'

            sconscript_env = sconscript_env.Clone()
            sconscript_env['sconscript_env'] = sconscript_env

            sconscript_env['sconscript_build_dir'] = path_without_ext
            sconscript_env['sconscript_toolchain_build_dir'] = os.path.join( path_without_ext, toolchain.name() )
            sconscript_env['sconscript_dir'] = os.path.join( sconscript_env['base_path'], sconstruct_offset_path )
            sconscript_env['abs_sconscript_dir'] = os.path.abspath( sconscript_env['sconscript_dir'] )
            sconscript_env['tool_arch_abi_dir'] = os.path.join( toolchain.name(), target_arch, abi )
            sconscript_env['tool_variant_dir'] = os.path.join( toolchain.name(), variant, target_arch, abi )
            sconscript_env['tool_variant_working_dir'] = os.path.join( sconscript_env['tool_variant_dir'], working_folder )

            build_base_path = os.path.join( path_without_ext, sconscript_env['tool_variant_dir'] )

            def flatten_dir( directory, join_char="_" ):
                return join_char.join( os.path.normpath( directory ).split( os.path.sep ) )

            sconscript_env['build_base_path']  = build_base_path
            sconscript_env['flat_build_base']  = flatten_dir( build_base_path )

            sconscript_env['tool_variant_build_dir']  = os.path.join( build_root, sconscript_env['tool_variant_dir'], working_folder )
            sconscript_env['build_dir']               = os.path.normpath( os.path.join( build_root, build_base_path, working_folder, '' ) )
            sconscript_env['abs_build_dir']           = os.path.abspath( sconscript_env['build_dir'] )
            sconscript_env['build_tool_variant_dir']  = os.path.normpath( os.path.join( build_root, sconscript_env['tool_variant_dir'], working_folder, '' ) )
            sconscript_env['offset_dir']              = sconstruct_offset_path
            sconscript_env['offset_tool_variant_dir'] = os.path.join( sconscript_env['offset_dir'], sconscript_env['tool_variant_dir'] )
            sconscript_env['tool_variant_dir_offset'] = os.path.normpath( os.path.join( sconscript_env['tool_variant_dir'], sconscript_env['offset_dir'] ) )
            sconscript_env['flat_tool_variant_dir_offset'] = os.path.normpath( os.path.join( flatten_dir( sconscript_env['tool_variant_dir'] ), sconscript_env['offset_dir'] ) )
            sconscript_env['final_dir']               = '..' + os.path.sep + 'final' + os.path.sep
            sconscript_env['active_toolchain']        = toolchain

            def abs_final_dir( abs_build_dir, final_dir ):
                return os.path.isabs( final_dir ) and final_dir or os.path.normpath( os.path.join( abs_build_dir, final_dir ) )

            sconscript_env['abs_final_dir']  = abs_final_dir( sconscript_env['abs_build_dir'], sconscript_env['final_dir'] )

            sconscript_env.AppendUnique( INCPATH = [
                    sconscript_env['offset_dir']
            ] )

            cuppa.core.environment.EnvironmentMethods.add_progress_tracking( sconscript_env )

            sconscript_exports = {
                'env'                     : sconscript_env,
                'sconscript_env'          : sconscript_env,
                'build_root'              : build_root,
                'build_dir'               : sconscript_env['build_dir'],
                'abs_build_dir'           : sconscript_env['abs_build_dir'],
                'final_dir'               : sconscript_env['final_dir'],
                'abs_final_dir'           : sconscript_env['abs_final_dir'],
                'common_variant_final_dir': '../../../common/final/',
                'common_project_final_dir': build_root + '/common/final/',
                'project'                 : name,
            }

            self._configure.configure( sconscript_exports['env'] )

            cuppa.modules.registration.init_env_for_variant( "methods", sconscript_exports )

            if sconscript_env['dump']:
                logger.info( "{} {}".format( as_info_label( "Dumping ENV for"), as_info( sconscript_exports['build_dir'] ) ) )
                dump = sconscript_env.Dump()
                logger.info( "\n" + dump + "\n" )
            else:
                SCons.Script.SConscript(
                    [ sconscript_file ],
                    variant_dir = sconscript_exports['build_dir'],
                    duplicate   = 0,
                    exports     = sconscript_exports
                )

        else:
            logger.error( "Skipping non-existent project [{}] using [{},{},{}]".format(
                    as_error( sconscript_file ),
                    as_error( toolchain.name() ),
                    as_error( variant ),
                    as_error( target_arch )
            ) )


def run( *args, **kwargs ):
    Construct( *args, **kwargs )

