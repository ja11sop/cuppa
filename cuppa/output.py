
#          Copyright Jamie Allsop 2020-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Output
#-------------------------------------------------------------------------------

import sys


class AutoFlushWriter(object):

    def __init__( self, f ):
        self.f = f

    def flush( self ):
        self.f.flush()

    def write( self, x ):
        self.f.write(x)
        self.f.flush()


try:
    import colorama
    sys.stdout = AutoFlushWriter( colorama.initialise.wrapped_stdout )
    sys.stderr = AutoFlushWriter( colorama.initialise.wrapped_stderr )
except ImportError:
    sys.stdout = AutoFlushWriter( sys.stdout )
    sys.stderr = AutoFlushWriter( sys.stderr )
