
#          Copyright Jamie Allsop 2018-2018
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Preprocess
#-------------------------------------------------------------------------------

import re

class AnsiEscape:

    ansi_escape_re = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]')

    @classmethod
    def strip( cls, line ):
        return cls.ansi_escape_re.sub( '', line )
