
#          Copyright Jamie Allsop 2011-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost Builder
#-------------------------------------------------------------------------------
import os

# SCons Imports
from SCons.Script import File, Flatten

# Cuppa Imports
import cuppa.build_platform

from cuppa.output_processor import IncrementalSubProcess
from cuppa.colourise        import as_info, as_notice, colour_items
from cuppa.log              import logger

# Boost Imports
from cuppa.dependencies.boost.bjam                 import BjamOutputProcessor, BuildBjam, bjam_exe, bjam_command
from cuppa.dependencies.boost.configjam            import WriteToolsetConfigJam
from cuppa.dependencies.boost.library_naming       import stage_directory, variant_name, static_library_name, shared_library_name, extract_library_name_from_path
from cuppa.dependencies.boost.library_dependencies import add_dependent_libraries



def _lazy_update_library_list( env, emitting, libraries, prebuilt_libraries, add_dependents, linktype, boost, stage_dir ):

    def build_with_library_name( library ):
        return library == 'log_setup' and 'log' or library

    if add_dependents:
        if not emitting:
            libraries = set( build_with_library_name(l) for l in add_dependent_libraries( boost, linktype, libraries ) )
        else:
            libraries = add_dependent_libraries( boost, linktype, libraries )

    if not stage_dir in prebuilt_libraries:
        logger.trace( "Lazy update libraries list for [{}] to [{}]".format( as_info(stage_dir), colour_items(str(l) for l in libraries) ) )
        prebuilt_libraries[ stage_dir ] = set( libraries )
    else:
        logger.trace( "Lazy read libraries list for [{}]: libraries are [{}]".format( as_info(stage_dir), colour_items(str(l) for l in libraries) ) )
        libraries = [ l for l in libraries if l not in prebuilt_libraries[ stage_dir ] ]
        prebuilt_libraries[ stage_dir ].update( libraries )

    return libraries



class BoostLibraryAction(object):

    prebuilt_libraries = {}

    def __init__( self, env, stage_dir, libraries, add_dependents, linktype, boost, verbose_build, verbose_config ):

        self._env = env

        logger.trace( "Requested libraries [{}]".format( colour_items( libraries ) ) )

        self._linktype       = linktype
        self._variant        = variant_name( self._env['variant'].name() )
        self._target_arch    = env['target_arch']
        self._toolchain      = env['toolchain']
        self._stage_dir      = stage_dir

        self._libraries = _lazy_update_library_list( env, False, libraries, self.prebuilt_libraries, add_dependents, linktype, boost, self._stage_dir )

        logger.trace( "Required libraries [{}]".format( colour_items( self._libraries ) ) )

        self._location       = boost.local()
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config
        self._job_count      = env['job_count']
        self._parallel       = env['parallel']


    def __call__( self, target, source, env ):

        if not self._libraries:
            return None

        args = bjam_command(
                    env,
                    self._location,
                    self._toolchain,
                    self._libraries,
                    self._variant,
                    self._target_arch,
                    self._linktype,
                    self._stage_dir,
                    self._verbose_build,
                    self._verbose_config,
                    self._job_count,
                    self._parallel
        )

        processor = BjamOutputProcessor( env, self._verbose_build, self._verbose_config, self._toolchain )

        returncode = IncrementalSubProcess.Popen(
                processor,
                args,
                cwd=self._location
        )

        summary = processor.summary( returncode )

        if summary:
            print summary

        if returncode:
            return returncode

        return None



class BoostLibraryEmitter(object):

    prebuilt_libraries = {}

    def __init__( self, env, stage_dir, libraries, add_dependents, linktype, boost ):
        self._env = env
        self._stage_dir    = stage_dir

        self._libraries    = _lazy_update_library_list( env, True, libraries, self.prebuilt_libraries, add_dependents, linktype, boost, self._stage_dir )

        self._location     = boost.local()
        self._boost        = boost
        self._threading    = True

        self._linktype     = linktype
        self._variant      = variant_name( self._env['variant'].name() )
        self._toolchain    = env['toolchain']


    def __call__( self, target, source, env ):

        for library in self._libraries:
            filename = None
            if self._linktype == 'static':
                filename = static_library_name( env, library, self._toolchain, self._boost.version(), self._variant, self._threading )
            else:
                filename = shared_library_name( env, library, self._toolchain, self._boost.full_version(), self._variant, self._threading )

            built_library_path = os.path.join( self._location, self._stage_dir, 'lib', filename )

            logger.trace( "Emit Boost library [{}] to [{}]".format( as_notice(library), as_notice(built_library_path) ) )

            node = File( built_library_path )

            target.append( node )

        return target, source



