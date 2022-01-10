
#          Copyright Jamie Allsop 2019-2022
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
    from collections import MutableMapping as MutableMapping
except ImportError: # Python 3.10+
    from collections.abc import MutableMapping as MutableMapping

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
    if None == bytes_or_string or is_string( bytes_or_string ):
        return bytes_or_string
    return bytes_or_string.decode(encoding)

def as_byte_str( bytes_or_string, encoding='utf-8' ):
    if None == bytes_or_string or not is_string( bytes_or_string ):
        return bytes_or_string
    return bytes_or_string.encode(encoding)

try:
    from html import escape
except ImportError:
    from cgi import escape

try:
    import itertools.izip as zip
except:
    # python3
    pass

try:
    from re import _pattern_type as Pattern
except ImportError:
    from re import Pattern as Pattern

def encode( payload, encoding='utf-8' ):
    if sys.version_info[0] <= 2:
        return payload.encode(encoding)
    else:
        return payload
