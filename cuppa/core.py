#          Copyright Jamie Allsop 2011-2016
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Core
#-------------------------------------------------------------------------------

# Python Standard
import os.path
import os
import re
import fnmatch
import multiprocessing
import pkg_resources
import collections

# Scons
import SCons.Script

# Custom
import cuppa.modules.registration
import cuppa.build_platform
import cuppa.output_processor
import cuppa.recursive_glob
import cuppa.configure
import cuppa.options
import cuppa.version
#import cuppa.progress
#import cuppa.tree
#import cuppa.cpp.stdcpp

from cuppa.colourise import colouriser, as_emphasised, as_info, as_error, as_notice, colour_items
from cuppa.log import initialise_logging, set_logging_level, reset_logging_format, logger

from cuppa.toolchains             import *
from cuppa.methods                import *
from cuppa.dependencies           import *
from cuppa.profiles               import *
from cuppa.variants               import *
from cuppa.project_generators     import *


SCons.Script.Decider( 'MD5-timestamp' )



def add_option( *args, **kwargs ):
    SCons.Script.AddOption( *args, **kwargs )


def add_base_options():

    add_option( '--raw-output', dest='raw_output', action='store_true',
                            help='Disable output processing like colourisation of output' )

    add_option( '--standard-output', dest='standard_output', action='store_true',
                            help='Perform standard output processing but not colourisation of output' )

    add_option( '--minimal-output', dest='minimal_output', action='store_true',
                            help='Show only errors and warnings in the output' )

    add_option( '--ignore-duplicates', dest='ignore_duplicates', action='store_true',
                            help='Do not show repeated errors or warnings' )

    add_option( '--projects', type='string', nargs=1,
                            action='callback', callback=cuppa.options.list_parser( 'projects' ),
                            help='Projects to build (alias for scripts)' )

    add_option( '--scripts', type='string', nargs=1,
                            action='callback', callback=cuppa.options.list_parser( 'projects' ),
                            help='Sconscripts to run' )

    add_option( '--thirdparty', type='string', nargs=1, action='store',
                            dest='thirdparty',
                            metavar='DIR',
                            help='Thirdparty directory' )

    add_option( '--build-root', type='string', nargs=1, action='store',
                            dest='build_root',
                            help='The root directory for build output. If not specified then _build_ is used' )

    add_option( '--download-root', type='string', nargs=1, action='store',
                            dest='download_root',
                            help='The root directory for downloading external libraries to.'
                                 ' If not specified then _cuppa_ is used' )

    add_option( '--cache-root', type='string', nargs=1, action='store',
                            dest='cache_root',
                            help='The root directory for caching downloaded external archived libraries.'
                                 ' If not specified then ~/_cuppa_/cache is used' )

    add_option( '--runner', type='string', nargs=1, action='store',
                            dest='runner',
                            help='The test runner to use for executing tests. The default is the'
                                 ' process test runner' )

    add_option( '--dump',   dest='dump', action='store_true',
                            help='Dump the default environment and exit' )

    add_option( '--parallel', dest='parallel', action='store_true',
                            help='Enable parallel builds utilising the available concurrency.'
                                 ' Translates to -j N with N chosen based on the current hardware' )

    add_option( '--show-test-output',   dest='show-test-output', action='store_true',
                            help='When executing tests display all outout to stdout and stderr as appropriate' )

    verbosity_choices = ( 'trace', 'debug', 'info', 'warn', 'error' )

    add_option( '--verbosity', dest='verbosity', choices=verbosity_choices, nargs=1, action='store',
                            help='The The verbosity level that you wish to run cuppa at. The default level'
                                 ' is "info". VERBOSITY may be one of {}'.format( str(verbosity_choices) ) )

#    add_option( '--b2',     dest='b2', action='store_true',
#                            help='Execute boost.build by calling b2 or bjam' )

#    add_option( '--b2-path', type='string', nargs=1, action='store',
#                            dest='b2_path',
#                            help='Specify a path to bjam or b2' )

    decider_choices = ( 'timestamp-newer', 'timestamp-match', 'MD5', 'MD5-timestamp' )

    add_option( '--decider', dest='decider', choices=decider_choices, nargs=1, action='store',
                            help='The decider to use for determining if a dependency has changed.'
                                 ' Refer to the Scons manual for more details. By default "MD5-timestamp"'
                                 ' is used. DECIDER may be one of {}'.format( str(decider_choices) ) )



def set_base_options():
    SCons.Script.SetOption( 'warn', 'no-duplicate-environment' )



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


