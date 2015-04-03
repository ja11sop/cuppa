
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Codeblocks
#-------------------------------------------------------------------------------
import shlex
import os
from exceptions   import Exception
from cuppa.output_processor import IncrementalSubProcess


class CodeblocksException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Codeblocks:

    @classmethod
    def add_options( cls, add_option ):

        def parse_paths_option(option, opt, value, parser):
            parser.values.excluded_paths_starting = value.split(',')


        add_option( '--generate-cbs', dest='generate-cbs',
                    action='store_true',
                    help='Tell scons to generate a Codeblocks project',
                    default=False )

        add_option( '--generate-cbs-ignore-variant', dest='generate-cbs-ignore-variant',
                    action='store_true',
                    help='Ignore build variants when creating the file list for the project',
                    default=False )

        add_option( '--generate-cbs-exclude-paths-starting', type='string', nargs=1,
                    action='callback', callback=parse_paths_option,
                    help='Exclude dependencies starting with the specified paths from the file list for the project' )


    @classmethod
    def add_to_env( cls, env ):
        try:
            generate = env.get_option( 'generate-cbs' )

            if generate:
                obj = cls( env.get_option( 'generate-cbs-ignore-variant' ),
                           None )
#                           env.get_option( 'excluded_paths_starting' ) )
                env['project_generators']['codeblocks'] = obj

        except CodeblocksException:
            pass


    def __init__( self, ignore_variants, excluded_paths_starting ):
        self.ignore_variants = ignore_variants
        self.excluded_paths_starting = excluded_paths_starting
        self.projects = {}


    def get_dependency_list( self, base_path, files, variant, env, project, build_dir ):

        tree_command = "scons --no-exec --tree=prune --" + variant + " --projects=" + project
        #print "Project Generator (CodeBlocks): Update using [" + tree_command + "]"

        if not self.excluded_paths_starting:
            self.excluded_paths_starting = [ build_dir ]

        tree_processor = ProcessTree( base_path, files, [ env['branch_root'] ], self.excluded_paths_starting )

        IncrementalSubProcess.Popen(
            tree_processor,
            shlex.split( tree_command )
        )
        return tree_processor.file_paths()


    def update( self, variant, env, project, build_root, working_dir, final_dir_offset ):

        if project not in self.projects:

            title = os.path.splitext( project )[0]
            directory, filename = os.path.split( title )
            directory = os.path.join( directory, "cbs")
            project_file = directory + os.path.sep + filename + ".cbp"

            execution_dir = ''
            if directory:
                execution_dir = os.path.relpath( os.getcwd(), directory )
                execution_dir = (   os.path.pardir
                                  + os.path.sep
                                  + os.path.join( execution_dir,
                                                  os.path.split( os.path.abspath( os.getcwd() ) )[1] ) )

            self.projects[project] = {}
            self.projects[project]['title']         = title
            self.projects[project]['directory']     = directory
            self.projects[project]['path']          = os.path.join( os.getcwd(), directory )
            self.projects[project]['execution_dir'] = execution_dir
            self.projects[project]['project_file']  = project_file
            self.projects[project]['working_dir']   = os.path.join( execution_dir, working_dir )
            self.projects[project]['final_dir']     = os.path.normpath(
                                                          os.path.join( self.projects[project]['working_dir'],
                                                                        final_dir_offset ) )

            self.projects[project]['files']         = set()
            self.projects[project]['variants']      = {}
            self.projects[project]['lines_header']  = []
            self.projects[project]['lines_footer']  = []

        self.projects[project]['files'] = self.get_dependency_list( self.projects[project]['path'],
                                                                    self.projects[project]['files'],
                                                                    variant,
                                                                    env,
                                                                    project,
                                                                    build_root )

        if not self.projects[project]['lines_header']:
            self.projects[project]['lines_header'] = self.create_header( self.projects[project]['title'],
                                                                         execution_dir )

        if not self.projects[project]['lines_footer']:
            self.projects[project]['lines_footer'] = self.create_footer()

        if variant not in self.projects[project]['variants']:
            self.projects[project]['variants'][variant] = self.create_target( project,
                                                                              variant,
                                                                              self.projects[project]['working_dir'],
                                                                              self.projects[project]['final_dir'] )


    def write( self, project ):
        project_file = self.projects[project]['project_file']
        directory    = self.projects[project]['directory']

        print "Project Generator (CodeBlocks): Update [" + self.projects[project]['project_file'] + "]"

        if directory and not os.path.exists( directory ):
            os.makedirs( directory )

        lines = []
        lines += self.projects[project]['lines_header']

        for variant in self.projects[project]['variants'].itervalues():
            lines += variant

        lines += [ '\t\t</Build>' ]
        for filepath in sorted( self.projects[project]['files'] ):
            lines += [ '\t\t<Unit filename="' + filepath + '" />' ]

        lines += self.projects[project]['lines_footer']

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
'\t\t\t<Build command="scons --standard-output --projects=$PROJECTS --$VARIANT" />\n'
'\t\t\t<CompileFile command="" />\n'
'\t\t\t<Clean command="scons --standard-output --projects=$PROJECTS --$VARIANT -c" />\n'
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
'</CodeBlocks_project_file>' ]

        return lines


    def create_target( self, project, variant, working_dir, final_dir ):
        lines = [
'\t\t\t<Target title="' + variant + '">\n'
'\t\t\t\t<Option working_dir="' + final_dir + '" />\n'
'\t\t\t\t<Option object_output="' + working_dir + '" />\n'
'\t\t\t\t<Option type="1" />\n'
#'\t\t\t\t<Option compiler="gcc" />\n'
'\t\t\t\t<Compiler>\n'
'\t\t\t\t</Compiler>\n'
'\t\t\t\t<Environment>' ]

        lines += [
'\t\t\t\t\t<Variable name="PROJECTS" value="' + project + '" />\n'
'\t\t\t\t\t<Variable name="VARIANT" value="' + variant + '" />' ]

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


class ProcessTree:

    def __init__( self, base_path, files, allowed_paths, excluded_paths ):
        self.base_path = base_path
        self.files = files
        self.allowed_paths = allowed_paths
        self.excluded_paths = excluded_paths

        #print "Project Generator (CodeBlocks): Allowed Paths Under    = " + str( self.allowed_paths )
        #print "Project Generator (CodeBlocks): Exclude Paths Starting = " + str( self.excluded_paths )

    def __call__( self, line ):
        line = line.lstrip( ' |+-[' )
        line = line.rstrip( ']' )

        file_path = line

        for excluded in self.excluded_paths:
            if file_path.startswith( excluded ):
                return

        if not os.path.exists( file_path ) or not os.path.isfile( file_path ):
            return

        for allowed in self.allowed_paths:
            prefix = os.path.commonprefix( [ os.path.abspath( file_path ), allowed ] )
            if prefix != allowed:
                return

        if file_path not in self.files:
            file_path = os.path.relpath( os.path.abspath( file_path ), self.base_path )
            self.files.add( file_path )
            return

    def file_paths( self ):
        return self.files


