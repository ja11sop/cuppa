#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Select tool failure lines for post-exit reprint
#-------------------------------------------------------------------------------

"""Pick high-signal lines from captured tool output after a non-zero exit.

Parallel CMake/Ninja builds often bury the real ``FAILED:`` / loader error under
a flood of continuing compile warnings. ``cuppa.utility.command.run`` reprints a
short selection after the exit-code line so the failure stays visible.
"""

from __future__ import annotations

import re


# Prefer ninja/cmake/loader failures; also keep compiler ``error:`` lines.
# Avoid matching ``-Werror`` tokens alone or ``error while`` inside notes.
_PRIORITY_PATTERNS = (
        re.compile( r'(?i)\bFAILED:' ),
        re.compile( r'(?i)\bCMake Error\b' ),
        re.compile( r'(?i)error while loading shared libraries' ),
        re.compile( r'(?i)\bninja:\s+build stopped' ),
        re.compile( r'(?i)\bNMAKE\s*:\s*fatal' ),
        re.compile( r'(?i)\bfatal error:' ),
)

_ERROR_PATTERNS = (
        re.compile( r'(?i)(?:^|\s)error:' ),
        re.compile( r'(?i)--\w+_out:.*Plugin failed' ),
        re.compile( r'(?i)\bundefined reference\b' ),
)


def line_failure_priority( line ):
    """Return ``2`` (high), ``1`` (error-like), or ``0`` (not a failure line)."""
    text = line.strip()
    if not text:
        return 0
    for pattern in _PRIORITY_PATTERNS:
        if pattern.search( text ):
            return 2
    for pattern in _ERROR_PATTERNS:
        if pattern.search( text ):
            return 1
    return 0


def select_failure_detail_lines( lines, limit=40 ):
    """Return up to ``limit`` failure-looking lines, high-priority first.

    Within each priority band, preserve first-seen order. Deduplicate exact
    matches. Empty or non-matching input yields an empty list.
    """
    if limit < 1 or not lines:
        return []

    seen = set()
    high = []
    normal = []
    for line in lines:
        text = line.rstrip( '\n' )
        priority = line_failure_priority( text )
        if priority == 0:
            continue
        if text in seen:
            continue
        seen.add( text )
        if priority >= 2:
            high.append( text )
        else:
            normal.append( text )

    selected = high + normal
    return selected[:limit]
