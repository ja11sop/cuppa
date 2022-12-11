#          Copyright Jamie Allsop 2022-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   AsciidocToHtmlMethod
#-------------------------------------------------------------------------------

# Python imports
import os.path
import shlex
import sys

# cuppa imports
import cuppa.progress
from cuppa.output_processor import IncrementalSubProcess
from cuppa.log import logger
from cuppa.colourise import as_notice, as_error


def process_stdout( line ):
    sys.stdout.write( line + '\n' )


def process_stderr( line ):
    sys.stderr.write( line + '\n' )


_asciidoc_extensions = set([
        ".adoc",
        ".asciidoc",
])


def _is_asciidoc( path ):
    extension = os.path.splitext( str(path) )[1]
    return extension and extension in _asciidoc_extensions


class AsciidoctorRunner(object):

    def __init__( self, plantuml_config=None ):
        if plantuml_config and isinstance( plantuml_config, list ):
            self._plantuml_config = plantuml_config[0]
        else:
            self._plantuml_config = plantuml_config
        self._command_template = "asciidoctor -r asciidoctor-diagram"
        if self._plantuml_config:
            self._command_template += " -a config={}".format( str(self._plantuml_config) )
        self._command_template += " -o {} {}"


    def __call__( self, target, source, env ):
        for s, t in zip( source, target ):
            in_file  = str(s)
            out_file = str(t)
            working_dir = env['sconstruct_dir']

            command = self._command_template.format( out_file, in_file )
            logger.debug( "Creating HTML files using command [{}] in working directory [{}]".format( as_notice( command ), as_notice(working_dir) ) )

            try:
                return_code = IncrementalSubProcess.Popen2(
                        process_stdout,
                        process_stderr,
                        shlex.split( command ),
                        cwd=working_dir
                )

                if return_code < 0:
                    logger.error( "Execution of [{}] terminated by signal: {}".format( as_notice( command ), as_error( str(-return_code) ) ) )
                elif return_code > 0:
                    logger.error( "Execution of [{}] returned with error code: {}".format( as_notice( command ), as_error( str(return_code) ) ) )

            except OSError as error:
                logger.error( "Execution of [{}] failed with error: {}".format( as_notice( command ), as_error( str(error) ) ) )

        return None


class AsciidoctorEmitter(object):

    def __init__( self, output_dir, plantuml_config=None ):
        self._output_dir = output_dir
        if plantuml_config and isinstance( plantuml_config, list ):
            self._plantuml_config = plantuml_config[0]
        else:
            self._plantuml_config = plantuml_config


    def __call__( self, target, source, env ):
        # We will skip over paired sources and targets and only enumerate
        # over the sources that come after the last specified target
        last_source = len(source)
        s_idx = len(target)
        while s_idx < last_source:
            if _is_asciidoc( str(source[s_idx]) ):
                path = os.path.join( self._output_dir, os.path.split( str(source[s_idx]) )[1] )
                t = os.path.splitext(path)[0] + ".html"
                target.append(t)
            s_idx = s_idx+1

        if self._plantuml_config:
            source.append( self._plantuml_config )

        return target, source


class AsciidoctorToHtmlMethod(object):

    def __call__( self, env, target, source, final_dir=None, plantuml_config_file=None ):
        if final_dir == None:
            final_dir = env['abs_final_dir']

        env.AppendUnique( BUILDERS = {
            'AsciidocToHtml' : env.Builder(
                action  = AsciidoctorRunner( plantuml_config=plantuml_config_file ),
                emitter = AsciidoctorEmitter( final_dir, plantuml_config=plantuml_config_file ) )
        } )

        html = env.AsciidocToHtml( target, source )
        cuppa.progress.NotifyProgress.add( env, html )
        return html


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "AsciidocToHtml", cls() )

