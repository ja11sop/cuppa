
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Generate Bitten Report
#-------------------------------------------------------------------------------

import json
import os
import itertools
import cgi

import cuppa.progress


class GenerateReportBuilder(object):

    def __init__( self, final_dir ):
        self._final_dir = final_dir


    def emitter( self, target, source, env ):
        sources = []
        targets = []
        try:
            for s in source:
                if os.path.splitext( str(s) )[1] == ".json":
                    sources.append( str(s) )
                    target_report = os.path.splitext( str(s) )[0] + "_bitten.xml"
                    targets.append( target_report )
        except StopIteration:
            pass
        return targets, sources


    def GenerateBittenReport( self, target, source, env ):
        for s, t in itertools.izip( source, target ):
            test_cases = self._read( str(s) )
            self._write( str(t), test_cases )
        return None


    def _read( self, json_report_path ):
        with open( json_report_path, "r" ) as report:
            test_cases = json.load( report )
            return test_cases


    def _write( self, destination_path, test_cases ):
        with open( destination_path, "w" ) as report:
            report.write( '<report category="test">\n' )
            for test in test_cases:
                report.write( '    <test>\n' )

                if not 'file' in test or test['file'] == None:
                    test['file'] = ""
                if not 'line' in test or test['line'] == None:
                    test['line'] = ""
                if not 'branch_dir' in test or test['branch_dir'] == None:
                    test['branch_dir'] = ""

                for key, value in test.iteritems():
                    if key == "cpu_times" or key == "timer":
                        continue
                    report.write( '        <%s>' % key )
                    if key == 'stdout':
                        value = ( '<span class="line">' + cgi.escape(line) + '<br /></span>' for line in value )
                        value = '<![CDATA[' + "\n".join( value ) + ']]>'
                    else:
                        value = cgi.escape( str( value ) )
                    report.write( value )
                    report.write( '</%s>\n' % key )
                report.write( '    </test>\n' )
            report.write( '</report>\n' )



class GenerateBittenReportMethod(object):

    def __call__( self, env, source, final_dir=None ):
        builder = GenerateReportBuilder( final_dir )
        env['BUILDERS']['GenerateBittenReport'] = env.Builder( action=builder.GenerateBittenReport, emitter=builder.emitter )
        report = env.GenerateBittenReport( [], source )
        cuppa.progress.NotifyProgress.add( env, report )
        return report


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "GenerateBittenReport", cls() )

