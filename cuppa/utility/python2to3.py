
#          Copyright Jamie Allsop 2019-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Python2to3
#-------------------------------------------------------------------------------

import sys
if sys.version_info[0] <= 2:
    from exceptions import Exception
Exception = Exception

try:
    import Queue as Queue
except ImportError:
    import queue as Queue

try:
    import os.errno as errno
except ImportError:
    import errno as errno

try:
    from time import clock
    def process_time_ns():
        return int( clock()*1000000000 )
except:  # Python version >= 3.8
    from time import process_time_ns

try:
    from string import maketrans
except ImportError:
    maketrans = str.maketrans

from .types import is_string

def as_str( bytes_or_string, encoding='utf-8' ):
    if is_string( bytes_or_string ):
        return bytes_or_string
    return bytes_or_string.decode(encoding)
