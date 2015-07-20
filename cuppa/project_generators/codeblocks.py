
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Codeblocks
#-------------------------------------------------------------------------------

import os
from exceptions import Exception

import cuppa.path
import cuppa.progress
import cuppa.tree
import cuppa.options

from cuppa.colourise import as_error, as_notice


class CodeblocksException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


def ignored_types( env ):
    return [
            env['PROGSUFFIX'],
            env['LIBSUFFIX'],
            env['SHLIBSUFFIX'],
            env['OBJSUFFIX'],
            env['SHOBJSUFFIX'],
            '.log'
    ]


class Codeblocks(object):

    @classmethod
    def add_options( cls, add_option ):

        add_option( '--generate-cbs', dest='generate-cbs',
                    action='store_true',
                    help='Tell scons to generate a Codeblocks project',
                    default=False )

        add_option( '--generate-cbs-include-thirdparty', dest='generate_cbs_include_thirdparty',
                    action='store_true',
                    help='Include dependencies under the thirdparty directory or in downloaded libraries.',
                    default=False )

        add_option( '--generate-cbs-exclude-relative-branches', dest='generate_cbs_exclude_relative_branches',
                    action='store_true',
                    help='Exclude branches outside of the working directory',
                    default=False )

        add_option( '--generate-cbs-place-with-sconscript', dest='generate_cbs_place_with_sconscript',
                    action='store_true',
                    help='Exclude branches outside of the working directory',
                    default=False )

        add_option( '--generate-cbs-exclude-paths-starting', type='string', nargs=1,
                    action='callback', callback=cuppa.options.list_parser( 'generate_cbs_exclude_paths_starting' ),
                    help='Exclude dependencies starting with the specified paths from the file list for the project' )


    @classmethod
    def add_to_env( cls, env ):
        try:
            generate = env.get_option( 'generate-cbs' )
            if generate:
                obj = cls( env,
                           env.get_option( 'generate_cbs_include_thirdparty' ),
                           env.get_option( 'generate_cbs_exclude_relative_branches' ),
                           env.get_option( 'generate_cbs_exclude_paths_starting' ),
                           env.get_option( 'generate_cbs_place_with_sconscript' ) )

                env['project_generators']['codeblocks'] = obj

        except CodeblocksException as error:
            print as_error( env, "cuppa: error: failed to create CodeBlocks project generator with error [{}]".format( error ) )


    def __init__( self, env, include_thirdparty, exclude_branches, excluded_paths_starting, place_cbs_by_sconscript ):

        self._include_thirdparty = include_thirdparty
        self._exclude_branches = exclude_branches
        self._excluded_paths_starting = excluded_paths_starting and excluded_paths_starting or []
        self._place_cbs_by_sconscript = place_cbs_by_sconscript

        self._projects = {}

        base_include = self._exclude_branches and env['base_path'] or env['branch_root']

        base = os.path.realpath( base_include )
        download = os.path.realpath( env['download_root'] )

        thirdparty = env['thirdparty'] and os.path.realpath( env['thirdparty'] ) or None

        common, tail1, tail2 = cuppa.path.split_common( base, download )
        download_under_base = common and not tail1

        thirdparty_under_base = None
        if thirdparty:
            common, tail1, tail2 = cuppa.path.split_common( base, thirdparty )
            thirdparty_under_base = common and not tail1

        self._exclude_paths = self._excluded_paths_starting
        self._build_root = [ env['build_root'] ]

        if not self._include_thirdparty:
            if download_under_base:
                self._exclude_paths.append( env['download_root'] )

            if thirdparty and thirdparty_under_base:
                self._exclude_paths.append( env['thirdparty'] )

        self._include_paths = [ base_include ]

        if self._include_thirdparty:
            if not download_under_base:
                self._include_paths.append( env['download_root'] )

            if thirdparty and not thirdparty_under_base:
                self._include_paths.append( env['thirdparty'] )

        self._ignored_types = ignored_types( env )

        cuppa.progress.NotifyProgress.register_callback( None, self.on_progress )

        print "cuppa: project-generator (CodeBlocks): Including Paths Under    = {}".format( as_notice( env, str( self._include_paths ) ) )
        print "cuppa: project-generator (CodeBlocks): Excluding Paths Starting = {}".format( as_notice( env, str( self._exclude_paths ) ) )


    def on_progress( self, progress, sconscript, variant, env, target, source ):
        if progress == 'begin':
            self.on_sconscript_begin( env, sconscript )
        elif progress == 'started':
            self.on_variant_started( env, sconscript )
        elif progress == 'finished':
            self.on_variant_finished( env, sconscript, target[0], source )
        elif progress == 'end':
            self.on_sconscript_end( env, sconscript )
        elif progress =='sconstruct_end':
            self.on_sconstruct_end( env )


    def on_sconscript_begin( self, env, sconscript ):
        pass


    def on_variant_started( self, env, sconscript ):
        project          = sconscript
        toolchain        = env['toolchain'].name()
        variant          = env['variant'].name()
        build_root       = env['build_root']
        working_dir      = env['build_dir']
        final_dir_offset = env['final_dir']

        self.update( env, project, toolchain, variant, build_root, working_dir, final_dir_offset )


    def on_variant_finished( self, env, sconscript, root_node, source ):
        project = sconscript

        tree_processor = ProcessNodes(
                env,
                self._projects[project]['path'],
                self._projects[project]['files'],
                self._include_paths,
                self._exclude_paths + self._build_root,
                self._ignored_types
        )

        cuppa.tree.process_tree( root_node, tree_processor, self._exclude_paths )

        self._projects[project]['files'] = tree_processor.file_paths()


    def on_sconscript_end( self, env, sconscript ):
        self.write( env, sconscript )


    def on_sconstruct_end( self, env ):
        workspace_dir = os.path.join( env['working_dir'], "cbs" )
        workspace_path = os.path.join( workspace_dir, "all.workspace" )

        if workspace_dir and not os.path.exists( workspace_dir ):
            os.makedirs( workspace_dir )

        print "cuppa: project-generator (CodeBlocks): write workspace [{}]".format(
            as_notice( env, workspace_path )
        )

        with open( workspace_path, "w" ) as workspace_file:
            workspace_file.write( "\n".join( self.create_workspace( self._projects ) ) )


    def update( self, env, project, toolchain, variant, build_root, working_dir, final_dir_offset ):

        print "cuppa: project-generator (CodeBlocks): update project [{}] for [{}, {}]".format( as_notice( env, project ), as_notice( env, toolchain) , as_notice( env, variant ) )

        if project not in self._projects:

            title = os.path.splitext( project )[0]
            directory, filename = os.path.split( title )
            cbs_file_name = filename
            if cbs_file_name in [ 'sconscript', 'SConscript', 'Sconscript' ]:
                cbs_file_name = os.path.split( directory )[1]
                if cbs_file_name == ".":
                    cbs_file_name = os.path.split( os.path.abspath( env['sconscript_dir'] ) )[1]
                    if not cbs_file_name:
                        cbs_file_name = "sconscript"

            if not self._place_cbs_by_sconscript:
                directory = env['working_dir']
            directory = os.path.join( directory, "cbs")
            project_file = directory + os.path.sep + cbs_file_name + ".cbp"

            execution_dir = ''
            if directory:
                execution_dir = os.path.relpath( os.getcwd(), directory )
                execution_dir = (   os.path.pardir
                                  + os.path.sep
                                  + os.path.join( execution_dir,
                                                  os.path.split( os.path.abspath( os.getcwd() ) )[1] ) )

            self._projects[project] = {}
            self._projects[project]['title']         = title
            self._projects[project]['directory']     = directory
            self._projects[project]['path']          = os.path.join( os.getcwd(), directory )
            self._projects[project]['execution_dir'] = execution_dir
            self._projects[project]['project_file']  = project_file
            self._projects[project]['working_dir']   = os.path.join( execution_dir, working_dir )

            self._projects[project]['final_dir']     = os.path.normpath(
                                                            os.path.join(
                                                                self._projects[project]['working_dir'],
                                                                final_dir_offset
                                                            )
                                                       )

            self._projects[project]['variants']      = set()
            self._projects[project]['toolchains']    = set()
            self._projects[project]['files']         = set()
            self._projects[project]['targets']       = {}
            self._projects[project]['lines_header']  = []
            self._projects[project]['lines_footer']  = []

        if not self._projects[project]['lines_header']:
            self._projects[project]['lines_header'] = self.create_header( self._projects[project]['title'],
                                                                          execution_dir )

        if not self._projects[project]['lines_footer']:
            self._projects[project]['lines_footer'] = self.create_footer()

        self._projects[project]['variants'].add( variant )
        self._projects[project]['toolchains'].add( toolchain )


        target = "{}-{}".format( toolchain, variant )

        test_actions = [ "", "--test" ]

        for action in test_actions:

            target_name = target + action

            if target_name not in self._projects[project]['targets']:
                self._projects[project]['targets'][target_name] = self.create_target(
                        target_name,
                        project,
                        toolchain,
                        variant,
                        action,
                        self._projects[project]['working_dir'],
                        self._projects[project]['final_dir'] )


    def write( self, env, project ):

        project_file = self._projects[project]['project_file']
        directory    = self._projects[project]['directory']

        print "cuppa: project-generator (CodeBlocks): write [{}] for [{}]".format(
            as_notice( env, self._projects[project]['project_file'] ),
            as_notice( env, project )
        )

        if directory and not os.path.exists( directory ):
            os.makedirs( directory )

        lines = []
        lines += self._projects[project]['lines_header']

        for target in sorted( self._projects[project]['targets'].itervalues() ):
            lines += target

        lines += [ '\t\t</Build>' ]
        for filepath in sorted( self._projects[project]['files'] ):
            lines += [ '\t\t<Unit filename="' + filepath + '" />' ]

        lines += self._projects[project]['lines_footer']

        with open( project_file, "w" ) as cbs_file:
            cbs_file.write( "\n".join( lines ) )


    def create_header( self, project, execution_dir ):
        lines = [
'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
'<CodeBlocks_project_file>\n'
'\t<FileVersion major="1" minor="6" />\n'
'\t<Project>' ]

        lines += [
'\t\t<Option title="' + project + '" />' ]

        lines += [
'\t\t<Option makefile="sconstruct" />\n'
'\t\t<Option makefile_is_custom="1" />' ]

        lines += [
'\t\t<Option execution_dir="' + execution_dir + '" />' ]

