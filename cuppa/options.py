
#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Options
#-------------------------------------------------------------------------------


class list_parser(object):

    def __init__( self, attribute ):
        self._attribute = attribute

    def __call__( self, option, opt, value, parser):
        setattr( parser.values, self._attribute, value.split(',') )
