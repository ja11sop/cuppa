
#          Copyright Jamie Allsop 2011-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Boost Builder
#-------------------------------------------------------------------------------
import os
import six

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


_prebuilt_boost_libraries = { 'action': {}, 'emitter': {}, 'builder': {} }
_bjam_invocations = {}

# NOTE: We want to take advantage of the ability to parallelise BJAM calls when building boost.
#       However a number of aspects of how BJAM is executed are not "thread-safe" - that is
#       concurrent calls to BJAM to build libraries that will touch the same folders or files
#       on disk will result in spurious build failures. To address this issues we attempt to do
#       two things:
#
#        1. We minimise the number of calls to BJAM by tracking the which libraries are being
#           built and re-use targets when a BJAM call exists that will perform the build. This
#           is the purpose of the `_prebuilt_boost_libraries` dictionary. We only really need
#           to track the libraries in the `buildber` sub-dict but the libraries as known to the
#           `action` and `emitter` are also tracked to help with logging and diagnostics.
#
#           By performing this tracking we can re-use library targets when building the dependency
#           tree and minimise unneeded calls to BJAM. We do this across a whole sconstruct file
#           as typically multiple sconscript files will make the same calls to build the same
#           libraries and if we are executing Scons in parallel mode using `--parallel` on the
#           cuppa commandline then those invocations of BJAM will potentially execute in parallel.
#
#        2. We serialise calls to BJAM because concurrent calls to BJAM that build targets
#           touching the same areas of disk with spuriously fail. Since we will use sufficient
#           cores to maximise the opportunity to execute builds in parallel when invoking BJAM we
#           will, on average, not suffer any loss of processing opportuinty. In other words we
#           can avoid hitting the build failures while still benefitting from executing a parallel
#           build. This is the purpose of the `_bjam_invocations` dict. With this we track all
#           invocations to BJAM and use a Requires() rule to force an ordering at the dependency
#           tree level.
#
#       Here is an example of BJAM code in Boost that cannot reliably function concurrently. From
#       'tools/build/src/util/path.jam':
#
#       ---------------------------------------------------------------------------------
#            rule makedirs ( path )
#            {
#                local result = true ;
#                local native = [ native $(path) ] ;
#                if ! [ exists $(native) ]
#                {
#                    if [ makedirs [ parent $(path) ] ]
#                    {
#                        if ! [ MAKEDIR $(native) ]
#                        {
#                            import errors ;
#                            errors.error "Could not create directory '$(path)'" ;
#                            result = ;
#                        }
#                    }
#                }
#                return $(result) ;
#            }
#       ---------------------------------------------------------------------------------
#
#       This should be written as:
#
#       ---------------------------------------------------------------------------------
#            rule makedirs ( path )
#            {
#                local result = true ;
#                local native = [ native $(path) ] ;
#                if ! [ exists $(native) ]
#                {
#                    if [ makedirs [ parent $(path) ] ]
#                    {
#                        if ! [ MAKEDIR $(native) ]
#                        {
#                            if ! [ exists $(native) ]
#                            {
#                                import errors ;
#                                errors.error "Could not create directory '$(path)'" ;
#                                result = ;
#                            }
#                        }
#                    }
#                }
#                return $(result) ;
#            }
#       ---------------------------------------------------------------------------------
#
#       This change is needed as makedirs might fail because the directly already exists, perhaps
#       because a concurrent invocation of BJAM created it between the call to exists and makedirs



def _lazy_update_library_list( env, emitting, libraries, prebuilt_libraries, add_dependents, linktype, boost, stage_dir ):

    def build_with_library_name( library ):
        if library == 'log_setup':
            return 'log'
        elif library in { 'prg_exec_monitor', 'test_exec_monitor', 'unit_test_framework' }:
            return 'test'
        else:
            return library

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

    def __init__( self, env, stage_dir, libraries, add_dependents, linktype, boost, verbose_build, verbose_config ):

        self._env = env

        sconstruct_id = env['sconstruct_path']
        global _prebuilt_boost_libraries
        if sconstruct_id not in _prebuilt_boost_libraries['action']:
            _prebuilt_boost_libraries['action'][sconstruct_id] = {}

        logger.trace( "Current Boost build [{}] has the following build variants [{}]".format( as_info(sconstruct_id), colour_items(_prebuilt_boost_libraries['action'][sconstruct_id].keys()) ) )

        logger.debug( "Requested libraries [{}]".format( colour_items( libraries ) ) )

        self._linktype       = linktype
        self._variant        = variant_name( self._env['variant'].name() )
        self._target_arch    = env['target_arch']
        self._toolchain      = env['toolchain']
        self._stage_dir      = stage_dir

        self._libraries = _lazy_update_library_list( env, False, libraries, _prebuilt_boost_libraries['action'][sconstruct_id], add_dependents, linktype, boost, self._stage_dir )

        logger.debug( "Required libraries [{}]".format( colour_items( self._libraries ) ) )

        self._location       = boost.local()
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config
        self._job_count      = env['job_count']
        self._parallel       = env['parallel']
        self._threading      = True


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
            print( summary )

        if returncode:
            return returncode

        return None



