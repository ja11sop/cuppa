
#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Utility
#-------------------------------------------------------------------------------

# Check if an object is a string
try:
    basestring
    def is_string( x ):
        return isinstance( x, basestring )
except NameError:
    def is_string( x ):
        return isinstance( x, str )