#        lines += [
#'\t\t<Option compiler="gcc" />' ]

        lines += [
'\t\t<MakeCommands>\n'
'\t\t\t<Build command="scons --standard-output --scripts=$SCRIPTS --$VARIANT --toolchains=$TOOLCHAINS $TEST" />\n'
'\t\t\t<CompileFile command="" />\n'
'\t\t\t<Clean command="scons --standard-output --scripts=$SCRIPTS --$VARIANT --toolchains=$TOOLCHAINS $TEST -c" />\n'
'\t\t\t<DistClean command="" />\n'
'\t\t\t<AskRebuildNeeded command="" />\n'
'\t\t\t<SilentBuild command="" />\n'
'\t\t</MakeCommands>' ]

        lines += [
'\t\t<Build>' ]

        return lines


    def create_footer( self ):
        lines = [
'\t</Project>\n'
'</CodeBlocks_project_file>\n' ]

        return lines


    def create_target( self, target, project, toolchain, variant, test, working_dir, final_dir ):
        lines = [
'\t\t\t<Target title="' + target + '">\n'
'\t\t\t\t<Option working_dir="' + final_dir + '" />\n'
'\t\t\t\t<Option object_output="' + working_dir + '" />\n'
'\t\t\t\t<Option type="1" />\n'
'\t\t\t\t<Compiler>\n'
'\t\t\t\t</Compiler>\n'
'\t\t\t\t<Environment>' ]

        lines += [
'\t\t\t\t\t<Variable name="SCRIPTS" value="' + project + '" />\n'
'\t\t\t\t\t<Variable name="TOOLCHAINS" value="' + toolchain + '" />\n'
'\t\t\t\t\t<Variable name="VARIANT" value="' + variant + '" />'
'\t\t\t\t\t<Variable name="TEST" value="' + test + '" />' ]

        lines += [
'\t\t\t\t</Environment>\n'
'\t\t\t\t<MakeCommands>\n'
'\t\t\t\t\t<Build command="" />\n'
'\t\t\t\t\t<CompileFile command="" />\n'
'\t\t\t\t\t<Clean command="" />\n'
'\t\t\t\t\t<DistClean command="" />\n'
'\t\t\t\t\t<AskRebuildNeeded command="" />\n'
'\t\t\t\t\t<SilentBuild command="" />\n'
'\t\t\t\t</MakeCommands>\n'
'\t\t\t</Target>' ]

        return lines


    def create_workspace( self, projects ):
        lines = [
'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
'<CodeBlocks_workspace_file>\n'
'\t<Workspace title="Workspace">' ]

        for project in projects.itervalues():

            project_file = project['project_file']
            base_path    = project['path']
            project_file = os.path.relpath( os.path.abspath( project_file ), base_path )

            lines += [
'\t\t<Project filename="' + project_file + '" />' ]

        lines += [
'\t</Workspace>\n'
'</CodeBlocks_workspace_file>\n' ]
        return lines


