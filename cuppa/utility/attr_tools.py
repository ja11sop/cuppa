#          Copyright Jamie Allsop 2020-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   attr_tools.py
#-------------------------------------------------------------------------------

def try_attr_as_str( instance, attribute, result_on_error=None ):
    try:
        if callable( getattr( instance, attribute ) ):
            return str(getattr( instance, attribute )())
    except AttributeError:
        return result_on_error