class BoostLibraryEmitter(object):

    def __init__( self, env, stage_dir, libraries, add_dependents, linktype, boost ):
        self._env = env

        sconstruct_id = env['sconstruct_path']
        global _prebuilt_boost_libraries
        if sconstruct_id not in _prebuilt_boost_libraries['emitter']:
            _prebuilt_boost_libraries['emitter'][sconstruct_id] = {}

        logger.trace( "Current Boost build [{}] has the following build variants [{}]".format( as_info(sconstruct_id), colour_items(_prebuilt_boost_libraries['emitter'][sconstruct_id].keys()) ) )

        self._stage_dir    = stage_dir

        logger.debug( "Requested libraries [{}]".format( colour_items( libraries ) ) )

        self._libraries    = _lazy_update_library_list( env, True, libraries, _prebuilt_boost_libraries['emitter'][sconstruct_id], add_dependents, linktype, boost, self._stage_dir )

        logger.debug( "Required libraries [{}]".format( colour_items( self._libraries ) ) )

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

    def __init__( self, boost, add_dependents, verbose_build, verbose_config ):
        self._boost = boost
        self._add_dependents = add_dependents
        self._verbose_build  = verbose_build
        self._verbose_config = verbose_config


    def __call__( self, env, target, source, libraries, linktype ):

        sconstruct_id = env['sconstruct_path']

        global _prebuilt_boost_libraries
        if sconstruct_id not in _prebuilt_boost_libraries['builder']:
            _prebuilt_boost_libraries['builder'][sconstruct_id] = {}

        global _bjam_invocations
        if sconstruct_id not in _bjam_invocations:
            _bjam_invocations[sconstruct_id] = []

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

        logger.trace( "Action  Prebuilt Libraries for [{}] = {}".format(
                as_info( variant_key ),
                colour_items( _prebuilt_boost_libraries['action'][sconstruct_id][variant_key] )
        ) )

        logger.trace( "Emitter Prebuilt Libraries for [{}] = {}".format(
                as_info( variant_key ),
                colour_items( _prebuilt_boost_libraries['emitter'][sconstruct_id][variant_key] )
        ) )

        env.AppendUnique( BUILDERS = {
            'BoostLibraryBuilder' : env.Builder( action=library_action, emitter=library_emitter )
        } )

        built_libraries = env.BoostLibraryBuilder( target, source )

        built_libraries_map = { extract_library_name_from_path(l):l for l in built_libraries }

        logger.trace( "Libraries to be built = [{}]".format( colour_items( built_libraries_map.keys() ) ) )

        if not variant_key in _prebuilt_boost_libraries['builder'][sconstruct_id]:
             _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ] = {}

        logger.trace( "Variant sources = [{}]".format( colour_items( _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ].keys() ) ) )

        required_libraries = add_dependent_libraries( self._boost, linktype, libraries )

        logger.trace( "Required libraries = [{}]".format( colour_items( required_libraries ) ) )

        unbuilt_libraries = False
        new_libraries = []

        for library in required_libraries:
            if library in _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ]:

                logger.trace( "Library [{}] already present in variant [{}]".format( as_notice(library), as_info(variant_key) ) )

                # Calling Depends() is required so SCons knows about the relationship, even
                # if the library already exists in the _prebuilt_boost_libraries dict
                logger.trace( "Add Depends for [{}]".format( as_notice( _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ][library].path ) ) )
                env.Depends( built_libraries, _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ][library] )
            else:
                unbuilt_libraries = True
                new_libraries.append( library )
                _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ][library] = built_libraries_map[library]

            env.Depends( target, _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ][library] )

        logger.trace( "Library sources for variant [{}] = [{}]".format(
                as_info(variant_key),
                colour_items( k+":"+as_info(v.path) for k,v in six.iteritems(_prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ]) )
        ) )


        if unbuilt_libraries:
            # if this is not the first BJAM invocation for this set of libraries make it require (using Requires)
            # the previous BJAM invocation otherwise we already have an invocation of BJAM that will create the
            # required libraries and therefore we can ignore the invocation

            index = len(_bjam_invocations[sconstruct_id])
            previous_invocation = _bjam_invocations[sconstruct_id] and _bjam_invocations[sconstruct_id][-1] or None

            if previous_invocation and previous_invocation['invocation'] != built_libraries:
                logger.debug( "Add BJAM invocation Requires() such that ([{}][{}][{}]) requires ([{}][{}][{}])".format(
                            as_info(str(index)),
                            as_info(variant_key),
                            colour_items( new_libraries ),
                            as_info(str(previous_invocation['index'])),
                            as_info(previous_invocation['variant']),
                            colour_items( previous_invocation['libraries'] )
                ) )
                env.Requires( built_libraries, previous_invocation['invocation'] )
            # if this is the first invocation of BJAM then add it to the list of BJAM invocations, or if this is
            # a different invocation (for different libraries) of BJAM add it to the list of invocations
            if not previous_invocation or previous_invocation['invocation'] != built_libraries and built_libraries:
                logger.debug( "Adding BJAM invocation [{}] for variant [{}] and new libraries [{}] to invocation list".format(
                            as_info(str(index)),
                            as_info(variant_key),
                            colour_items( new_libraries )
                ) )
                _bjam_invocations[sconstruct_id].append( {
                        'invocation': built_libraries,
                        'index'     : index,
                        'variant'   : variant_key,
                        'libraries' : new_libraries
                } )


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

            logger.debug( "Install Boost library [{}:{}] to [{}]".format( as_notice(library), as_info(str(_prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ][library])), as_notice(install_dir) ) )

            library_node = _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ][library]

            logger.trace( "Library Node = \n[{}]\n[{}]\n[{}]\n[{}]\n[{}]".format(
                    as_notice(library_node.path),
                    as_notice(str(library_node)),
                    as_notice(str(library_node.get_binfo().bact) ),
                    as_notice(str(library_node.get_state()) ),
                    as_notice(str(library_node.srcnode())   )
            ) )

            installed_library = env.CopyFiles( install_dir, _prebuilt_boost_libraries['builder'][sconstruct_id][ variant_key ][library] )

            installed_libraries.append( installed_library )

        logger.debug( "Boost 'Installed' Libraries = [{}]".format( colour_items( l.path for l in Flatten( installed_libraries ) ) ) )

        return Flatten( installed_libraries )
