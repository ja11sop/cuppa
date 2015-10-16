
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   MarkdownToHtmlMethod
#-------------------------------------------------------------------------------

import os.path
import itertools
import grip
import cuppa.progress


class GripRunner(object):

    def __call__( self, target, source, env ):
        for s, t in itertools.izip( source, target ):
            in_file  = str(s)
            out_file = str(t)
            try:
                grip.export( path=in_file, render_wide=True, out_filename=out_file )
            except Exception as error:
                print "cuppa: error: grip.export( path={}, render_wide=True, out_filename={}) failed with error [{}]".format( in_file, out_file, error )

        return None


class GripEmitter(object):

    def __init__( self, output_dir ):
        self._output_dir = output_dir

    def __call__( self, target, source, env ):
        target = []
        for s in source:
            path = os.path.join( self._output_dir, os.path.split( str(s) )[1] )
            t = os.path.splitext(path)[0] + ".html"
            target.append(t)
        return target, source


class MarkdownToHtmlMethod(object):

    def __call__( self, env, source, final_dir=None ):
        if final_dir == None:
            final_dir = env['abs_final_dir']

        env.AppendUnique( BUILDERS = {
            'Grip' : env.Builder(
                action  = GripRunner(),
                emitter = GripEmitter(final_dir) )
        } )

        html = env.Grip( [], source )
        cuppa.progress.NotifyProgress.add( env, html )
        return html


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "MarkdownToHtml", cls() )