class BoostLibraryBuilder(object):

    _prebuilt_libraries = {}

    def __init__( self, boost, add_dependents, verbose_build, verbose_config ):
        self._boost = boost
        self._add_dependents = add_dependents
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config


    def __call__( self, env, target, source, libraries, linktype ):

        logger.trace( "Build Dir = [{}]".format( as_info( env['build_dir'] ) ) )

        logger.trace( "Requested libraries = [{}]".format( colour_items( libraries ) ) )

        variant      = variant_name( env['variant'].name() )
        target_arch  = env['target_arch']
        toolchain    = env['toolchain']
        stage_dir    = stage_directory( toolchain, variant, target_arch, toolchain.abi_flag(env) )
        variant_key  = stage_dir

        logger.trace( "Prebuilt Libraries Variant Key = [{}]".format( as_notice( variant_key ) ) )

        library_action  = BoostLibraryAction ( env, stage_dir, libraries, self._add_dependents, linktype, self._boost, self._verbose_build, self._verbose_config )
        library_emitter = BoostLibraryEmitter( env, stage_dir, libraries, self._add_dependents, linktype, self._boost )

        logger.trace( "Action  Prebuilt Libraries for [{}] = {}".format( as_info( variant_key ), colour_items( BoostLibraryAction.prebuilt_libraries[variant_key] ) ) )
        logger.trace( "Emitter Prebuilt Libraries for [{}] = {}".format( as_info( variant_key ), colour_items( BoostLibraryEmitter.prebuilt_libraries[variant_key] ) ) )

        env.AppendUnique( BUILDERS = {
            'BoostLibraryBuilder' : env.Builder( action=library_action, emitter=library_emitter )
        } )

        built_libraries = env.BoostLibraryBuilder( target, source )

        built_libraries_map = { extract_library_name_from_path(l):l for l in built_libraries }

        logger.trace( "Libraries to be built = [{}]".format( colour_items( built_libraries_map.keys() ) ) )

        if not variant_key in self._prebuilt_libraries:
             self._prebuilt_libraries[ variant_key ] = {}

        logger.trace( "Variant sources = [{}]".format( colour_items( self._prebuilt_libraries[ variant_key ].keys() ) ) )

        required_libraries = add_dependent_libraries( self._boost, linktype, libraries )

        logger.trace( "Required libraries = [{}]".format( colour_items( required_libraries ) ) )

        for library in required_libraries:
            if library in self._prebuilt_libraries[ variant_key ]:

                logger.trace( "Library [{}] already present in variant [{}]".format( as_notice(library), as_info(variant_key) ) )

                #if library not in built_libraries_map: # The Depends is required regardless so SCons knows about the relationship
                logger.trace( "Add Depends for [{}]".format( as_notice( self._prebuilt_libraries[ variant_key ][library].path ) ) )
                env.Depends( built_libraries, self._prebuilt_libraries[ variant_key ][library] )
            else:
                self._prebuilt_libraries[ variant_key ][library] = built_libraries_map[library]

        logger.trace( "Library sources for variant [{}] = [{}]".format(
                as_info(variant_key),
                colour_items( k+":"+as_info(v.path) for k,v in self._prebuilt_libraries[ variant_key ].iteritems() )
        ) )


        bjam = env.Command( bjam_exe( self._boost ), [], BuildBjam( self._boost ) )
        env.NoClean( bjam )

        if built_libraries:

            env.Requires( built_libraries, bjam )

            if cuppa.build_platform.name() == "Linux":

                toolset_target = os.path.join( self._boost.local(), env['toolchain'].name() + "._jam" )
                toolset_config_jam = env.Command( toolset_target, [], WriteToolsetConfigJam() )

                project_config_target = os.path.join( self._boost.local(), "project-config.jam" )
                if not os.path.exists( project_config_target ):
                    project_config_jam = env.Requires( project_config_target, env.AlwaysBuild( toolset_config_jam ) )
                    env.Requires( built_libraries, project_config_jam )

                env.Requires( built_libraries, toolset_config_jam )

        install_dir = linktype == 'shared' and env['abs_final_dir'] or env['abs_build_dir']

        installed_libraries = []

        for library in required_libraries:

            logger.debug( "Install Boost library [{}:{}] to [{}]".format( as_notice(library), as_info(str(self._prebuilt_libraries[ variant_key ][library])), as_notice(install_dir) ) )

            library_node = self._prebuilt_libraries[ variant_key ][library]

            logger.trace( "Library Node = \n[{}]\n[{}]\n[{}]\n[{}]\n[{}]".format(
                    as_notice(library_node.path),
                    as_notice(str(library_node)),
                    as_notice(str(library_node.get_binfo().bact) ),
                    as_notice(str(library_node.get_state()) ),
                    as_notice(str(library_node.srcnode())   )
            ) )

            installed_library = env.CopyFiles( install_dir, self._prebuilt_libraries[ variant_key ][library] )

            installed_libraries.append( installed_library )

        logger.debug( "Boost 'Installed' Libraries = [{}]".format( colour_items( l.path for l in Flatten( installed_libraries ) ) ) )

        return Flatten( installed_libraries )
