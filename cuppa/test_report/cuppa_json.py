
#          Copyright Jamie Allsop 2015-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Json Encoder for Cuppa Types
#-------------------------------------------------------------------------------

import json

import cuppa.timer


class Encoder( json.JSONEncoder ):

    def default(self, obj):

        if isinstance( obj, cuppa.timer.CpuTimes ):
            return {
                "wall_time"    : obj.wall,
                "process_time" : obj.process,
                "system_time"  : obj.system,
                "user_time"    : obj.user
            }
        elif isinstance( obj, cuppa.timer.Timer ):
            return {
                "wall_time"    : obj.elapsed().wall,
                "process_time" : obj.elapsed().process,
                "system_time"  : obj.elapsed().system,
                "user_time"    : obj.elapsed().user
            }

        return json.JSONEncoder.default( self, obj )


def write_report( report_path, test_cases ):

    with open( report_path, "w" ) as report:
        json.dump(
            test_cases,
            report,
            sort_keys = True,
            indent = 4,
            separators = (',', ': '),
            cls = Encoder
        )