class CuppaEnvironment(collections.MutableMapping):

    _tools = []
    _options = {}
    _cached_options = {}
    _methods = {}

    # Option Interface
    @classmethod
    def get_option( cls, option, default=None ):
        if option in cls._cached_options:
            return cls._cached_options[ option ]

        value = SCons.Script.GetOption( option )
        source = None
        if value == None or value == '':
            if cls._options['default_options'] and option in cls._options['default_options']:
                value = cls._options['default_options'][ option ]
                source = "in the sconstruct file"
            elif default:
                value = default
                source = "using default"
        else:
            source = "on command-line"

        if option in cls._options['configured_options']:
            source = "using configure"

        if value:
            logger.debug( "option [{}] set {} as [{}]".format(
                        as_info( option ),
                        source,
                        as_info( str(value) ) )
            )
        cls._cached_options[option] = value
        return value


    @classmethod
    def _get_option_method( cls, env, option, default=None ):
        return cls.get_option( option, default )


    # Environment Interface
    @classmethod
    def default_env( cls ):
        if not hasattr( cls, '_default_env' ):
            cls._default_env = SCons.Script.Environment( tools=['default'] + cls._tools )
        return cls._default_env


    @classmethod
    def create_env( cls, **kwargs ):

        tools = ['default'] + cls._tools
        if 'tools' in kwargs:
            tools = tools + kwargs['tools']
            del kwargs['tools']

        tools = SCons.Script.Flatten( tools )

        env = SCons.Script.Environment(
                tools = tools,
                **kwargs
        )

        env['default_env'] = CuppaEnvironment.default_env()

        for key, option in cls._options.iteritems():
            env[key] = option
        for name, method in cls._methods.iteritems():
            env.AddMethod( method, name )
        env.AddMethod( cls._get_option_method, "get_option" )

        return env


    @classmethod
    def dump( cls ):
        print str( cls._options )
        print str( cls._methods )


    @classmethod
    def colouriser( cls ):
        return colouriser

    @classmethod
    def add_tools( cls, tools ):
        cls._tools.append( tools )


    @classmethod
    def tools( cls ):
        return cls._tools

    @classmethod
    def add_method( cls, name, method ):
        cls._methods[name] = method

    @classmethod
    def add_variant( cls, name, variant ):
        if not 'variants' in  cls._options:
            cls._options['variants'] = {}
        cls._options['variants'][name] = variant

    @classmethod
    def add_action( cls, name, action ):
        if not 'actions' in  cls._options:
            cls._options['actions'] = {}
        cls._options['actions'][name] = action

    @classmethod
    def add_supported_toolchain( cls, name ):
        if not 'supported_toolchains' in  cls._options:
            cls._options['supported_toolchains'] = []
        cls._options['supported_toolchains'].append( name )

    @classmethod
    def add_available_toolchain( cls, name, toolchain ):
        if not 'toolchains' in  cls._options:
            cls._options['toolchains'] = {}
        cls._options['toolchains'][name] = toolchain

    @classmethod
    def add_project_generator( cls, name, project_generator ):
        if not 'project_generators' in  cls._options:
            cls._options['project_generators'] = {}
        cls._options['project_generators'][name] = project_generator

    @classmethod
    def add_profile( cls, name, profile ):
        if not 'profiles' in  cls._options:
            cls._options['profiles'] = {}
        cls._options['profiles'][name] = profile

    @classmethod
    def add_dependency( cls, name, dependency ):
        if not 'dependencies' in  cls._options:
            cls._options['dependencies'] = {}
        cls._options['dependencies'][name] = dependency

    # Dict Interface
    def __getitem__( self, key ):
        return self._options[key]

    def __setitem__( self, key, value ):
        self._options[key] = value

    def __delitem__( self, key ):
        del self._options[key]
        del self._cached_options[key]

    def __iter__( self ):
        return iter( self._options )

    def __len__( self ):
        return len( self._options )

    def __contains__( self, key ):
        return key in self._options


class Construct(object):

    platforms_key    = 'platforms'
    variants_key     = 'variants'
    actions_key      = 'actions'
    toolchains_key   = 'toolchains'
    dependencies_key = 'dependencies'
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



    def initialise_options( self, options, default_options, dependencies ):
        options['default_options'] = default_options or {}
        # env.AddMethod( self.get_option, "get_option" )
        add_base_options()
        cuppa.modules.registration.add_options( self.toolchains_key )
        cuppa.modules.registration.add_options( self.dependencies_key )
        cuppa.modules.registration.add_options( self.profiles_key )
        cuppa.modules.registration.add_options( self.project_generators_key )
        cuppa.modules.registration.add_options( self.methods_key )

        if dependencies:
            for dependency in dependencies.itervalues():
                dependency.add_options( SCons.Script.AddOption )

        for dependency_plugin in pkg_resources.iter_entry_points( group='cuppa.dependency.plugins', name=None ):
                dependency_plugin.load().add_options( SCons.Script.AddOption )