class ProcessNodes(object):

    def __init__( self, env, base_path, files, allowed_paths, excluded_paths, ignored_types ):
        self._env = env
        self._base_path = base_path
        self._files = files
        self._allowed_paths = allowed_paths
        self._excluded_paths = excluded_paths
        self._ignored_types = ignored_types

    def __call__( self, node ):
        file_path = str(node)

        for excluded in self._excluded_paths:
            if file_path.startswith( excluded ):
                return

        path, ext = os.path.splitext( file_path )

        if ext and ext in self._ignored_types:
            return

        for allowed in self._allowed_paths:
            prefix = os.path.commonprefix( [ os.path.abspath( file_path ), allowed ] )
#            print "cuppa: project-generator (CodeBlocks): str(file)=[{}], file.path=[{}], allowed=[{}], prefix=[{}]".format(
#                    as_notice( self._env, str(node) ),
#                    as_notice( self._env, node.path ),
#                    as_notice( self._env, str(allowed) ),
#                    as_notice( self._env, str(prefix) )
#            )
            if prefix != allowed:
                return

#        print "cuppa: project-generator (CodeBlocks): str(file)=[{}], file.path=[{}], allowed=[{}], prefix=[{}]".format(
#                as_notice( self._env, str(node) ),
#                as_notice( self._env, node.path ),
#                as_notice( self._env, str(allowed) ),
#                as_notice( self._env, str(prefix) )
#        )

        file_path = os.path.relpath( os.path.abspath( file_path ), self._base_path )
        self._files.add( file_path )
        return

    def file_paths( self ):
        return self._files



