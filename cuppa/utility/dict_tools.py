
#          Copyright Jamie Allsop 2020-2020
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Dictionary Tools
#-------------------------------------------------------------------------------

import six


def args_from_dict( dictionary ):
    args = {}

    if not dictionary or not isinstance( dictionary, dict ):
        return args

    for key, value in six.iteritems( dictionary ):
        args[key] = callable(value) and value() or value
    return args