#        cuppa.cpp.stdcpp.add_options( SCons.Script.AddOption )


    def print_construct_variables( self, env ):
        keys = {
                'raw_output',
                'standard_output',
                'minimal_output',
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
                'decider'
        }

        for key in keys:
            if key in env:
                print "cuppa: Env[%s] = %s" % ( key, env[key] )


    @classmethod
    def _set_verbosity_level( cls, cuppa_env ):
        verbosity = None

        ## Check if -Q was passed on the command-line
        scons_no_progress = cuppa_env.get_option( 'no_progress' )
        if scons_no_progress:
            verbosity = 'warn'

        ## Check if -q, --quiet or --silent was passed on the command-line
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


    def __init__( self,
                  base_path            = os.path.abspath( '.' ),
                  branch_root          = None,
                  default_options      = {},
                  default_projects     = [],
                  default_variants     = [],
                  default_dependencies = [],
                  default_profiles     = [],
                  default_runner       = None,
                  configure_callback   = None,
                  dependencies         = {},
                  tools                = [] ):

        set_base_options()
        initialise_logging()

        cuppa_env = CuppaEnvironment()
        cuppa_env.add_tools( tools )

        self.initialise_options( cuppa_env, default_options, dependencies )
        cuppa_env['configured_options'] = {}
        self._configure = cuppa.configure.Configure( cuppa_env, callback=configure_callback )

        self._set_verbosity_level( cuppa_env )

        cuppa_env['sconstruct_file'] = cuppa_env.get_option( 'file' )

        if not cuppa_env['sconstruct_file']:
            for path in [ 'SConstruct', 'Sconstruct', 'sconstruct' ]:
                if os.path.exists( path ):
                    cuppa_env['sconstruct_file'] = path

        self._set_output_format( cuppa_env )

        cuppa.version.check_current_version()

        logger.info( "using sconstruct file [{}]".format( as_notice( cuppa_env['sconstruct_file'] ) ) )

        help = cuppa_env.get_option( 'help' ) and True or False

        self._configure.load()

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

        build_root = cuppa_env.get_option( 'build_root', default='_build' )
        cuppa_env['build_root'] = os.path.normpath( os.path.expanduser( build_root ) )

        download_root = cuppa_env.get_option( 'download_root', default='_cuppa' )
        cuppa_env['download_root'] = os.path.normpath( os.path.expanduser( download_root ) )

        cache_root = cuppa_env.get_option( 'cache_root', default='~/_cuppa/_cache' )
        cuppa_env['cache_root'] = os.path.normpath( os.path.expanduser( cache_root ) )
        if not os.path.exists( cuppa_env['cache_root'] ):
            os.makedirs( cuppa_env['cache_root'] )

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

        cuppa_env['show_test_output'] = cuppa_env.get_option( 'show-test-output' ) and True or False

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

            def add_dependency( name, dependency ):
                cuppa_env['dependencies'][name] = dependency

            cuppa.modules.registration.get_options( "methods", cuppa_env )

            if not help and not self._configure.handle_conf_only():
                cuppa_env[self.project_generators_key] = {}
                cuppa.modules.registration.add_to_env( "dependencies",       cuppa_env, add_dependency )
                cuppa.modules.registration.add_to_env( "profiles",           cuppa_env )
                cuppa.modules.registration.add_to_env( "methods",            cuppa_env )
                cuppa.modules.registration.add_to_env( "project_generators", cuppa_env )

                for method_plugin in pkg_resources.iter_entry_points( group='cuppa.method.plugins', name=None ):
                    method_plugin.load().add_to_env( cuppa_env )

                for dependency_plugin in pkg_resources.iter_entry_points( group='cuppa.dependency.plugins', name=None ):
                    dependency_plugin.load().add_to_env( cuppa_env, add_dependency )

                if dependencies:
                    for name, dependency in dependencies.iteritems():
                        dependency.add_to_env( cuppa_env, add_dependency )

            # TODO - default_profile

            if cuppa_env.get_option( 'dump' ):
                cuppa_env.dump()
                SCons.Script.Exit()

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
                logger.debug( "Running in {} with option [{}] set {} as [{}]".format(
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
            print "cuppa: Handling onfiguration only, so no builds will be attempted."
            print "cuppa: With the current configuration executing 'scons -D' would be equivalent to:"
            print ""
            print "scons -D {}".format( self._command_line_from_settings( cuppa_env['configured_options'] ) )
            print ""
            print "cuppa: Nothing to be done. Exiting."
            SCons.Script.Exit()


    def _command_line_from_settings( self, settings ):
        commands = []
        for key, value in settings.iteritems():
            command = as_emphasised( "--" + key )
            if value != True and value != False:
                if not isinstance( value, list ):
                    command += "=" + as_info( str(value) )
                else:
                    command += "=" + as_info( ",".join( value ) )
            commands.append( command )
        commands.sort()
        return " ".join( commands )


    def get_active_actions_for_variant( self, cuppa_env, active_variants, variant ):
        available_variants = cuppa_env[ self.variants_key ]
        available_actions  = cuppa_env[ self.actions_key ]
        specified_actions  = {}

        for key, action in available_actions.items():
            if cuppa_env.get_option( action.name() ):
                specified_actions[ action.name() ] = action

        if not specified_actions:
            default_variants = active_variants
            if default_variants:
                for variant in default_variants:
                    if available_actions.has_key( variant ):
                        specified_actions[ variant ] = available_actions[ variant ]

        active_actions = {}

        for key, action in specified_actions.items():
            if key not in available_variants:
                active_actions[ key ] = action
            elif key == variant.name():
                active_actions[ key ] = action

        return active_actions


    def create_build_envs( self, toolchain, cuppa_env ):

        variants = cuppa_env[ self.variants_key ]
        target_architectures = cuppa_env[ 'target_architectures' ]

        if not target_architectures:
            target_architectures = [ None ]

        active_variants = {}

        for key, variant in variants.items():
            if cuppa_env.get_option( variant.name() ):
                active_variants[ variant.name() ] = variant

        if not active_variants:
            default_variants = cuppa_env['default_variants'] or toolchain.default_variants()
            if default_variants:
                for variant in default_variants:
                    if variants.has_key( variant ):
                        active_variants[ variant ] = variants[ variant ]

        build_envs = []

        for key, variant in active_variants.items():

            for target_arch in target_architectures:

                env, target_arch = toolchain.make_env( cuppa_env, variant, target_arch )

                if env:
                    build_envs.append( {
                        'variant': key,
                        'target_arch': target_arch,
                        'abi': toolchain.abi( env ),
                        'env': env } )

                    if not cuppa_env['raw_output']:
                        cuppa.output_processor.Processor.install( env )

                    env['toolchain']       = toolchain
                    env['variant']         = variant
                    env['target_arch']     = target_arch
                    env['abi']             = toolchain.abi( env )
                    env['variant_actions'] = self.get_active_actions_for_variant( cuppa_env, active_variants, variant )

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
            if name.lower() == "sconscript":
                path_without_ext = sconstruct_offset_path
                name = path_without_ext

            sconscript_env['sconscript_file'] = sconscript_file

            build_root = sconscript_env['build_root']

            sconscript_env = sconscript_env.Clone()
            sconscript_env['sconscript_env'] = sconscript_env

            sconscript_env['sconscript_build_dir'] = path_without_ext
            sconscript_env['sconscript_toolchain_build_dir'] = os.path.join( path_without_ext, toolchain.name() )
            sconscript_env['sconscript_dir']   = os.path.join( sconscript_env['base_path'], sconstruct_offset_path )
            sconscript_env['tool_variant_dir'] = os.path.join( toolchain.name(), variant, target_arch, abi )

            build_base_path = os.path.join( path_without_ext, sconscript_env['tool_variant_dir'] )

            def flatten_dir( directory, join_char='_' ):
                return "_".join( directory.split( os.path.sep ) )

            sconscript_env['build_base_path']  = build_base_path
            sconscript_env['flat_build_base']  = flatten_dir( build_base_path )

            sconscript_env['build_dir']        = os.path.normpath( os.path.join( build_root, build_base_path, 'working', '' ) )
            sconscript_env['abs_build_dir']    = os.path.abspath( sconscript_env['build_dir'] )
            sconscript_env['offset_dir']       = sconstruct_offset_path
            sconscript_env['final_dir']        = '..' + os.path.sep + 'final' + os.path.sep
            sconscript_env['active_toolchain'] = toolchain

            def abs_final_dir( abs_build_dir, final_dir ):
                return os.path.isabs( final_dir ) and final_dir or os.path.normpath( os.path.join( abs_build_dir, final_dir ) )

            sconscript_env['abs_final_dir']  = abs_final_dir( sconscript_env['abs_build_dir'], sconscript_env['final_dir'] )

            sconscript_env.AppendUnique( INCPATH = [
                    sconscript_env['offset_dir']
            ] )

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

