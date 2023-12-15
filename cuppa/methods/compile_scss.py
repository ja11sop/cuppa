
#          Copyright Jamie Allsop 2022-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CompileScssMethod
#-------------------------------------------------------------------------------

import sys

import cuppa.progress
from cuppa.log import logger
from cuppa.colourise import as_notice


class CompileScssAction(object):

    def __init__( self, load_path ):
        self._load_path = load_path

    def __call__( self, target, source, env ):
        if self._load_path:
            logger.debug( "compiling SCSS files using load-path [{}]".format( as_notice( self._load_path ) ) )
        import shlex
        import subprocess
        for s, t in zip( source, target ):
            logger.debug( "compiling SCSS file [{}] to CSS file [{}]".format( as_notice( s.path ), as_notice( t.path ) ) )

            if sys.version_info < (3,11,0):
                # pyscss needs an update to allow it to work under python 3.11
                with open( s.abspath, 'rb', 0) as scss_file, open( t.abspath, 'wb') as css_file:
                    load_path = self._load_path and "--load-path {}".format( self._load_path ) or ""
                    command = "python -m scss {load_path}".format( load_path = load_path )
                    subprocess.call( shlex.split( command ), stdin=scss_file, stdout=css_file )
            else:
                load_path = self._load_path and "--include-path {}".format( self._load_path ) or ""
                command = "pysassc {load_path} {scss_file} {css_file}".format( load_path = load_path, scss_file=s.abspath, css_file=t.abspath )
                subprocess.call( shlex.split( command ) )

        return None


class CompileScssEmitter(object):

    def __call__( self, target, source, env ):
        import os.path
        if not target:
            for s in source:
                target.append( env.File( os.path.splitext(s.abspath)[0]+".css" ) )

        return target, source


class CompileScssMethod(object):

    def __call__( self, env, target, source, load_path=None ):

        env.AppendUnique( BUILDERS = {
            'CompileScssBuilder' : env.Builder(
                action = CompileScssAction( load_path ),
                emitter = CompileScssEmitter()
        ) } )

        from SCons.Script import Flatten
        target = Flatten( target )
        source = Flatten( source )

        css_files = env.CompileScssBuilder( target, source )
        cuppa.progress.NotifyProgress.add( env, css_files )
        return css_files

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "CompileScss", cls() )
