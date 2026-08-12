#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import re

_QUOTED_FRAGMENT_RE = re.compile( r"'[^']*'" )


def normalise_message( message ):
    """Collapse quoted identifiers so template and member names share one pattern key."""
    return _QUOTED_FRAGMENT_RE.sub( "'…'", message )
